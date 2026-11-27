"""Checks on the simulated circuits (need ngspice on the PATH)."""
import math
import sys
from pathlib import Path
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))
import circuits as C  # noqa: E402


def eq(settings):
    return C.run("Vin in 0 DC 6 AC 1\n" + C.eq_stage("in", "out", settings),
                 "ac dec 200 10 40k", ["vdb(out)"])["vdb(out)"]


def test_eq_flat_when_all_pots_centred():
    _, v = eq([0] * 5)
    assert np.ptp(v) < 0.05


@pytest.mark.parametrize("i", range(5))
def test_eq_band_centre_and_range(i):
    s = [0] * 5
    s[i] = 1
    f, b = eq(s)
    s[i] = -1
    _, c = eq(s)
    target = C.BANDS_HZ[i]
    assert abs(math.log(f[b.argmax()] / target)) < math.log(1.08)      # peak within 8 % of target
    assert 11.0 <= b.max() <= 13.5                                       # about +12 dB
    assert abs(b.max() + c.min()) < 0.1                                  # cut mirrors boost


def test_mixer_unity_gain_and_sum():
    body = "Va a 0 AC 0.5\nVb b 0 AC 0.5\n" + C.mixer_stage(["a", "b"], "m", [1, 1])
    f, v = C.run(body, "ac lin 3 990 1010", ["vdb(m)"])["vdb(m)"]
    assert abs(v[1]) < 0.05                                               # 0.5 V + 0.5 V = 1 V (0 dB)


@pytest.mark.parametrize("cout,lo,hi", [("220u", 80, 100), ("1000u", 15, 40)])
def test_amp_gain_and_low_cutoff(cout, lo, hi):
    f, v = C.run("Vin in 0 DC 6 AC 1\n" + C.amp_stage("in", "spk", cout),
                 "ac dec 200 5 100k", ["vdb(spk)"])["vdb(spk)"]
    mid = np.interp(1e3, f, v)
    assert abs(mid - 20 * math.log10(C.AMP_GAIN)) < 1.0                   # gain about 50
    assert lo < f[np.argmax(v > mid - 3)] < hi


def led_ma(apk, vcc=12.0, r_led=100.0):
    r = C.run(f"Vin in 0 SIN(0 {apk} 1k)\n" + C.visualizer_stage("in", r_led=r_led), "tran 50u 300m 0 50u",
              [f"v(a{k}_0)" for k in range(4)], vcc=vcc)
    return [max(0.0, (vcc - r[f"v(a{k}_0)"][1][-1000:]).mean() / r_led * 1e3) for k in range(4)]


def test_visualizer_columns_light_in_order():
    weak, mid, loud = led_ma(0.6), led_ma(1.6), led_ma(4.0)
    assert max(weak) < 1                                                  # nothing lit
    assert mid[0] > mid[1] > mid[2] > mid[3]                              # column 1 first
    assert all(17 < i < 22 for i in loud)                                 # all full at 12 V


def test_visualizer_led_current_vs_supply():
    assert max(led_ma(4.0, vcc=10.0)) < 8                                 # 5 LEDs in series barely light at 10 V
    assert min(led_ma(4.0, vcc=15.0)) > 35                                # over the 20 mA rating at 15 V
    assert all(15 < i < 20 for i in led_ma(4.0, vcc=15.0, r_led=270))     # 270 ohm fixes it


def test_netlists_export():
    files = C.export_netlists()
    assert {f.name for f in files} == {"mixer.cir", "eq.cir", "amp.cir", "visualizer.cir"}
