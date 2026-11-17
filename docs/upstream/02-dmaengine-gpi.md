# Series 2 — dmaengine: qcom: gpi (EE offset from DT, reclaim after kexec)

Readiness: **needs work**. Send as two separate submissions:

- 2a `Reclaim GPIIs left allocated and tear down on shutdown`: a generic robustness fix
  (kexec, and any firmware that leaves a GPII allocated). Plain patch, after more testing.
- 2b `qcom,gpi-ee-offset` binding + driver: **RFC**, because it is a design question for the DT
  maintainers.

## Patches

| # | Subject | Source | Files |
|---|---|---|---|
| 1 | `dt-bindings: dma: qcom,gpi: add qcom,gpi-ee-offset` (capitalise: `Add`) | 3a840e785 | `Documentation/devicetree/bindings/dma/qcom,gpi.yaml` |
| 2 | `dmaengine: qcom: gpi: Allow the DT to override the EE offset` | 6f1496ab8 | `drivers/dma/qcom/gpi.c` |
| 3 | `dmaengine: qcom: gpi: Reclaim GPIIs left allocated and tear down on shutdown` | c99d858fc | `drivers/dma/qcom/gpi.c` |

## Checks

- checkpatch --strict: clean except the placeholder sign-off.
- dt_binding_check `dma/qcom,gpi.yaml`: clean.
- Hardware: QUPv3_0 (touch, i2c5) and QUPv3_1 (speakers, i2c11) work only with offsets 0x1000
  and 0x6000; without them every GPI command times out. The reclaim path is exercised on
  every kexec.

## Recipients

- To: Vinod Koul <vkoul@kernel.org> (dmaengine); for patch 1 also Rob Herring
  <robh@kernel.org>, Krzysztof Kozlowski <krzk+dt@kernel.org>, Conor Dooley
  <conor+dt@kernel.org>
- Cc: Frank Li <Frank.Li@kernel.org>, linux-arm-msm@vger.kernel.org, dmaengine@vger.kernel.org,
  devicetree@vger.kernel.org, linux-kernel@vger.kernel.org; Bjorn Andersson and Konrad Dybcio
  (qcom) are worth adding by hand.
- Tree: dmaengine (`vkoul/dmaengine.git` next).

## Cover letter draft (2b, RFC)

```
Subject: [RFC PATCH 0/2] dmaengine: qcom: gpi: Allow the EE offset to come from DT

On the Samsung Galaxy Tab S7+ (SM8250) the GSI is partitioned between
execution environments differently from the SoC default: the stock
kernel uses an EE offset of 0x1000 for QUPv3_0 and 0x6000 for QUPv3_1
and QUPv3_2, while the sm8250 match data has 0. With 0, every GPI
command times out ("EV ALLOCATE completion timeout") and the serial
engines that the firmware set to GSI mode cannot be used.

The offset is set by the firmware of the board, not by the SoC, and it
differs between QUP wrappers, so it cannot come from the compatible.
This series adds an optional qcom,gpi-ee-offset property. Is a property
the right way, or would you prefer a board-specific compatible for the
GPI instances?

<OWNER NAME>
```

## Must do before sending

1. 2b: expect push-back on a vendor property describing firmware configuration. Prepare the
   evidence (stock DT values per wrapper, the timeout without it) and the alternative
   (per-board compatible). Check lore for other boards with the same problem (other Samsung
   SM8250/SM8350 devices).
2. 2b binding: say why the value cannot be derived (it is not discoverable from registers).
   Give a range or an enum of allowed values if possible.
3. 2a: test on a second SM8250 board (RB5) with and without kexec, and a normal reboot; check
   that `.shutdown` does not race with clients still holding channels (i2c/spi drivers'
   own shutdown order). Split "reclaim at probe" and "tear down on shutdown" into two patches
   if the reviewer asks; consider `Fixes:` only if a concrete bug outside kexec is shown.
4. Base on dmaengine `next`, rebuild with W=1.
