#!/bin/sh
# Write the factory speaker calibration of the four CS35L41 into their protection firmware.
# Run as root on the tablet, WHILE the amplifiers' DSP runs (PCM Source = DSP, a stream
# playing): the calibration controls are volatile, the driver refuses them otherwise.
#
# usage: gts7xl-amp-cal.sh [--dry-run] [SEC_EFS_DEVICE]   (default /dev/disk/by-partlabel/sec_efs)
#
# Source: the stock factory calibration in the sec_efs partition, /cirrus/<kind>_cal<suffix>
# (ASCII decimal, written by Samsung's cirrus-cal driver), read with debugfs: read only, the
# partition is never mounted. Values stay on the device; nothing is stored here.
# Suffixes from the stock DT (cirrus,mfd-suffix): "" = 0x41 Top Left, "_r" = 0x40 Bottom Left,
# "_b" = 0x43 Top Right, "_br" = 0x42 Bottom Right. temp_cal is shared.
# What is written, as the stock driver does (cirrus_cal_apply): CAL_R = rdc, CAL_AMBIENT = temp,
# CAL_STATUS = 1, CAL_CHECKSUM = rdc + 1, VIMON_CAL = 2 (valid) with VSC/ISC, or 1 if missing.
set -eu
dry=0
[ "${1:-}" = --dry-run ] && { dry=1; shift; }
dev=${1:-/dev/disk/by-partlabel/sec_efs}
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT

rd() { # rd NAME -> decimal value or empty
	debugfs -R "dump /cirrus/$1 $tmp/$1" "$dev" >/dev/null 2>&1 || true
	[ -s "$tmp/$1" ] && tr -cd '0-9' < "$tmp/$1" || true
}
be() { # be N -> amixer BYTES value, big-endian 4 bytes
	printf '0x%02x,0x%02x,0x%02x,0x%02x' $(( ($1 >> 24) & 255 )) $(( ($1 >> 16) & 255 )) \
		$(( ($1 >> 8) & 255 )) $(( $1 & 255 ))
}
set_ctl() { # set_ctl PREFIX "ALG NAME" VALUE
	if [ $dry = 1 ]; then echo "would set '$1 DSP1 Protection $2' = $3"
	else amixer -q -c0 cset name="$1 DSP1 Protection $2" "$(be "$3")"; fi
}

temp=$(rd temp_cal); [ -n "$temp" ] || temp=23   # stock default ambient
for map in ":Top Left" "_r:Bottom Left" "_b:Top Right" "_br:Bottom Right"; do
	sfx=${map%%:*} p=${map#*:}
	rdc=$(rd "rdc_cal$sfx"); vsc=$(rd "vsc_cal$sfx"); isc=$(rd "isc_cal$sfx")
	[ -n "$rdc" ] || rdc=8580                        # stock default (CS34L40_CAL_RDC_DEFAULT)
	vimon=2; { [ -n "$vsc" ] && [ -n "$isc" ]; } || { vimon=1; vsc=0; isc=0; }
	echo "$p: rdc $rdc ($(( rdc * 292857 / 50000 / 8192 )).x ohm approx), ambient $temp C, vimon $vimon"
	set_ctl "$p" "cd CAL_R" "$rdc"
	set_ctl "$p" "cd CAL_AMBIENT" "$temp"
	set_ctl "$p" "cd CAL_STATUS" 1
	set_ctl "$p" "cd CAL_CHECKSUM" $(( rdc + 1 ))
	set_ctl "$p" "400a4 VIMON_CAL" "$vimon"
	set_ctl "$p" "400a4 VSC" "$vsc"
	set_ctl "$p" "400a4 ISC" "$isc"
done
