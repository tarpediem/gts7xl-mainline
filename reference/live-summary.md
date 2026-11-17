# Live capture from the running stock kernel (2026-11-17)

Read-only capture over `adb -s <serial> exec-out su -c …` (stock T976BXXS7DXH1
+ Magisk). Raw files in `reference/live/` (gitignored: they may hold device
serials).

## Board and DTB selection

- Bootloader picked base DTB `qcom,msm-id = <0x164 0x20001>` and overlay
  `qcom,board-id = <0x08 0x06>`; cmdline `androidboot.dtbo_idx=4`,
  `androidboot.revision=6`.
- Model: "Samsung GTS7XL PROJECT - DV Rev0.4 (board-id,6)".

## Panel

- `msm_drm.dsi_display0=ss_dsi_panel_S6TUUM3_AMSA24VU01_WQXGA`, `lcd_id=0x80141A`.
  Driver source: droidian-gts7xl/kernel_samsung_sm8250/techpack/display/msm/samsung/S6TUUM3_AMSA24VU01.

## Peripherals (bus-addr: driver)

| Bus | Device |
|---|---|
| i2c 2-0066 | max77705 (PMIC / charger / fuel gauge) |
| i2c 2-0057 | pca9468 (direct charger) |
| i2c 4-0049 | fts_touch (STM FTS touchscreen) |
| i2c 9-0056 | wacom w90xx (S Pen digitizer) |
| i2c 6-0040..0043 | 4 × cs35l41 (speaker amps) |
| i2c 7-0028 | ps5169 (USB-C DP redriver) |
| i2c 5-002a | stm32_pogo (keyboard pogo pins) |
| i2c 0-0020, 1-0020 | a96t3x6 (grip sensors) |
| i2c 3-0028 | nq-nci (NFC) |
| i2c 8-0025 | hl6111r (wireless charging receiver) |
| i2c 8-0064 | rtc6226 (FM radio) |
| spi7.0 | (unnamed; to identify) |

## reserved-memory: live vs stock base DTB

Live has 43 nodes, stock base 33. Present only live (from the board overlay or
added by the bootloader at boot) — all must be carried into the mainline DTS:

| Node | Base | Size |
|---|---|---|
| ramoops@9FA00000 | 0x9fa00000 | 0x100000 |
| hdm_region@9FB00000 | 0x9fb00000 | 0x1000 |
| sec_debug_region@0 | 0x9f000000 | 0x800000 |
| ss_plog_region@9F800000 | 0x9f800000 | 0x200000 |
| kaslr_region@A0001000 | 0xa0001000 | 0x1000 |
| tima_region@B0100000 | 0xb0100000 | 0x100000 |
| rkp_region@B0200000 | 0xb0200000 | 0x200000 |
| uh_heap_region | 0xb0400000 | 0x1800000 |
| camera_mem_region | dynamic | 0x40000000 (size only) |
| sec_debug_rdx_bootdev@0 | 0x1_00000000 | 0xad00000 |
