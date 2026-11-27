"""Run every simulation, save the figures to media/ and the numbers to results.json.

    python analysis/run_all.py          (needs ngspice on the PATH)
"""
from __future__ import annotations
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import circuits as C

MEDIA = C.ROOT / "media"
INK, MUTE, GRID = "#1d1f24", "#6a6f7a", "#e6e4de"
BAND_COLORS = ["#2f6db0", "#2f8f6b", "#c08a1e", "#b5523b", "#7a4fa0"]
plt.rcParams.update({"font.size": 10.5, "axes.edgecolor": MUTE, "axes.labelcolor": INK,
                     "xtick.color": MUTE, "ytick.color": MUTE, "axes.grid": True,
                     "grid.color": GRID, "axes.spines.top": False, "axes.spines.right": False,
                     "figure.dpi": 150, "savefig.bbox": "tight"})


def ac(body, out, start=10, stop=40e3, pts=400):
    return C.run(body, f"ac dec {pts} {start} {stop}", [f"vdb({out})"])[f"vdb({out})"]


def eq_curve(settings):
    return ac("Vin in 0 DC 6 AC 1\n" + C.eq_stage("in", "out", settings), "out")


def eq_results(res):
    rows = []
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.2))
    f, flat = eq_curve([0] * 5)
    res["eq_flat_ripple_db"] = float(np.ptp(flat))
    for i, comp in enumerate(C.eq_components()):
        s = [0] * 5; s[i] = 1
        _, b = eq_curve(s)
        s[i] = -1
        _, c = eq_curve(s)
        rows.append({"band_hz": comp["f_target"], "C": comp["C"], "CG": comp["CG"],
                     "L_H": comp["L"], "f0_calc": comp["f0"], "Q_calc": comp["Q"],
                     "peak_hz": float(f[b.argmax()]), "boost_db": float(b.max()),
                     "cut_db": float(c.min())})
        axs[0].semilogx(f, b, color=BAND_COLORS[i], lw=1.8)
        axs[0].semilogx(f, c, color=BAND_COLORS[i], lw=1.8, ls="--")
        axs[0].text(comp["f_target"], b.max() + 0.6, f"{comp['f_target']:g} Hz" if comp["f_target"] < 1000
                    else f"{comp['f_target']/1000:g} kHz", ha="center", color=BAND_COLORS[i], fontsize=9)
    axs[0].semilogx(f, flat, color=INK, lw=1.2)
    axs[0].set(title="Each band at full boost (solid) and full cut (dashed)", xlabel="Frequency (Hz)",
               ylabel="Gain (dB)", ylim=(-15, 15), xlim=(20, 20e3))
    presets = {"all bands up": [1] * 5, "all bands down": [-1] * 5,
               "bass and treble up (\"smile\")": [1, 0.5, -0.3, 0.5, 1]}
    for (name, s), col in zip(presets.items(), ["#2f6db0", "#b5523b", "#2f8f6b"]):
        _, y = eq_curve(s)
        axs[1].semilogx(f, y, lw=1.8, color=col, label=name)
        res.setdefault("eq_presets", {})[name] = {"min_db": float(y[(f >= 20) & (f <= 20e3)].min()),
                                                 "max_db": float(y[(f >= 20) & (f <= 20e3)].max())}
    axs[1].semilogx(f, flat, color=INK, lw=1.2, label="all flat")
    axs[1].set(title="Several bands together", xlabel="Frequency (Hz)", ylim=(-19, 19), xlim=(20, 20e3))
    axs[1].legend(frameon=False, fontsize=9, loc="lower center")
    fig.savefig(MEDIA / "eq_response.png")
    plt.close(fig)
    res["eq_bands"] = rows


def headroom(res):
    """Largest 60 Hz input the EQ passes without clipping at full 60 Hz boost."""
    def peak(a):
        body = f"Vin in 0 SIN(6 {a} 60)\n" + C.eq_stage("in", "out", [1, 0, 0, 0, 0])
        r = C.run(body, "tran 50u 400m 200m 50u", ["v(out)"])["v(out)"][1]
        return float(r.max() - 6), float(6 - r.min())
    lo, hi = 0.2, 2.0
    for _ in range(14):
        mid = (lo + hi) / 2
        up, dn = peak(mid)
        gain = 10 ** (res["eq_bands"][0]["boost_db"] / 20)
        if abs(up - mid * gain) / (mid * gain) < 0.01 and abs(dn - mid * gain) / (mid * gain) < 0.01:
            lo = mid
        else:
            hi = mid
    res["eq_headroom_vpk_at_full_boost"] = lo
    res["eq_headroom_vrms_at_full_boost"] = lo / np.sqrt(2)


def mixer_results(res):
    body = "Va a 0 AC 1\nVb b 0 0\n" + C.mixer_stage(["a", "b"], "mout", [1, 1])
    f, m = ac(body, "mout", 2, 100e3, 100)
    res["mixer"] = {"gain_db_1k": float(np.interp(1e3, f, m)), "gain_db_20hz": float(np.interp(20, f, m)),
                    "gain_db_20khz": float(np.interp(20e3, f, m)),
                    "f_low_3db": float(f[np.argmax(m > m.max() - 3)])}
    # sum check: two inputs at 0.5 V each, in phase -> 1.0 V out
    body = "Va a 0 AC 0.5\nVb b 0 AC 0.5\n" + C.mixer_stage(["a", "b"], "mout", [1, 1])
    f, m = C.run(body, "ac lin 3 990 1010", ["vdb(mout)"])["vdb(mout)"]
    res["mixer"]["two_inputs_0p5v_sum_db"] = float(np.interp(1e3, f, m))


def amp_results(res):
    fig, ax = plt.subplots(figsize=(7.5, 4))
    out = {}
    for cout, col, lab in [("220u", "#b5523b", "220 µF (as built)"),
                           ("1000u", "#2f6db0", "1000 µF (suggested)")]:
        f, v = ac("Vin in 0 DC 6 AC 1\n" + C.amp_stage("in", "spk", cout), "spk", 5, 200e3, 200)
        mid = np.interp(1e3, f, v)
        out[cout] = {"gain_db": float(mid), "f_low_3db": float(f[np.argmax(v > mid - 3)]),
                     "at_60hz_db": float(np.interp(60, f, v) - mid)}
        ax.semilogx(f, v - mid, lw=2, color=col, label=f"output capacitor {lab}")
    for b, c in zip(C.BANDS_HZ, BAND_COLORS):
        ax.axvline(b, color=c, lw=0.8, ls=":")
    ax.set(title="LM386 into an 8 Ω speaker: low-frequency response", xlabel="Frequency (Hz)",
           ylabel="Gain re 1 kHz (dB)", xlim=(10, 20e3), ylim=(-20, 2))
    ax.legend(frameon=False, loc="lower right")
    ax.text(62, -18.5, "dotted lines: EQ band centres", color=MUTE, fontsize=8.5)
    fig.savefig(MEDIA / "amp_low_end.png")
    plt.close(fig)
    # clipping: output swings about +-5 V on 12 V; input that reaches it at each gain setting
    out["clip_input_vpk"] = {str(g): 5.0 / g for g in (20, 50, 200)}
    res["amp"] = out


def vis_currents(apk, vcc=C.VCC, r_led=C.VIS_R_LED):
    """Mean LED current (mA) in each column for a 1 kHz tone of apk volts peak at the speaker."""
    body = f"Vin in 0 SIN(0 {apk:.5f} 1k)\n" + C.visualizer_stage("in", r_led=r_led)
    r = C.run(body, "tran 50u 400m 0 50u", [f"v(a{k}_0)" for k in range(C.VIS_COLUMNS)], vcc=vcc)
    return [float(max(0.0, (vcc - r[f"v(a{k}_0)"][1][-1000:]).mean() / r_led * 1e3))
            for k in range(C.VIS_COLUMNS)]


def visualizer_results(res):
    levels = np.arange(-6, 12.01, 0.5)          # dB re 1 V peak at the speaker
    cur = np.array([vis_currents(10 ** (db / 20)) for db in levels])
    on = []                                      # level where each column reaches 5 mA (clearly lit)
    for k in range(C.VIS_COLUMNS):
        idx = np.argmax(cur[:, k] >= 5)
        on.append(float(levels[idx]) if cur[idx, k] >= 5 else None)
    supply = {str(v): vis_currents(4.0, vcc=v) for v in (10.0, 12.0, 15.0)}
    fix = vis_currents(4.0, vcc=15.0, r_led=270)
    res["visualizer"] = {"levels_db": levels.tolist(), "column_ma": cur.tolist(),
                         "column_on_db_5ma": on,
                         "full_scale_ma_by_supply": supply,
                         "full_scale_ma_15v_270ohm": fix}
    fig, ax = plt.subplots(figsize=(7.5, 3.9))
    cols = ["#2f8f6b", "#c08a1e", "#b5523b", "#7a4fa0"]
    for k in range(C.VIS_COLUMNS):
        ax.plot(levels, cur[:, k], lw=2.2, color=cols[k], label=f"column {k+1}")
    ax.axhline(5, color=MUTE, lw=0.8, ls=":")
    ax.text(levels[0] + 0.2, 6, "clearly lit (5 mA)", color=MUTE, fontsize=8.5)
    ax.set(title="LED meter (as built): current in each column of 5 LEDs", ylabel="LED current (mA)",
           xlabel="Speaker signal, dB relative to 1 V peak (1 kHz tone)", ylim=(0, 22))
    ax.legend(frameon=False, loc="upper left", bbox_to_anchor=(0, 0.92))
    fig.savefig(MEDIA / "visualizer_columns.png")
    plt.close(fig)


def system_results(res):
    """Whole chain: input 1 -> mixer -> EQ -> volume -> LM386 -> 8 ohm, EQ flat, volume at max."""
    body = ("Va a 0 AC 0.01\nVb b 0 0\n" + C.mixer_stage(["a", "b"], "mout", [1, 1]) +
            C.eq_stage("mout", "eqo", [0] * 5) + C.amp_stage("eqo", "spk", "1000u"))
    f, v = ac(body, "spk", 5, 100e3, 100)
    band = (f >= 50) & (f <= 20e3)
    res["system"] = {"gain_db_1k": float(np.interp(1e3, f, v) + 40),
                     "flatness_50hz_20khz_db": float(np.ptp(v[band])),
                     "f_low_3db": float(f[np.argmax(v > np.interp(1e3, f, v) - 3)])}


def main():
    MEDIA.mkdir(exist_ok=True)
    res = {}
    mixer_results(res)
    eq_results(res)
    headroom(res)
    amp_results(res)
    visualizer_results(res)
    system_results(res)
    C.export_netlists()
    (C.ROOT / "results.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
