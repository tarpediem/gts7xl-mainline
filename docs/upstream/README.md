# Upstreaming the gts7xl kernel work — readiness (draft, 2026-11-18)

Nothing has been sent. The 32 commits of `gts7xl-linux` (branch `gts7xl`, on `v7.3.4`) were
regrouped into 8 series, one per subsystem, regenerated with `git format-patch` in a scratch
directory (not committed: they carry a placeholder identity), and checked with checkpatch
`--strict`, `dt_binding_check`, `dtbs_check` and `get_maintainer.pl`. How, and the b4 workflow:
[workflow.md](workflow.md).

Every patch needs, before anything else: the owner's identity as author and in
`Signed-off-by:` (placeholder `<OWNER NAME> <OWNER EMAIL>` today), `Assisted-by:` instead of
`Co-Authored-By:`, a rebase on the subsystem's `-next`, and a W=1 / sparse build (not run
tonight: no `bc` / `ld.lld` on the host).

| # | Series | Patches | Tree | Readiness | Main blocker |
|---|---|---|---|---|---|
| 1 | [arm64: kexec `__nocfi`](01-arm64-kexec.md) | 1 | arm64 | **Ready** after checks | Fill `Fixes:`; make sure it is not already fixed upstream |
| 2a | [gpi: reclaim GPIIs / shutdown](02-dmaengine-gpi.md) | 1 | dmaengine | Needs work | Test on another SM8250 board, shutdown ordering |
| 2b | [gpi: `qcom,gpi-ee-offset`](02-dmaengine-gpi.md) | 2 | dmaengine + DT | Needs work (**RFC**) | DT maintainers' answer on a firmware-config property |
| 3 | [pm8941-pwrkey warm reset at probe](03-input-pm8941-pwrkey.md) | 1 | input | Needs work (**RFC**) | Probably belongs in qcom-pon / reboot-mode, not the input driver |
| 4 | [drm/panel S6TUUM3](04-drm-panel-s6tuum3.md) | 2 | drm-misc | Needs work (small) | MAINTAINERS, identity, checkpatch nits, "never fail enable" |
| 5 | [Input FTS1BA90A](05-input-fts1ba90a.md) | 2 | input | Needs work | Justify a new driver vs `stmfts.c`; vendor-driver credit |
| 6a | [max77705 fixes + MFD revision](06-max77705.md) | 1 + 3-4 to extract | MFD, power-supply | Needs work, then ready | Extract the charger bug fixes from the monitor commit, add `Fixes:` |
| 6b | [max17042 OF match fallback](06-max77705.md) | 1 | power-supply | Unclear | May be dead code on the current tree (FG binds via simple-mfd-i2c) |
| 6c | [max77705 safety monitor, 80 % cap](06-max77705.md) | 3 | power-supply + DT | Needs work (**RFC**) | Policy in a driver; split the 785-line patch; name lookup |
| 6c' | [max77705 BC1.2 input limit](06-max77705.md) | 1 | power-supply | **Not upstreamable** as is | Raw SMBus reads of the unclaimed USB-C block (needs a MUIC/Type-C driver) |
| 7 | [ASoC sm8250 Primary TDM](07-asoc-qcom-sm8250.md) | 1 | ASoC | Needs work (small) | TDM slots should come from DT; check RB5 is unaffected |
| 8 | [Board DTS + qcom.yaml](08-qcom-dts.md) | 2 | qcom | Needs work, **blocked** | Bindings of 2b/4/5/6; framebuffer holds (`required-opps` fails the schema) |

Not upstreamable (stay local or in pmaports):

- the boot shim and the RECOVERY image layout (Samsung bootloader specific);
- the kernel command line used on the device: `clk_ignore_unused pd_ignore_unused
  regulator_ignore_unused cpuidle.off=1` — the submitted DTS must boot without them;
- the initramfs MUIC switch of the USB data lines through `/dev/i2c-N`;
- the BC1.2 read of the USB-C block from the charger (see 6c');
- the Samsung-signed firmware images (zap shader, ADSP) — referenced by path only, never
  redistributed;
- userspace parts (speaker-protection PipeWire filter, volume cap, UCM files): those go to
  their own projects (alsa-ucm-conf, pmaports) when ready.

## Suggested order of submission

1. **Series 1** (arm64 kexec fix, stable) — independent, smallest, good first contact.
2. **Series 6a** (charger bug fixes with `Fixes:`, MFD revision) — real bugs in an upstream
   driver, easy to review.
3. **Series 4** (panel) and **series 5** (touch) — new bindings + drivers, independent of each
   other; they unblock the useful part of the DTS.
4. **Series 2a** (GPI reclaim) and **series 2b** (EE offset, RFC) — 2b decides how the DTS
   enables GPI for touch and speakers.
5. **Series 7** (ASoC TDM) — after checking the DT-driven slot layout.
6. **Series 8** (board DTS) — once 4 and 5 are in linux-next; a first version may leave out the
   nodes that depend on 2b and 6c, added in follow-ups.
7. **Series 3** (pwrkey, RFC) and **series 6c** (safety monitor, RFC) — design discussions, can
   run in parallel at any time; 6c' waits for a MAX77705 USB-C driver.

Recipients, cover-letter drafts, checkpatch output and the must-fix list for each series are in
the per-series files.
