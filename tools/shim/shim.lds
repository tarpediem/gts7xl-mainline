/* SPDX-License-Identifier: GPL-2.0-only */
/*
 * Linked at 0 and position independent (PC-relative addressing only).
 * The mainline DTB follows the code. The Image sits at SHIM_KERNEL_OFFSET,
 * chosen so that it is already 2 MiB aligned when the ABL loads the shim at
 * a 2 MiB aligned base plus text_offset (0x80000); otherwise the shim moves it.
 */
ENTRY(_start)
SECTIONS
{
	. = 0;
	.head : { KEEP(*(.head)) }
	.text : { *(.text*) }
	.rodata : { *(.rodata*) }
	.data : { *(.data*) }
	. = ALIGN(16);
	__bss_start = .;
	.bss : { *(.bss*) *(COMMON) }
	. = ALIGN(16);
	__bss_end = .;
	. = ALIGN(8);
	.payload.dtb : { __dtb_start = .; KEEP(*(.payload.dtb)) }
	__dtb_end = .;
	. = SHIM_KERNEL_OFFSET;
	.payload.kernel : { __kernel_start = .; KEEP(*(.payload.kernel)) }
	/DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
