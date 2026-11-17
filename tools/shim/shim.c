// SPDX-License-Identifier: GPL-2.0-only
/*
 * Move the boot data the ABL computed from the vendor DTB into the embedded
 * mainline DTB, place the embedded Image and hand over to it.
 *
 * Runs with the MMU off, so every access is Device-like memory: the build
 * uses -mstrict-align and the copies below stay word aligned.
 *
 * Nothing can be printed here. Failures fill the bootloader splash with one
 * colour and stop (the tablet then needs Vol Down + Power for 7 s):
 *   yellow  - x0 does not point to a valid device tree
 *   red     - the ABL put its DTB or the ramdisk inside the window the shim
 *             writes to (the Image header's image_size was not honoured)
 *   magenta - the embedded mainline DTB cannot be opened, or does not fit
 *   cyan    - the memory layout could not be copied
 * A green bar across the top of the screen means the shim is done and is
 * entering the kernel; what follows on screen comes from Linux.
 *
 * Based on boot/shim of https://github.com/Iamtianyuyang/steamos-tabs7
 * (GPL-2.0-only), which boots mainline on the Tab S7 11" this way.
 */
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include "libfdt.h"

#define SZ_64K		0x10000UL
#define SZ_2M		0x200000UL

/* Bootloader splash: the simple-framebuffer node of the board DTS. */
#ifndef SHIM_FB_BASE
#define SHIM_FB_BASE	0x9c000000UL
#define SHIM_FB_WIDTH	2800UL
#define SHIM_FB_HEIGHT	1752UL
#endif

#define YELLOW		0xffffff00u
#define RED		0xffff0000u
#define MAGENTA		0xffff00ffu
#define CYAN		0xff00ffffu
#define GREEN		0xff00ff00u

extern char _start[], __dtb_start[], __kernel_start[];

struct handoff {
	uint64_t kernel;
	uint64_t dtb;
};

static void paint(uint32_t colour, unsigned long rows)
{
	volatile uint32_t *fb = (volatile uint32_t *)SHIM_FB_BASE;
	unsigned long i;

	for (i = 0; i < SHIM_FB_WIDTH * rows; i++)
		fb[i] = colour;
	__asm__ volatile("dsb sy" ::: "memory");
}

static void __attribute__((noreturn)) fail(uint32_t colour)
{
	paint(colour, SHIM_FB_HEIGHT);
	for (;;)
		__asm__ volatile("wfe");
}

static uint64_t align_up(uint64_t value, uint64_t align)
{
	return (value + align - 1) & ~(align - 1);
}

static uint64_t read_le64(const void *where)
{
	const uint8_t *p = where;
	uint64_t value = 0;
	int i;

	for (i = 7; i >= 0; i--)
		value = (value << 8) | p[i];
	return value;
}

/* A one or two cell big-endian number, as in linux,initrd-start. */
static int read_cells(const void *fdt, int node, const char *name, uint64_t *value)
{
	const uint8_t *p;
	int len, i;

	p = fdt_getprop(fdt, node, name, &len);
	if (!p || (len != 4 && len != 8))
		return -1;
	*value = 0;
	for (i = 0; i < len; i++)
		*value = (*value << 8) | p[i];
	return 0;
}

static int overlaps(uint64_t start, uint64_t end, uint64_t lo, uint64_t hi)
{
	return start < hi && end > lo;
}

/* Word copy that handles overlap; both ends are 8-byte aligned here. */
static void move_words(uint64_t *dst, const uint64_t *src, uint64_t bytes)
{
	uint64_t words = (bytes + 7) / 8, i;

	if (dst < src) {
		for (i = 0; i < words; i++)
			dst[i] = src[i];
	} else if (dst > src) {
		for (i = words; i > 0; i--)
			dst[i - 1] = src[i - 1];
	}
}

/*
 * /chosen and /memory of the bootloader DTB, found in one pass over the root
 * node: that DTB is close to 1 MiB and a lookup by path walks it from the
 * start every time, which is slow with the caches off.
 */
static void find_boot_nodes(const void *fdt, int *chosen, int *memory)
{
	const char *name;
	int node, len;

	*chosen = *memory = -1;
	for (node = fdt_first_subnode(fdt, 0); node >= 0; node = fdt_next_subnode(fdt, node)) {
		name = fdt_get_name(fdt, node, &len);
		if (!name)
			continue;
		if (*chosen < 0 && len == 6 && !memcmp(name, "chosen", 6))
			*chosen = node;
		else if (*memory < 0 && len >= 6 && !memcmp(name, "memory", 6) &&
			 (len == 6 || name[6] == '@'))
			*memory = node;
		if (*chosen >= 0 && *memory >= 0)
			return;
	}
}

/* Copy one property of the bootloader DTB node `src` to the node `path` of ours. */
static void copy_prop(const void *from, int src, void *to, const char *path,
		      const char *name, int required)
{
	const void *value = NULL;
	int dst, len;

	if (src >= 0)
		value = fdt_getprop(from, src, name, &len);
	if (!value) {
		if (required)
			fail(CYAN);
		return;
	}
	dst = fdt_path_offset(to, path);
	if (dst < 0 || fdt_setprop(to, dst, name, value, len))
		fail(CYAN);
}

struct handoff shim_main(const void *bootloader_dtb)
{
	uint64_t base = (uint64_t)_start;
	uint64_t window_end = base + SHIM_RESERVE;
	uint64_t image_size, kernel, dtb, start, end;
	void *patched;
	int chosen, memory;

	if (fdt_check_header(bootloader_dtb))
		fail(YELLOW);

	/*
	 * The arm64 boot protocol wants the Image at a 2 MiB aligned address.
	 * It is there already when the ABL loads the shim at a 2 MiB aligned
	 * base + text_offset; if not, it is moved up to the next boundary.
	 */
	image_size = read_le64(__kernel_start + 16);
	kernel = align_up((uint64_t)__kernel_start, SZ_2M);
	dtb = align_up(kernel + image_size, SZ_64K);
	if (dtb + SHIM_DTB_ROOM + SHIM_STACK_ROOM > window_end)
		fail(MAGENTA);

	/* Nothing the ABL prepared may sit where the Image, its BSS and the DTB go. */
	start = (uint64_t)bootloader_dtb;
	if (overlaps(start, start + fdt_totalsize(bootloader_dtb), base, window_end))
		fail(RED);
	find_boot_nodes(bootloader_dtb, &chosen, &memory);
	if (chosen >= 0 &&
	    !read_cells(bootloader_dtb, chosen, "linux,initrd-start", &start) &&
	    !read_cells(bootloader_dtb, chosen, "linux,initrd-end", &end) &&
	    overlaps(start, end, base, window_end))
		fail(RED);

	move_words((uint64_t *)kernel, (const uint64_t *)__kernel_start, image_size);

	patched = (void *)dtb;
	if (fdt_open_into(__dtb_start, patched, SHIM_DTB_ROOM))
		fail(MAGENTA);

	/*
	 * What the ABL computed for this boot. Only the memory layout is
	 * mandatory: without a command line or a ramdisk the kernel still
	 * gets far enough to show its log on the framebuffer.
	 */
	copy_prop(bootloader_dtb, memory, patched, "/memory", "reg", 1);
	copy_prop(bootloader_dtb, chosen, patched, "/chosen", "bootargs", 0);
	copy_prop(bootloader_dtb, chosen, patched, "/chosen", "linux,initrd-start", 0);
	copy_prop(bootloader_dtb, chosen, patched, "/chosen", "linux,initrd-end", 0);
	copy_prop(bootloader_dtb, chosen, patched, "/chosen", "kaslr-seed", 0);
	copy_prop(bootloader_dtb, chosen, patched, "/chosen", "rng-seed", 0);

	if (fdt_pack(patched))
		fail(CYAN);

	paint(GREEN, 64);
	return (struct handoff){ .kernel = kernel, .dtb = dtb };
}
