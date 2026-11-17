#!/bin/sh
# Silent TDM loopback test (run as the session user, PipeWire stopped):
# speakers muted (Digital PCM Volume 0 = mute, analog gain minimum), every amp's ASP TX1 = ASPRX1,
# full-scale noise played on MultiMedia1, the TDM TX slots captured on MultiMedia3.
set -x
U=/usr/share/alsa/ucm2
alsaucm -c 0 set _verb HiFi set _enadev Speaker
for p in "Top Left" "Top Right" "Bottom Left" "Bottom Right"; do
	amixer -q -c0 cset name="$p Digital PCM Volume" 0
	amixer -q -c0 cset name="$p Analog PCM Volume" 0
	amixer -q -c0 cset name="$p ASP TX1 Source" ASPRX1
	# only ASPTX1 may drive the bus: TX2-4 sit on slots 1-3 by default
	for t in 2 3 4; do amixer -q -c0 cset name="$p ASP TX$t Source" Zero; done
done
amixer -q -c0 cset name='MultiMedia3 Mixer PRIMARY_TDM_TX_0' 1
for p in "Top Left" "Top Right"; do amixer -c0 cget name="$p Digital PCM Volume" | grep ": values"; amixer -c0 cget name="$p ASP TX1 Source" | grep ": values"; done
arecord -l
arecord -D hw:0,2 -f S16_LE -r 48000 -c 2 -d 9 /tmp/loop-cap-${1:-a}.wav & rec=$!
sleep 1
aplay -D hw:0,0 ~/audiotest/noise-fs-6s.wav
wait $rec
amixer -q -c0 cset name='MultiMedia3 Mixer PRIMARY_TDM_TX_0' 0
for p in "Top Left" "Top Right" "Bottom Left" "Bottom Right"; do
	amixer -q -c0 cset name="$p Digital PCM Volume" 817
	amixer -q -c0 cset name="$p Analog PCM Volume" 6
done
alsaucm -c 0 set _verb HiFi set _disdev Speaker reset
ls -la /tmp/loop-cap-${1:-a}.wav
