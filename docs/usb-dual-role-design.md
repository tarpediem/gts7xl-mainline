# USB dual role (host with a hub) on the gts7xl: design (nothing implemented, nothing tested)

Goal: plug a USB hub / keyboard / drive into the USB-C port and have the tablet act as host,
powering unpowered devices; keep USB device mode (gadget networking, the debug shell's link)
as the default whenever a PC or charger is attached.

## What is there today

- dwc3 (`usb_1`, `usb_1_dwc3`, 0xa600000) runs in device mode only (board DTS), HS PHY only.
- The MAX77705 has three blocks on i2c0: charger (0x69, driven by our mainline charger driver
  with the safety monitor), fuel gauge (0x36), and the **USB-C/PD controller with its own
  firmware** (0x25: "MUIC"/CCIC). Mainline has no driver for that USB-C block; the initramfs
  hook and the charger's BC1.2 read (BC_STATUS, 0x08) use it read-only.
- Vendor kernel (`drivers/ccic/max77705_cc.c`, `max77705_usbc.c`, `drivers/battery_v2/max77705_charger.c`):
  - CC_STATUS0 (0x0A) bits 2:0 `CCStat`: 0 no connection, 1 SINK (the tablet is the sink: a
    PC or charger is the source → device role), 2 SOURCE (a sink is attached: hub, OTG
    adapter, keyboard → the tablet must be host and provide VBUS), 3 audio, 4 debug accessory.
    Interrupt CCStatI (bit 0 of the CC interrupt register) on every change.
  - On SOURCE the vendor turns VBUS on (`max77705_vbus_turn_on_ctrl` → charger "OTG on"):
    CHG_CNFG_02 OTG_ILIM = 900 mA (`MAX77705_OTG_ILIM_900`, field values 500/900/1200/1500 mA),
    CHG_CNFG_00 MODE = 0xA `BOOST_OTG_ON` (from 0x4/0x5 buck/charge), CHG and CHGIN interrupts
    masked while boosting; on detach: back to the previous mode, interrupts restored.
  - It never boosts while CHGIN has a valid input (the modes are exclusive: buck = charger in,
    boost = power out).

## Plan, in steps (each one a separate commit and test, the boost step only with the owner)

1. **Manual role switch (no VBUS).** DTS: `dr_mode = "otg"` + `usb-role-switch` on
   `usb_1_dwc3`, default role device; check `/sys/class/usb_role/a600000.usb-role-switch/role`
   (`host` / `device` / `none`). Test with a **self-powered** hub (or a hub on a power supply):
   `echo host > …/role`, lsusb, keyboard; `echo device` brings gadget networking back.
   Risk: none for the power path. The debug link drops while in host mode (USB is single port).
2. **Automatic role from the USB-C controller (read-only).** A small mainline driver
   `max77705-usbc` (MFD cell or i2c client 0x25 already claimed? no: today unclaimed) that reads
   CC_STATUS0 on its interrupt and is a `usb_role_switch` *consumer*: SINK → device,
   SOURCE → host, none → device (default). No writes to the USB-C firmware, no PD.
   The initramfs MUIC hook must keep working (it switches the data lines; to re-check).
3. **VBUS out (OTG boost) — owner present, charger knowledge needed.** A `vbus` regulator in
   the max77705 charger driver, used by the role logic: enable = OTG_ILIM 900 mA (stock), MODE 0xA;
   the safety monitor must know about it (no charging, no CHGIN rewrite, watchdog handling while
   boosting). Hard interlocks, all re-checked before and every few seconds during boost:
   - never enable if CHGIN is valid / BC_STATUS reports VBUS from outside / CCStat ≠ SOURCE;
   - battery temperature inside the window and capacity above a floor (e.g. 15 %);
   - disable on CCStat change, on OVP/OCP/overcurrent interrupt, on driver unbind, on shutdown;
   - read back MODE after every write; any I2C error = boost off.
   Test plan: a USB keyboard first (≪ 100 mA), then a bus-powered hub; measure battery current
   and temperature; then unplug/replug a PC and a charger to prove the interlocks.

Defaults stay as today: device mode, gadget networking, no VBUS, until each step passes.
Questions for the owner: which hub (self-powered or not) and devices; acceptable battery floor
for OTG.
