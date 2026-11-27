"""Netlist builders and an ngspice runner for the four stages of the audio processor.

Every stage runs from one 12 V supply with a buffered 6 V mid-rail reference (VREF),
the same single-supply arrangement as the course build.
"""
from __future__ import annotations
import math
import subprocess
import tempfile
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "spice" / "models.lib"
VCC = 12.0          # the build's parts list gives 10-15 V for every stage
VREF = 6.0

SUPPLY = """
Vcc vcc 0 {vcc}
Rv1 vcc vdiv 10k
Rv2 vdiv 0 10k
Cv vdiv 0 10u
Xref vdiv vref vcc 0 vref OPAMP
"""

# ---------------------------------------------------------------- equalizer design
BANDS_HZ = [60, 250, 1000, 4000, 16000]
EQ_Q = 1.0          # bandwidth about 1.4 octaves per band
EQ_RL = 470.0       # gyrator series resistance = branch loss: sets the boost/cut range
EQ_RG = 68e3        # gyrator resistor
EQ_RX = 2.2e3       # input and feedback resistors of the EQ op-amp
EQ_POT = 10e3       # one linear pot per band

E6 = [1.0, 1.5, 2.2, 3.3, 4.7, 6.8]
E12 = [1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2]


def nearest(x: float, series=E12) -> float:
    """Nearest standard value."""
    dec = 10 ** math.floor(math.log10(x))
    cands = [s * dec * k for s in series for k in (0.1, 1, 10)]
    return min(cands, key=lambda c: abs(math.log(c / x)))


E96 = [round(10 ** (i / 96), 2) for i in range(96)]


def eq_components() -> list[dict]:
    """Standard (E12) values for each band: series C and gyrator CG.
    Series RLC with L = RL*RG*CG:  f0 = 1/(2 pi sqrt(L C)),  Q = sqrt(L/C)/RL.
    The pair of E12 values nearest the target f0 with Q between 0.8 and 1.25 is chosen."""
    out = []
    for f0 in BANDS_HZ:
        w0 = 2 * math.pi * f0
        c = 1 / (w0 * EQ_Q * EQ_RL)
        cg = EQ_Q / (w0 * EQ_RG)
        best = None
        for cs in {nearest(c * k, E12) for k in (0.7, 0.85, 1, 1.2, 1.4)}:
            for cgs in {nearest(cg * k, E12) for k in (0.7, 0.85, 1, 1.2, 1.4)}:
                L = EQ_RL * EQ_RG * cgs
                f = 1 / (2 * math.pi * math.sqrt(L * cs))
                q = math.sqrt(L / cs) / EQ_RL
                if 0.8 <= q <= 1.25 and (best is None or abs(math.log(f / f0)) < abs(math.log(best[2] / f0))):
                    best = (cs, cgs, f, q, L)
        cs, cgs, f, q, L = best
        out.append({"f_target": f0, "C_ideal": c, "CG_ideal": cg, "C": cs, "CG": cgs,
                    "L": L, "f0": f, "Q": q})
    return out


def pot(name: str, a: str, b: str, w: str, total: float, pos: float) -> str:
    """Potentiometer between a and b, wiper w; pos = 0 at a, 1 at b."""
    pos = min(max(pos, 1e-4), 1 - 1e-4)
    return f"R{name}a {a} {w} {total * pos}\nR{name}b {w} {b} {total * (1 - pos)}\n"


def eq_stage(inp: str, out: str, settings: list[float]) -> str:
    """Single op-amp graphic equalizer. settings: -1 (full cut) .. 0 (flat) .. +1 (full boost)."""
    s = f"Rx1 {inp} eqa {EQ_RX}\nXeq eqa eqb vcc 0 {out} OPAMP\nRx2 {out} eqb {EQ_RX}\n"
    for i, (b, g) in enumerate(zip(eq_components(), settings)):
        pos = (g + 1) / 2                       # 0 = wiper at A (cut), 1 = at B (boost)
        s += pot(f"eq{i}", "eqa", "eqb", f"w{i}", EQ_POT, pos)
        s += f"Cs{i} w{i} g{i} {b['C']}\n"
        s += f"Xg{i} g{i} vref vcc 0 GYRATOR params: RL={EQ_RL} RG={EQ_RG} CG={b['CG']}\n"
    return s


# ---------------------------------------------------------------- mixer
MIX_RIN = 10e3
MIX_RF = 10e3
MIX_POT = 10e3


def mixer_stage(inputs: list[str], out: str, volumes: list[float]) -> str:
    """Inverting summing amplifier on VREF, one volume pot per input (AC coupled)."""
    s = ""
    for i, (src, vol) in enumerate(zip(inputs, volumes)):
        s += f"Cm{i} {src} p{i} 4.7u\n"
        s += pot(f"m{i}", "vref", f"p{i}", f"mw{i}", MIX_POT, vol)
        s += f"Rm{i} mw{i} sum {MIX_RIN}\n"
    s += f"Rmf {out} sum {MIX_RF}\nXmix vref sum vcc 0 {out} OPAMP\n"
    return s


# ---------------------------------------------------------------- power amplifier
AMP_GAIN = 50        # LM386 with 1.2 kOhm + 10 uF between pins 1 and 8 (the build's circuit)


def amp_stage(inp: str, spk: str, cout: str = "220u", gain: int = AMP_GAIN, volume: float = 1.0) -> str:
    """LM386 stage as built: 10k volume pot, gain set by pins 1-8, Zobel 10 ohm + 0.1 uF,
    output capacitor to an 8 ohm speaker. The input capacitor removes the 6 V bias of the EQ output."""
    return (f"Ca {inp} va 1u\n" + pot("vol", "0", "va", "vw", 10e3, volume) +
            f"Xamp vw 0 vcc 0 ao LM386 params: GAIN={gain}\n"
            f"Rz ao zb 10\nCz zb 0 0.1u\n"
            f"Co ao {spk} {cout}\nRspk {spk} 0 8\n")


# ---------------------------------------------------------------- visualizer
VIS_COLUMNS = 4
VIS_LEDS_PER_COLUMN = 5
VIS_R_LED = 100.0


def visualizer_stage(inp: str, sensitivity: float = 1.0, r_led: float = VIS_R_LED) -> str:
    """LED meter as built: sensitivity pot, voltage-doubler rectifier (D5, D4) into 10 uF,
    then a diode ladder (D1-D3) so each next transistor needs about one more diode drop.
    Each 2N3904 switches a column of 5 red LEDs in series with 100 ohm from the supply."""
    s = pot("sens", "0", inp, "sw", 10e3, sensitivity)
    s += (f"C1v sw d 10u\nD5v 0 d D1N4148\nD4v d n0 D1N4148\nC2v n0 0 10u\n"
          f"D1v n0 n1 D1N4148\nD2v n1 n2 D1N4148\nD3v n2 n3 D1N4148\n")
    for k in range(VIS_COLUMNS):
        s += f"Rb{k} n{k} b{k} 10k\nQ{k} col{k} b{k} 0 Q2N3904\n"
        s += f"Rc{k} vcc a{k}_0 {r_led}\n"
        for j in range(VIS_LEDS_PER_COLUMN):
            nxt = f"a{k}_{j+1}" if j < VIS_LEDS_PER_COLUMN - 1 else f"col{k}"
            s += f"Dl{k}_{j} a{k}_{j} {nxt} LEDRED\n"
    return s


# ---------------------------------------------------------------- runner
def run(body: str, control: str, outputs: list[str], title="audio", vcc: float = VCC) -> dict:
    """Run ngspice in batch; returns {vector: (x, y)} for each requested vector."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        files = []
        ctl = control
        for i, v in enumerate(outputs):
            f = d / f"o{i}.txt"
            files.append(f)
            ctl += f"\nwrdata {f} {v}"
        net = (f"* {title}\n.include {MODELS}\n{SUPPLY.format(vcc=vcc)}\n{body}\n"
               f".control\nset wr_singlescale\nset wr_vecnames\n{ctl}\n.endc\n.end\n")
        (d / "c.cir").write_text(net)
        r = subprocess.run(["ngspice", "-b", str(d / "c.cir")], capture_output=True, text=True, timeout=600)
        res = {}
        for v, f in zip(outputs, files):
            if not f.exists():
                raise RuntimeError(f"ngspice failed for {v}:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
            a = np.loadtxt(f, skiprows=1)
            res[v] = (a[:, 0], a[:, 1])
        return res


def export_netlists() -> list[Path]:
    """Write standalone ngspice netlists to spice/ (run with:  ngspice spice/eq.cir)."""
    stages = {
        "mixer": ("Two inputs, 1 V AC on input 1", "Va a 0 AC 1\nVb b 0 0\n" + mixer_stage(["a", "b"], "out", [1, 1]),
                  "ac dec 50 10 100k\nplot vdb(out)"),
        "eq": ("5-band EQ, 60 Hz band at full boost (edit the pot values to change the setting)",
               "Vin in 0 DC 6 AC 1\n" + eq_stage("in", "out", [1, 0, 0, 0, 0]),
               "ac dec 100 10 40k\nplot vdb(out)"),
        "amp": ("LM386 stage as built, 220 uF output capacitor", "Vin in 0 DC 6 AC 0.01\n" + amp_stage("in", "spk", "220u"),
                "ac dec 50 5 100k\nplot vdb(spk)"),
        "visualizer": ("LED meter as built, 1 kHz tone of 2 V peak at the speaker",
                       "Vin in 0 SIN(0 2 1k)\n" + visualizer_stage("in"),
                       "tran 50u 400m 0 50u\nplot (12-v(a0_0))/100 (12-v(a1_0))/100 (12-v(a2_0))/100 (12-v(a3_0))/100"),
    }
    out = []
    for name, (title, body, ctl) in stages.items():
        f = ROOT / "spice" / f"{name}.cir"
        f.write_text(f"* {title}\n* Generated by analysis/circuits.py\n.include models.lib\n"
                     f"{SUPPLY.format(vcc=VCC)}\n{body}\n.control\n{ctl}\n.endc\n.end\n")
        out.append(f)
    return out
