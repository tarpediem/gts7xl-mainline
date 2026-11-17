# tests/test_dts_audio.py
"""Speaker amplifiers (4x CS35L41) and the speaker UCM must stay within stock limits.

The DTS is read from linux/ (or GTS7XL_LINUX, e.g. linux-audio while the audio branch is
not merged); the test is skipped when that tree has no CS35L41 yet. Stock values come from
reference/live/live.dts (local only) or the numbers below (T976BXXS7DXH1).
Safety rules checked:
- boost peak current not above stock; boost inductor/capacitor that program the same
  coefficients as stock (the stock driver leaves BSTCVRT_COEFF/SLOPE_LBST at reset: 1.0 uH,
  capacitor range 0-19 uF);
- the four amps at the stock addresses on the stock bus, stock reset/interrupt GPIOs;
- Primary TDM on the stock pins;
- the UCM speaker device keeps every amp at <= 6.5 dB analog gain (14 dB under the
  maximum) and at most 0 dB digital.
"""
import os
import re
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
LINUX = ROOT / os.environ.get("GTS7XL_LINUX", "linux")
DTS = LINUX / "arch" / "arm64" / "boot" / "dts" / "qcom" / "sm8250-samsung-gts7xl.dts"
LIVE = ROOT / "reference" / "live" / "live.dts"
UCM = ROOT / os.environ.get("GTS7XL_PMAPORTS", "pmaports") / "device" / "testing" / \
    "alsa-ucm-conf-samsung-gts7xl" / "HiFi.conf"

STOCK = {
    "addrs": {0x40, 0x41, 0x42, 0x43},
    "boost_peak_ma": 4100,
    "reset_gpio": 69,
    "irq_gpio": 84,
    "tdm_pins": {"gpio138": "mi2s0_sck", "gpio139": "mi2s0_data0",
                 "gpio140": "mi2s0_data1", "gpio141": "mi2s0_ws"},
}

# Analog PCM Volume: raw 0..20 = 0.5..20.5 dB. Without the speaker-protection
# firmware keep at least 14 dB of headroom: raw <= 6 (6.5 dB).
ANALOG_MAX = 6
# Digital PCM Volume: raw 1..913 = -102..+12 dB in 1/8 dB steps, 0 dB = 817
DIG_0DB = 817


def dts_text():
    if not DTS.exists():
        pytest.skip("needs the linux checkout")
    text = DTS.read_text()
    if "cirrus,cs35l41" not in text:
        pytest.skip(f"{LINUX.name} has no speaker amplifiers yet")
    return text


@pytest.fixture(scope="module")
def stock():
    if not LIVE.exists():
        return STOCK
    live = LIVE.read_text()
    amps = re.findall(r"cs35l41@(\w+) \{(.*?)\n\t\t\t\};", live, re.S)
    peak = {int(x, 0) for _, b in amps for x in re.findall(r"boost-peak-milliamp = <(\w+)>", b)}
    reset = {int(x, 0) for _, b in amps for x in re.findall(r"reset-gpios = <\w+ (\w+) ", b)}
    irq = {int(x, 0) for _, b in amps for x in re.findall(r"\tinterrupts = <(\w+) ", b)}
    assert len(peak) == len(reset) == len(irq) == 1
    pins = {}
    for name in ("clk", "sync", "din", "dout"):
        blk = re.search(rf"pri_tdm_{name}_active: pri_tdm_{name}_active \{{(.*?)\n\t\t\t\t\}};",
                        live, re.S).group(1)
        pins[re.search(r'pins = "(gpio\d+)"', blk).group(1)] = \
            re.search(r'function = "(\w+)"', blk).group(1)
    return {"addrs": {int(a, 16) for a, _ in amps}, "boost_peak_ma": peak.pop(),
            "reset_gpio": reset.pop(), "irq_gpio": irq.pop(), "tdm_pins": pins}


def amps(text):
    i2c = re.search(r"^&i2c11 \{\n(.*?)\n\};", text, re.S | re.M)
    assert i2c, "&i2c11"
    return re.findall(r"speaker-amp@(\w+) \{\n(.*?)\n\t\};", i2c.group(1), re.S)


def u32(block, prop):
    m = re.search(rf"\t{re.escape(prop)} = <([^>]*)>;", block)
    assert m, prop
    return m.group(1).split()


def test_amp_addresses_and_gpios(stock):
    found = amps(dts_text())
    assert {int(a, 16) for a, _ in found} == stock["addrs"]
    for _, b in found:
        assert u32(b, "reset-gpios")[:2] == ["&tlmm", str(stock["reset_gpio"])]
        assert int(u32(b, "interrupts")[0]) == stock["irq_gpio"]


def test_boost_not_above_stock(stock):
    for addr, b in amps(dts_text()):
        assert int(u32(b, "cirrus,boost-peak-milliamp")[0]) <= stock["boost_peak_ma"], addr
        # stock coefficients (driver defaults): 1.0 uH, capacitor range 0..19 uF
        assert int(u32(b, "cirrus,boost-ind-nanohenry")[0]) == 1000, addr
        assert 0 <= int(u32(b, "cirrus,boost-cap-microfarad")[0]) <= 19, addr
        assert "cirrus,boost-type" not in b, addr  # internal boost, as stock


def test_left_right_slots():
    """Codec n of the speaker link plays slot n % 2: left, right, left, right.
    Positions checked by ear (landscape): 0x41/0x40 left, 0x43/0x42 right."""
    text = dts_text()
    labels = dict((lab, int(a, 16)) for lab, a in
                  re.findall(r"(spk_amp_\w+): speaker-amp@(\w+)", text))
    link = re.search(r"speaker-dai-link \{(.*?)\n\t\};", text, re.S).group(1)
    codecs = re.findall(r"&(spk_amp_\w+) 0", link)
    addrs = [labels[c] for c in codecs]
    assert [a for i, a in enumerate(addrs) if i % 2 == 0] and \
        {a for i, a in enumerate(addrs) if i % 2 == 0} == {0x41, 0x40}
    assert {a for i, a in enumerate(addrs) if i % 2 == 1} == {0x43, 0x42}


def test_tdm_pins(stock):
    text = dts_text()
    blk = re.search(r"pri_tdm_active: pri-tdm-active-state \{\n(.*?)\n\t\};", text, re.S)
    assert blk
    pins = dict(re.findall(r'pins = "(gpio\d+)";\n\t+function = "(\w+)";', blk.group(1)))
    assert pins == stock["tdm_pins"]


def test_adsp_firmware_path():
    text = dts_text()
    m = re.search(r"^&adsp \{\n(.*?)\n\};", text, re.S | re.M)
    assert m and 'firmware-name = "qcom/sm8250/samsung/gts7xl/adsp.mbn";' in m.group(1)
    assert 'status = "okay"' in m.group(1)


def test_ucm_volumes_capped():
    if not UCM.exists():
        pytest.skip("no UCM in this pmaports tree")
    ucm = UCM.read_text()
    for p in ("Top Left", "Top Right", "Bottom Left", "Bottom Right"):
        a = re.findall(rf"cset \"name='{p} Analog PCM Volume' (\d+)\"", ucm)
        d = re.findall(rf"cset \"name='{p} Digital PCM Volume' (\d+)\"", ucm)
        assert len(a) == 1 and int(a[0]) <= ANALOG_MAX, p
        assert len(d) == 1 and int(d[0]) <= DIG_0DB, p
    assert "PlaybackMixerElem" not in ucm  # volume stays in software
