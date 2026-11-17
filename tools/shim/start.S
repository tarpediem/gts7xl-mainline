/* SPDX-License-Identifier: GPL-2.0-only */
/*
 * Boot shim entry for the Samsung Galaxy Tab S7+ 5G (gts7xl).
 *
 * The Samsung ABL only goes through with the vendor DTB, but it runs whatever
 * sits in the kernel slot. So the image carries this shim as its "kernel"
 * and the stock DTB/overlays for the ABL. The shim takes the DTB the ABL
 * prepared, moves what the ABL filled in into the embedded mainline DTB and
 * enters the embedded mainline Image.
 *
 * Design and header quirks from the Tab S7 port (GPL-2.0-only):
 * https://github.com/Iamtianyuyang/steamos-tabs7 (boot/shim).
 *
 * Entered like a kernel: EL1 (or EL2), MMU and D-cache off, x0 = DTB.
 * Position independent for any 4 KiB-aligned load address (adrp, -mcmodel=small);
 * every Qualcomm ABL loads the kernel page-aligned.
 */
	.section .head, "ax"
	.global _start
_start:
	b	entry			/* code0 */
	.long	0			/* code1 */
	.quad	0x80000			/* text_offset, as in the stock kernel */
	.quad	SHIM_RESERVE		/* image_size: all the room the shim uses */
	.quad	0xa			/* flags: LE, 4K pages, as in the stock kernel */
	.quad	0			/* res2 */
	.quad	0xecefecef		/* res3: default value of Samsung's head.S */
	.quad	0			/* res4 */
	.ascii	"ARM\x64"		/* magic */
	.long	0			/* res5 */

	.text
entry:
	mov	x19, x0

	/* Stack at the top of the reserved window. */
	adr	x1, _start
	ldr	x2, =(SHIM_RESERVE - 16)
	add	x2, x1, x2
	and	x2, x2, #~0xf
	mov	sp, x2

	adrp	x3, __bss_start
	add	x3, x3, :lo12:__bss_start
	adrp	x4, __bss_end
	add	x4, x4, :lo12:__bss_end
1:	cmp	x3, x4
	b.hs	2f
	str	xzr, [x3], #8
	b	1b

2:	mov	x0, x19
	bl	shim_main		/* returns x0 = kernel entry, x1 = DTB */
	mov	x20, x0
	mov	x21, x1

	/* The Image may have been moved: drop stale instructions. */
	ic	iallu
	dsb	sy
	isb

	mov	x0, x21
	mov	x1, xzr
	mov	x2, xzr
	mov	x3, xzr
	br	x20
	.ltorg
