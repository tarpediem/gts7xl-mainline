# Series 7 — ASoC: qcom: sm8250: Primary TDM with several codecs

Readiness: **needs work (small)**.

## Patch

| # | Subject | Source | Files |
|---|---|---|---|
| 1 | `ASoC: qcom: sm8250: Support Primary TDM with several codecs` | 77d829629 | `sound/soc/qcom/sm8250.c` |

## Checks

- checkpatch --strict: `ENOTSUPP` x3 (the code tolerates `-ENOTSUPP` from
  `snd_soc_dai_set_*()`, which is what ASoC returns; keep it but compare against what the
  other qcom machine drivers do, and add a comment), placeholder sign-off.
- Hardware: four CS35L41 amplifiers in stereo (left, right, left, right) at 48 kHz through
  the ADSP; checked by ear amp by amp.

## Recipients

- To: Srinivas Kandagatla <srini@kernel.org> (qcom audio), Mark Brown <broonie@kernel.org>,
  Liam Girdwood <lgirdwood@gmail.com>
- Cc: Jaroslav Kysela, Takashi Iwai, linux-sound@vger.kernel.org,
  linux-arm-msm@vger.kernel.org, linux-kernel@vger.kernel.org; for the amplifier side,
  patches@opensource.cirrus.com is useful to Cc.
- Tree: ASoC (`broonie/sound.git` for-next).

## Must do before sending

1. Hard-coded TDM format (4 slots x 16 bits, 48 kHz, DSP_A, bit clock always on): check how
   sm8250.c and sc8280xp.c / x1e80100.c handle TDM today and whether the slot layout can come
   from DT (`dai-tdm-slot-num`, `dai-tdm-slot-width`, `dai-tdm-slot-tx-mask` in the
   sound-card link) instead of the driver. Mark Brown will prefer DT-driven parameters.
2. "codec n gets slot n % channels" is a board policy; move it to DT (per-codec TDM masks) if
   possible.
3. Verify the Qualcomm RB5 (the other sm8250 user of this machine driver) is unaffected:
   the new code must only run for TDM links.
4. Open items from NOTES.md that reviewers may ask about: `AFE failed to vote (3)` at ADSP
   start, no IV feedback (TDM TX) yet, no speaker protection firmware. Mention them below the
   `---`.
