# Series 8 — arm64: dts: qcom: Samsung Galaxy Tab S7+ 5G

Readiness: **needs work; blocked on the bindings of series 2, 4, 5 and 6**. Send last.

## Patches

| # | Subject | Source | Files |
|---|---|---|---|
| 1 | `dt-bindings: arm: qcom: Add Samsung Galaxy Tab S7+ 5G` | binding part of 78dfd9767 | `Documentation/devicetree/bindings/arm/qcom.yaml` |
| 2 | `arm64: dts: qcom: Add Samsung Galaxy Tab S7+ 5G` | all 18 DTS commits folded | `arch/arm64/boot/dts/qcom/{Makefile,sm8250-samsung-gts7xl.dts}` |

A new board goes in as one DTS patch; the 18 incremental bring-up commits are folded.

## Checks

- checkpatch --strict: `LONG_LINE_COMMENT` (header comment, 106 columns),
  `FILE_PATH_CHANGES` (MAINTAINERS), placeholder sign-off.
- dt_binding_check `arm/qcom.yaml`: clean.
- `make CHECK_DTBS=y qcom/sm8250-samsung-gts7xl.dtb` (dtschema 2026.9):
  `framebuffer@9c000000 (simple-framebuffer): 'required-opps' does not match any of the
  regexes` — the only warning.
- `make W=1` dtc: no warning from the board file.

## Recipients

- To: Bjorn Andersson <andersson@kernel.org>, Konrad Dybcio <konradybcio@kernel.org>; for
  patch 1 Rob Herring, Krzysztof Kozlowski, Conor Dooley
- Cc: linux-arm-msm@vger.kernel.org, devicetree@vger.kernel.org, linux-kernel@vger.kernel.org
  (Kees Cook / Tony Luck / G. Piccoli are listed because of the ramoops node; optional)
- Tree: qcom (`qcom/linux.git` `arm64-for-<next>`).

## Cover letter draft

```
Subject: [PATCH 0/2] arm64: dts: qcom: Add Samsung Galaxy Tab S7+ 5G

Add initial support for the Samsung Galaxy Tab S7+ 5G (SM-T976B,
gts7xl), an SM8250 tablet with a 12.4" 2800x1752 120 Hz OLED panel.

Working: UFS, USB 2.0 peripheral, volume and power keys, ramoops,
display (S6TUUM3, DSC, command mode, 120 Hz), touchscreen (FTS1BA90A),
Adreno 650 (freedreno), Wi-Fi and Bluetooth (QCA6390), MAX77705
charger and fuel gauge, four CS35L41 speaker amplifiers through the
ADSP.

Not described yet: cameras, sensors hub, microphones, USB host and
Type-C role switching, the PCA9468 direct charger, the modem.

Dependencies (bindings in flight):
- display panel: <lore link of series 4>
- touchscreen:   <lore link of series 5>
- GPI EE offset: <lore link of series 2b>
- MAX77705 charger properties: <lore link of series 6>

The bootloader only accepts DTBs with Samsung's qcom,msm-id and
qcom,board-id values, which are included.

<OWNER NAME>
```

## Must fix before sending

1. **Dependencies.** The DTS uses `samsung,s6tuum3-amsa24vu01`, `st,fts1ba90a`,
   `qcom,gpi-ee-offset` and the new MAX77705 properties. Options: wait for the bindings to be
   in linux-next, or send a first DTS without the nodes that need unmerged bindings (no
   `qcom,gpi-ee-offset` means no GPI for touch and speakers, so touch, speakers and the
   charger monitor would come in follow-up patches) and add them later.
2. **Boot framebuffer holds** (from 5954f55b7): `simple-framebuffer` with `power-domains`
   (MMCX + MDSS GDSC), `required-opps` and two DSI supplies, to stop sync_state from cutting
   the display before the MSM driver binds. `required-opps` fails the schema. Either drop the
   holds (and check the handover still works without `pd_ignore_unused`), or propose a
   simple-framebuffer binding change with the reason. Upstream reviewers generally prefer
   fixing sync_state ordering over DT workarounds; expect discussion.
3. **Kernel command line hacks** used on the device today are not part of the DTS but the
   DTS must not depend on them: `clk_ignore_unused`, `pd_ignore_unused`,
   `regulator_ignore_unused`, `cpuidle.off=1`. Boot the submitted DTS without all four and fix
   what breaks (missing consumers, idle states) before sending.
4. Comments describing local workarounds must go or be rewritten as hardware facts: the MUIC
   comment that says the initramfs switches the USB data lines through `/dev/i2c-N`, the
   "r7/r9 image" history in comments, the stock-tree file references.
5. Header comment: wrap at 100 columns; drop "Bring-up tree" wording.
6. Signed firmware (`a650_zap.mbn`, `adsp.mbn`) is loaded from
   `qcom/sm8250/samsung/gts7xl/`: standard practice for phones, but say in the message that the
   files are Samsung-signed and not in linux-firmware.
7. `qcom,board-id` lists eight board IDs; keep only those the bootloader actually needs, and
   check that `arm/qcom.yaml` allows msm-id/board-id for this compatible (dtbs_check passed
   tonight, re-check on next).
8. `regulator-always-on` on L5C (antenna switch, no consumer): acceptable, keep the comment.
9. No `MAINTAINERS` entry is needed for a single board DTS (the qcom entry covers it); ignore that
   checkpatch warning.
10. Rebase on the qcom `arm64-for-next` branch; run `make CHECK_DTBS=y W=1` again; check the
    DTS sorting rules (`Documentation/devicetree/bindings/dts-coding-style.rst`: nodes ordered
    by address, `&label` overrides alphabetical) — not checked tonight.
