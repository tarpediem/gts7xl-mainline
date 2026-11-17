# Series 4 — drm/panel: Samsung S6TUUM3 AMSA24VU01

Readiness: **needs work (small)**. Closest to ready of the new drivers.

## Patches

| # | Subject | Source | Files |
|---|---|---|---|
| 1 | `dt-bindings: display: panel: Add Samsung S6TUUM3 AMSA24VU01` | binding part of 929788b3b | `Documentation/devicetree/bindings/display/panel/samsung,s6tuum3-amsa24vu01.yaml` |
| 2 | `drm/panel: Add Samsung S6TUUM3 AMSA24VU01 panel driver` | 929788b3b + f1ca9badd (folded) | `drivers/gpu/drm/panel/{Kconfig,Makefile,panel-samsung-s6tuum3.c}` |

## Checks

- checkpatch --strict on 2: `BLOCK_COMMENT_STYLE` (1), `MSLEEP` < 20 ms (2),
  `PARENTHESIS_ALIGNMENT` (1), `FILE_PATH_CHANGES` (MAINTAINERS) on both.
- dt_binding_check: clean.
- Hardware: 2800x1752 at 120 Hz in command mode with DSC, kmscube flips at 119.6-120.3 Hz,
  Hyprland and GNOME run on it.

## Recipients

- To: Neil Armstrong <neil.armstrong@linaro.org>, Jessica Zhang <jesszhan0024@gmail.com>
  (panel maintainers); for patch 1 Rob Herring, Krzysztof Kozlowski, Conor Dooley
- Cc: David Airlie, Simona Vetter, Maarten Lankhorst, Maxime Ripard, Thomas Zimmermann,
  dri-devel@lists.freedesktop.org, devicetree@vger.kernel.org, linux-kernel@vger.kernel.org,
  linux-arm-msm@vger.kernel.org (by hand)
- get_maintainer.pl also lists the owner's own address (from the binding's `maintainers:`).
- Tree: drm-misc (`drm-misc-next`).

## Cover letter draft

```
Subject: [PATCH 0/2] drm/panel: Add Samsung S6TUUM3 AMSA24VU01 panel

This adds the 2800x1752 OLED panel of the Samsung Galaxy Tab S7+ 5G
(SM-T976B, gts7xl): an S6TUUM3 DDIC behind an Anapass TCON, four DSI
lanes, command mode, DSC 1.1 with two 1400x12 slices.

The command sequences, waits and the power sequence (one module supply,
LP-11, reset, wait for TCON_RDY) follow the vendor kernel. Brightness
uses the vendor DBV table for the normal range (no HBM).

Tested on SM8250 (MSM DSI, DSC) at 120 Hz with Hyprland and GNOME. The
board DTS is sent separately to the qcom tree.

<OWNER NAME>
```

## Must do before sending

1. Replace the owner handle/address in the binding `maintainers:` and in `MODULE_AUTHOR()`.
2. Add a `MAINTAINERS` entry (binding + driver) in patch 2.
3. Fix the checkpatch items: block comment, `msleep()` < 20 ms → `usleep_range()` or
   `mipi_dsi_msleep()` in the multi-context helpers, alignment.
4. "Never fail enable" (folded f1ca9badd): a failed enable logs and returns 0 so that
   `disable()` still sends display off. Reviewers will question it; explain it in the commit
   message and in a comment, or find a cleaner way (track state, return the error, handle
   cleanup in `unprepare`).
5. The bootloader-left-running path (TCON_RDY shortcut only after our own successful enable)
   depends on the boot framebuffer handover; keep it, but describe it plainly.
6. Brightness: say where the DBV table comes from (vendor table, factual numbers) and why a
   linear 11-bit range is not used; consider exposing the 11-bit range and dropping the table.
7. Check that the compatible naming (`samsung,s6tuum3-amsa24vu01`) matches the scheme of the
   other Samsung panels in drm-misc-next.
