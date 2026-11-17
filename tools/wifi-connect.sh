#!/usr/bin/env bash
# Connect the tablet (pmOS debug shell over USB) to a WPA2/WPA3 personal Wi-Fi network.
# The passphrase is typed here, hidden. It goes only into a RAM file on the tablet
# (/tmp is tmpfs) and a /dev/shm temp file here, shredded on exit.
# Needs wpa_supplicant unpacked in /tmp/w on the tablet (see NOTES.md).
set -euo pipefail
cd "$(dirname "$0")/.."

read -rp "Wi-Fi network name (SSID): " ssid
read -rsp "Wi-Fi password: " pass; echo

tmp=$(mktemp -p /dev/shm wpa.XXXXXX)
trap 'shred -u "$tmp" 2>/dev/null || rm -f "$tmp"' EXIT
SSID="$ssid" PASS="$pass" python3 - "$tmp" <<'EOF'
import hashlib, os, sys
ssid, pw = os.environ["SSID"].encode(), os.environ["PASS"].encode()
if not 8 <= len(pw) <= 63:
    sys.exit("password must be 8 to 63 characters")
if b'"' in pw or b"\n" in pw:
    sys.exit("password with a double quote or newline is not supported here")
psk = hashlib.pbkdf2_hmac("sha1", pw, ssid, 4096, 32).hex()
with open(sys.argv[1], "w") as f:
    f.write("ctrl_interface=/tmp/wpa_ctrl\nsae_pwe=2\n"
            f"network={{\n\tssid={ssid.hex()}\n\tpsk={psk}\n\tkey_mgmt=WPA-PSK\n}}\n"
            f"network={{\n\tssid={ssid.hex()}\n\tsae_password=\"{pw.decode()}\"\n"
            "\tkey_mgmt=SAE\n\tieee80211w=2\n}\n")
EOF
unset pass

echo "Sending the key to the tablet..."
python3 tools/usbsh.py --timeout 60 push "$tmp" /tmp/wpa.conf >/dev/null
echo "Connecting (up to a minute)..."
python3 tools/usbsh.py --timeout 90 run '
chmod 600 /tmp/wpa.conf
export LD_LIBRARY_PATH=/tmp/w/lib
killall wpa_supplicant udhcpc 2>/dev/null; sleep 1
ip link set wlan0 up
/tmp/w/wpa_supplicant -B -i wlan0 -c /tmp/wpa.conf -D nl80211 >/dev/null
for i in $(seq 1 25); do iw dev wlan0 link | grep -q Connected && break; sleep 1; done
iw dev wlan0 link | grep -E "Connected|signal|tx bitrate" | sed "s/Connected to .*/Connected/"
printf "%s\n" "#!/bin/sh" "[ \"\$1\" = bound ] || exit 0" "ip addr add \$ip/\${mask:-24} dev \$interface" "ip route add default via \${router%% *} dev \$interface" "rm -f /etc/resolv.conf; for d in \$dns; do echo nameserver \$d >> /etc/resolv.conf; done" > /tmp/udhcpc.sh
chmod +x /tmp/udhcpc.sh
udhcpc -i wlan0 -q -n -t 8 -s /tmp/udhcpc.sh >/dev/null 2>&1 && echo "DHCP OK" || echo "DHCP failed"
ip -4 addr show wlan0 | grep -oE "inet [0-9.]+/[0-9]+"
ping -c 3 -W 2 1.1.1.1 | tail -1
' 2>&1 | grep -vE "^(~ #|$)"
echo "Done. The tablet keeps the connection until reboot or kexec."
