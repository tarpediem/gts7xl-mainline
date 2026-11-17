# Series 5 — Input: ST FTS1BA90A touchscreen

Readiness: **needs work**.

## Patches

| # | Subject | Source | Files |
|---|---|---|---|
| 1 | `dt-bindings: input: touchscreen: Add ST FTS1BA90A` | 52898455b | `Documentation/devicetree/bindings/input/touchscreen/st,fts1ba90a.yaml` |
| 2 | `Input: Add ST FTS1BA90A touchscreen driver` | 3be9c1361 + 435b40e87 (folded) | `drivers/input/touchscreen/{Kconfig,Makefile,stmfts1b.c}` |

## Checks

- checkpatch --strict: only `FILE_PATH_CHANGES` (MAINTAINERS) + placeholder sign-off.
- dt_binding_check: clean.
- Hardware: multitouch under Hyprland and GNOME, on-screen keyboards usable, input
  stopped/started with the display (power key).

## Recipients

- To: Dmitry Torokhov <dmitry.torokhov@gmail.com>; for patch 1 Rob Herring, Krzysztof
  Kozlowski, Conor Dooley
- Cc: Henrik Rydberg <rydberg@bitmath.org>, linux-input@vger.kernel.org,
  devicetree@vger.kernel.org, linux-kernel@vger.kernel.org
- get_maintainer.pl also adds Maxime Coquelin, Alexandre Torgue, linux-stm32 and
  linux-arm-kernel (keyword match on the `st,` prefix, STM32 entry): **drop them**, they
  are not related. It also lists the owner's address (binding `maintainers:`).
- Tree: input (`dtor/input.git` next).

## Cover letter draft

```
Subject: [PATCH 0/2] Input: Add ST FTS1BA90A touchscreen driver

The ST FingerTip FTS1BA90A is the touch controller of the Samsung
Galaxy Tab S7+ (SM8250). Its protocol differs from the controllers
handled by the existing stmfts driver: 16-byte events read with the
0x60/0x61 commands, other command set for reset, scan and system info,
and a ready event after reset. This series adds a minimal driver based
on the protocol of the Samsung vendor driver: power-up, reset, chip and
firmware ID, scan on/off around open/close and system sleep, multitouch
events. The firmware in the IC is used as is: nothing is flashed,
configured or calibrated.

<OWNER NAME>
```

## Must do before sending

1. **Separate driver vs. stmfts**: Dmitry will ask whether this can extend `stmfts.c`. Write
   the comparison (command set, event format, init sequence) in the cover letter; search lore
   for any existing FTS5 / FTM5 / fts1ba90a work and reuse it if there is one.
2. Copyright/credit: the driver's protocol knowledge comes from the GPL vendor driver;
   state it in the header comment and the commit message.
3. Replace the owner handle/address in the binding `maintainers:`; add a `MAINTAINERS` entry.
4. Supplies are never switched off (the 1.8 V rail is shared with the display on this
   board): fine as a board fact, but the driver should still use regulator APIs normally
   (enable/disable balanced) and let the shared regulator stay on; reviewers dislike
   board-specific assumptions in a generic driver.
5. Asynchronous probe and bounded polls (folded 435b40e87): keep, mention.
6. Name: file `stmfts1b.c` vs compatible `st,fts1ba90a` vs Kconfig `TOUCHSCREEN_STMFTS1B`;
   align on one name.
