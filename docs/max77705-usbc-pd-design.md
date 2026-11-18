# MAX77705 USB-C / PD controller in mainline: study and design (no code yet)

Scope: the USB-C block of the MAX77705 (I2C 0x25 on i2c0, "MUIC"/"CCIC" in the vendor kernel),
which runs its own firmware (Type-C state machine, BC1.2, USB-PD policy engine, VDM engine).
Goals, in order: (1) source role so OTG adapters/hubs are detected and powered (r25 needs it),
(2) cleaner roles (typec class port instead of polling in the charger driver), (3) 9 V PD
charging, (4) DisplayPort Alt Mode (HDMI adapters).
Sources: vendor kernel `drivers/ccic/max77705_{usbc,cc,pd,alternate}.c`,
`include/linux/ccic/max77705*.h` (droidian-gts7xl tree), stock DT (reference/), our r23-r25
measurements, mainline `drivers/soc/qcom/pmic_glink_altmode.c`,
`drivers/gpu/drm/bridge/aux-hpd-bridge.c`, `drivers/usb/typec/`.

**Nothing in this document has been written to the chip.** Every write is listed in
section 5 with a tag **[OWNER APPROVAL]**.

## 1. What we know from the hardware (r23-r25, read only)

| Register (0x25) | Name | Seen |
|---|---|---|
| 0x00 / 0x01 / 0x09 | HW rev / FW rev / FW minor | 0x1a / 0x52 / 0x28 |
| 0x06 / 0x07 | USBC_STATUS1 (VBUS ADC 7:4, UID ADC 2:0) / STATUS2 (SYSMsg) | |
| 0x08 | BC_STATUS: 7 VBUSDet, 5:3 PrChgTyp, 2 DCDTmo, 1:0 ChgTyp | 0x8b wall charger, 0x81 PC |
| 0x0A | CC_STATUS0: 7:6 CCPinStat (CC1/CC2), 5:4 CCIStat (Rp level), 3 CCVcnStat, 2:0 CCStat | 0x71 wall charger (CC1, Rp 3 A, sink); **0x40 with an OTG adapter: CC1 seen, CCStat 0** |
| 0x0B | CC_STATUS1: 7:6 CC/SBU short, 5 VCONN OCP, 4 VCONN SC, 3 vSafe0V, 2 AttachSrcErr, 1 ConnStat (water), 0 Altmode | 0x00 |
| 0x0C / 0x0D | PD_STATUS0 (PDMsg) / PD_STATUS1 (7 data role, 4 PS_RDY, 3:0 FCT_ID) | 0x01 / 0x57 with the PD charger (no contract requested by us) |
| 0x02..0x05 | UIC_INT, CC_INT, PD_INT, VDM_INT (read to clear) | never read by us |
| 0x0E..0x11 | the four interrupt masks | never written by us |
| 0x21..0x41 | mailbox out: 0x21 opcode, 0x22.. data, 0x41 = 0 ends a short command | written once per boot by the initramfs MUIC hook (CTRL1_W COM_USB) |
| 0x51..0x60 | mailbox in: echo of the opcode + answer, valid after UIC_INT APCmdResI (bit 7) | never read |

The PMIC's top interrupt has a USBC source (mainline `MAX77705_SRC_IRQ_USBC`), so an
interrupt-driven driver is possible; until then everything can be polled.

Finding (r25 hands-on): with an OTG adapter the firmware sees a pin (CCPinStat CC1) but never
attaches as source (CCStat stays 0). Stock configures the firmware at boot through the mailbox;
we never did. That is the first thing to fix.

## 2. The mailbox protocol (vendor max77705_usbc.c)

- **Command**: bulk write `[0x21] = opcode, [0x22..] = data` (up to 32 data bytes); if
  shorter than 32 bytes, write `[0x41] = 0x00` (end). One command at a time: the vendor
  queues them and waits for the answer (timeout 3 s, `OPCODE_WAIT_TIMEOUT`).
- **Answer**: UIC_INT bit 7 (APCmdResI) set, then bulk read from 0x51 (`opcode, data...`);
  the first byte must echo the opcode.
- **Recovery**: after a firmware reset (SYSMsg in USBC_STATUS2) the vendor replays
  CCCTRL1_W, FACTORY_TEST (auto VBUS) and SET_ALTERNATEMODE (`max77705_recover_opcode`).

Opcodes that matter here (from `max77705_opcode_list`):

| Opcode | Name | Use |
|---|---|---|
| 0x05/0x06 | CTRL1 R/W | USB switch: 0x09 COM_USB (our initramfs hook already writes it) |
| 0x07/0x08, 0x09/0x0A | CTRL2, CTRL3 R/W | misc control (CTRL3: lock-error enable) |
| 0x0B/0x0C | CCCTRL1 R/W | 7 CCSrcCurCh, 6:5 CCSrcCur (Rp we advertise), 4 CCSrcSnk, 3 CCSnkSrc (try roles), 2 CCDbgEn, 1 CCAudEn, 0 CCDetEn |
| 0x0D/0x0E, 0x0F/0x10 | CCCTRL2, CCCTRL3 R/W | (CCCTRL2 written by the vendor for SBU/water handling) |
| 0x15/0x16 | CHGIN_ILIM R/W | the firmware writes the charger's input limit itself ("AutoIBUS") |
| 0x2E | SET_SNKCAP | our sink capabilities (stock DT `battery,snkcap_data`) |
| 0x30 | CURRENT_SRCCAP | read the source's PDO list (31 bytes) |
| 0x32 | SRCCAP_REQUEST | request PDO n (1 byte) |
| 0x37/0x38 | SWAP_REQUEST / response | PR/DR/VCONN swap |
| 0x48 / 0x4B | VDM SET_VDM_REQ / GET_VDM_RESP | DP: discover, enter, status, configure (pin assignment) |
| 0x54 | SAMSUNG_FACTORY_TEST | data 0x02 = firmware "auto VBUS" on, 0x00 = off (VBUS from the AP) |
| 0x55 | SET_ALTERNATEMODE | 0x01 SRCCAP, 0x02 VDM, 0x03 SRC + VDM (stock at boot: 0x03) |
| 0x57 | SAMSUNG_FW_AUTOIBUS | 0x00 fw + auto on, 0x01 fw on / auto off (stock), 0x02, 0x03 |

### What stock sends at boot (`max77705_init_opcode` + probe)

1. interrupt masks: UIC_INT_M 0x04, CC_INT_M 0x20, PD_INT_M 0x00, VDM_INT_M 0xF0 (direct
   register writes 0x0E..0x11);
2. `FACTORY_TEST 0x00`: firmware auto VBUS **off** (the AP decides VBUS, via the charger's
   OTG boost) — `max77705_usbc_disable_auto_vbus`;
3. `CCCTRL1_W` with CCAudEn/CCDbgEn only if audio accessories are supported (not on this
   tablet: `audio,no-earjack`);
4. `SET_ALTERNATEMODE 0x03` (SRC + VDM) once the alternate-mode framework is "ready"
   (`max77705_set_enable_alternate_mode(ALTERNATE_MODE_START)`); 0x01 when stopped;
5. from the battery side: `FW_AUTOIBUS 0x01` (firmware input-limit control on, automatic
   changes off), `SET_SNKCAP` with the stock sink capabilities.

Our reading (to verify, see E1-E3): the firmware boots sink-only / without source
capability until (4); stock's OTG and DP both depend on it. Before (4) the auto-VBUS state
must be known: with firmware auto VBUS on, the firmware could switch the boost on by itself,
bypassing our charger interlocks. So (2) always comes before (4).

## 3. Mainline architecture

A new driver `drivers/usb/typec/maxim/max77705_usbc.c` (I2C client 0x25, DT node
`usb-c@25` under i2c0 with a `connector` child, `usb-c-connector` binding). Not TCPM: the
firmware runs the policy engine, the driver is a thin port driver like `pmic_glink_altmode` /
`ucsi`. It replaces the polling in the charger driver (r25) and the BC_STATUS/CC_STATUS
reads there (the charger gets cable type, Rp level and PD contract through a power_supply
supplier or a small notifier).

- **typec port**: `typec_register_port` (DRP, data DRD, try-SNK as stock), partner on
  CCStat attach, `typec_set_pwr_role / data_role / orientation` from CCStat and CCPinStat,
  `typec_set_pwr_opmode` from CCIStat (default / 1.5 A / 3 A) and PD contract.
- **USB role**: `usb_role_switch` consumer (dwc3, already a role switch in r25): SOURCE ->
  host, SINK -> device, PD DR_swap -> as reported by PD_STATUS1 bit 7.
- **VBUS out**: regulator from the charger driver (`vbus` regulator, boost with every r25
  interlock in its enable/monitor path); the typec driver enables it on a source attach
  (firmware auto VBUS off).
- **Orientation / mode switch**: `typec_switch` + `typec_mux` towards the QMP USB/DP
  combo PHY (`usb_1_qmpphy`, `orientation-switch` already in sm8250.dtsi; enable it, add
  `mode-switch`; it also brings USB 3 back, we run HS only today).
- **DisplayPort Alt Mode**: `typec_port_register_altmode` (SVID 0xff01). The firmware runs
  Discover Identity/SVIDs/Modes and Enter Mode once SET_ALTERNATEMODE has VDM enabled; the
  driver gets DP Status / Attention through VDM_INT + GET_VDM_RESP, picks the pin assignment
  (C or E for 4 lanes, D for 2 lanes + USB, vendor `max77705_vdm_dp_select_pin`) and sends
  DP Configure (SET_VDM_REQ). HPD: `drm_aux_hpd_bridge_register` on the connector, and
  `drm_aux_hpd_bridge_notify(connected/disconnected)` on HPD state and IRQ_HPD (as
  pmic_glink_altmode does). DTS: enable `mdss_dp`, `mdss_dp_out` endpoint to the USB-C
  connector graph, QMP PHY in DP mode; the panel (DSI) is untouched.
- **PD sink**: power_supply `max77705-usbc` (type USB_PD) exporting the PDO list and the
  contract; PDO selection policy in the kernel driver (fixed PDOs only, see 4).

## 4. 9 V PD charging: safety plan

Stock values: `battery,max_input_voltage` 9000 mV, `pd_charging_charge_power` 15000 mW,
`max_input_current` 3000 mA, `chg_high_temp` 80.0 C (recovery 77.0 C) with
`chg_input_limit_current` 1000 mA / `chg_charging_limit_current` 1500 mA above it.

- Only fixed PDOs, 5 V or 9 V; never above 9 V (stock), no PPS/APDO (that is the direct
  charger, PCA9468, which stays disabled).
- Input limit at 9 V = min(PDO current, 15 W / 9 V = 1666 mA -> 1650 mA), written and
  verified **before** the 9 V request (it is lower than the 5 V limits we use), and the
  safety monitor's reference follows the contract (as for the cable type, r23/r24).
- Charge current unchanged at first (1500 mA on DCP/PD); raising it is a separate decision,
  never above stock (2100 mA TA, 3150 mA max).
- Preconditions for the request: safety monitor running, battery inside 2..41 C, charger
  thermistor (chg_therm, r24) below 77 C, PD contract at 5 V established (PS_RDY), no fault.
- During: VBUS check from USBC_STATUS1 VBADC and CHGIN_DTLS valid; charger thermistor at or
  above 80 C -> input 1000 mA / charge 1500 mA (stock), and back to the 5 V PDO; any
  detach, hard reset, unreadable status or mismatch -> charging off by the monitor, 5 V PDO.
- AutoIBUS: `FW_AUTOIBUS 0x01` as stock so the firmware does not change the charger's input
  limit on its own; our "at or under the reference" check stays as the second line (it
  rewrites any higher value).
- The 9 V request is off by default (sysfs or DT switch), like the VBUS output.

## 5. Writes needed, in the order they would be tried

Each one **[OWNER APPROVAL]** before it is sent; each experiment kexec-tested, logged, and
reverted by a reboot (the firmware state does not survive a PMIC reset; to confirm in E1).

| # | Write | Purpose | Risk |
|---|---|---|---|
| E1 | mailbox read commands: CCCTRL1_R 0x0B, CCCTRL2_R 0x0D, CCCTRL3_R 0x0F, CTRL1_R 0x05, CTRL3_R 0x09 (write opcode to 0x21 + 0x41 = 0, read 0x51..) | dump the current firmware configuration | low: read opcodes, but they are writes to the mailbox and the hook's CTRL1_W shares it |
| E2 | `FACTORY_TEST` (0x54) data 0x00 | firmware auto VBUS off (stock boot state) | low; required before E3 |
| E3 | `SET_ALTERNATEMODE` (0x55) data 0x01, then 0x03 | enable source role (OTG detection), then VDM | medium: the tablet may present Rp and attach as source; VBUS must stay off (checked: BC_STATUS VBUSDet 0 with the adapter) |
| E4 | interrupt masks 0x0E..0x11 as stock (0x04, 0x20, 0x00, 0xF0) | interrupt-driven driver | low |
| E5 | `CCCTRL1_W` | only if E1/E3 show detection disabled | medium |
| E6 | `FW_AUTOIBUS` (0x57) 0x01, `SET_SNKCAP` (0x2E) stock data | PD sink setup as stock | medium (input limit owner changes) |
| E7 | `SRCCAP_REQUEST` (0x32) PDO 2 (9 V) | 9 V charging | **high**: input voltage; only with section 4 in place |
| E8 | `SET_VDM_REQ` (0x48) DP Configure | DisplayPort Alt Mode | low for power, needs the DTS/DP work |
| — | `CHGIN_ILIM_W` (0x16), firmware update, `RAM_TEST`, `GRL_COMMAND`, GPIO5 | not used | never sent |

After E1-E3 the r25 VBUS output can be tested as planned (owner with the OTG adapter and a
keyboard): source attach -> host role -> boost with every interlock.

## 6. Order of work

1. E1 (read only on the firmware side) and E2-E3 by hand under kexec, owner present for E3
   with the OTG adapter: does CCStat become SOURCE, is VBUS still off.
2. If yes: r26 = boot-time E2+E3 in the charger driver's USB-C code (minimal, replayed after a
   firmware reset), r25's boost test with the owner.
3. The typec port driver (section 3) taking over roles, orientation, Rp, VBUS; charger
   driver's polling removed.
4. QMP combo PHY + USB 3, then DP Alt Mode (adapter needed: owner's HDMI adapter).
5. PD 9 V (section 4), off by default, tested with the owner's PD charger.

## 7. E1-E3 test plan (approved by the owner, to run after his Waydroid test)

Script: `tools/usbc-mailbox-test.sh build/otg-r25/linux-samsung-gts7xl-7.3.4-r25.apk`, owner steps
answered one line each on stdin (the agent feeds them from the coordinator's relay). Takes the
tablet lock, battery >= 20 %, starts from BOOT (r24).

1. Owner: nothing plugged. E1 on r24 (configuration before any write).
2. kexec r25 (dual role; VBUS output policy checked `off`, never enabled in this test).
3. E1 again, E2 (0x54 = 0x00), VBUS watch 5 s; E3a (0x55 = 0x01), VBUS watch 10 s, E1 again.
4. Owner: plug the OTG adapter with the keyboard. Expected: CCStat 2 (SOURCE), role host,
   **VBUS still off** (BC_STATUS bit 7 = 0, CHGIN_OK = 0, CHGIN_DTLS = 0, CNFG_00 boost bit 0);
   the keyboard stays unpowered. Owner: unplug it.
5. E3b (0x55 = 0x03), adapter plugged/unplugged again with the same checks.
6. Owner: wall charger. Expected: CCStat 1 (SINK), role device, DCP, input limit and charging
   as with r24.
7. Reboot to r24, E1 again: does the firmware keep E2/E3 across a reboot (PMIC not reset)?

VBUS watch: every second, any sign of VBUS or boost while nothing should supply it ->
ABORT: E2 (auto VBUS off) is re-sent, the owner is told to unplug the adapter at once, the
script stops with the lock held (exit 4) and the tablet stays on r25 for a look.
