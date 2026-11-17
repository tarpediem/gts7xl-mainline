-- gts7xl (Samsung Galaxy Tab S7+ 5G) overrides for Omarchy, required last from
-- ~/.config/hypr/hyprland.lua (installed by arch/gts7xl-device).

-- Panel: DSI command mode, 2800x1752 at 120 Hz; scale 2 (validated under pmOS).
hl.monitor({ output = "DSI-1", mode = "2800x1752@120", position = "0x0", scale = 2 })
hl.env("LANG", "en_US.UTF-8")

hl.config({
  input = {
    kb_layout = "us",
    -- The touchscreen already reports in the landscape frame (kernel DT); bind it to the panel.
    touchdevice = { output = "DSI-1" },
  },
})

-- The owner's BT keyboard is QWERTY with no Super key: its left Alt acts as Super so every
-- Omarchy SUPER binding works (right Alt stays Alt).
hl.device({ name = "bt-keyboard", kb_options = "altwin:swap_lalt_lwin" })

-- On-screen keyboard: squeekboard, hidden until asked (SUPER + K, or gts7xl-osk).
o.launch_on_start("squeekboard")
o.bind("SUPER + K", "On-screen keyboard", "gts7xl-osk")

-- Power key: screen off/on (DPMS), as validated under pmOS; gts7xl-powerkey inhibits the
-- touchscreen on the same press. Replaces Omarchy's power menu on this key.
o.rebind("XF86PowerOff", "Screen off/on", "gts7xl-hypr-dpms", { locked = true })

-- Volume keys capped at 60 % (no speaker protection firmware; distortion above that).
o.rebind("XF86AudioRaiseVolume", "Volume up (max 60 %)", "gts7xl-volume raise", { locked = true, repeating = true })
o.rebind("XF86AudioLowerVolume", "Volume down", "gts7xl-volume lower", { locked = true, repeating = true })
o.rebind("XF86AudioMute", "Mute", "gts7xl-volume mute-toggle", { locked = true })
hl.unbind("ALT + XF86AudioRaiseVolume")
