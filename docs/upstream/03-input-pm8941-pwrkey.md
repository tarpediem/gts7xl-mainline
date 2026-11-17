# Series 3 — Input: pm8941-pwrkey - warm PS_HOLD reset type at probe

Readiness: **needs work, RFC**.

## Patch

| # | Subject | Source | Files |
|---|---|---|---|
| 1 | `Input: pm8941-pwrkey - set the warm PS_HOLD reset type at probe with reboot=warm` | a67de047d | `drivers/input/misc/pm8941-pwrkey.c` |

## Checks

- checkpatch --strict: clean except the placeholder sign-off.
- Hardware: dmesg `PS_HOLD reset type set to warm (reboot=warm)`; a panic restart keeps
  ramoops on this board.

## Recipients

- To: Dmitry Torokhov <dmitry.torokhov@gmail.com>
- Cc: linux-input@vger.kernel.org, linux-arm-msm@vger.kernel.org, linux-kernel@vger.kernel.org;
  Kees Cook, Tony Luck, Guilherme G. Piccoli (pstore/ramoops, matched by keyword); Bjorn
  Andersson and Konrad Dybcio by hand.
- Tree: input (`dtor/input.git` next).

## Problem statement for the message

A panic restarts through `emergency_restart()`, which skips the reboot notifiers, so the
driver never writes the PS_HOLD reset type and the PMIC keeps what the firmware left (a hard
reset here), which loses RAM and therefore ramoops.

## Must do before sending

1. Ask first whether the input driver is the right home: the PS_HOLD reset type is PMIC PON
   state, and `drivers/power/reset/qcom-pon.c` / the reboot-mode code are the more natural
   place. Reviewers may also prefer a DT property (board knows that ramoops needs warm reset)
   to parsing `reboot=warm`.
2. Check whether `reboot_mode` is readable this early and how other drivers consume it.
3. Send as `[RFC PATCH]` with the alternatives listed below the `---`.
