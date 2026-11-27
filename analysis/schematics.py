"""Draw the schematics of the four stages (schemdraw) into media/ as SVG and PNG."""
import schemdraw
import schemdraw.elements as elm
from circuits import ROOT, EQ_RX, EQ_RL, EQ_RG, eq_components

MEDIA = ROOT / "media"
schemdraw.config(fontsize=11, lw=1.3)


def fmt_c(c):
    if c >= 1e-6:
        return f"{c*1e6:.3g} µF"
    if c >= 1e-9:
        return f"{c*1e9:.3g} nF"
    return f"{c*1e12:.3g} pF"


def save(d, name):
    d.save(str(MEDIA / f"{name}.svg"))


def mixer():
    d = schemdraw.Drawing(show=False)
    op = d.add(elm.Opamp(leads=True).right().anchor("in1").at((9, 0)))          # (-) on top
    node = (7.6, 0)
    d.add(elm.Line().at(op.in1).to(node))
    d.add(elm.Dot().at(node))
    for i, y in enumerate([2.0, -2.0]):
        x0 = 0.0
        d.add(elm.Dot(open=True).at((x0, y)).label(f"In {i+1}", loc="left"))
        d.add(elm.Capacitor().at((x0, y)).right(1.6).label("4.7 µF", loc="top"))
        top = (x0 + 1.6, y)
        p = d.add(elm.Potentiometer().at(top).down(2.2))
        d.add(elm.Ground())
        d.add(elm.Line().at(p.tap).right().tox(4.4))
        d.add(elm.Resistor().right().tox(6.6).label("10 kΩ", loc="top"))
        d.add(elm.Line().right().tox(node[0]))
        d.add(elm.Line().up().toy(node[1]) if y < 0 else elm.Line().down().toy(node[1]))
        d.add(elm.Label().at((top[0] - 0.75, y - 1.1)).label(f"volume {i+1}\n10 kΩ", fontsize=9, halign="right"))
    d.add(elm.Line().at(op.in2).left(0.5))
    d.add(elm.Ground())
    d.add(elm.Line().at(node).up(3.4))
    d.add(elm.Resistor().right().tox(op.out[0] + 0.8).label("Rf 10 kΩ", loc="top"))
    d.add(elm.Line().down().toy(op.out[1]))
    d.add(elm.Dot())
    d.add(elm.Line().at(op.out).right(1.8))
    d.add(elm.Dot(open=True).label("to EQ", loc="right"))
    d.add(elm.Label().at((6.0, -5.5)).label(
        "Inverting summer: each input has gain −Rf/Rin = −1.  Ground symbols are the 6 V reference (VREF)."))
    save(d, "sch_mixer")


def eq():
    comps = eq_components()
    d = schemdraw.Drawing(show=False)
    d.add(elm.Dot(open=True).at((-0.5, 0)).label("from mixer", loc="left"))
    d.add(elm.Resistor().right().to((2.5, 0)).label(f"Rx {EQ_RX/1e3:g} kΩ", loc="top"))
    A = (2.5, 0)
    d.add(elm.Dot().at(A).label("A", loc="top"))
    op = d.add(elm.Opamp(leads=True).right().flip().anchor("in2").at((4.2, 0)))  # (+) on top
    d.add(elm.Line().at(A).to(op.in2))
    pot = d.add(elm.Potentiometer().at(A).down(3).flip())
    d.add(elm.Label().at((4.3, -2.6)).label("10 kΩ band pot\nwiper at A = cut\nwiper at B = boost",
                                            halign="left", fontsize=10))
    B = (2.5, -3)
    d.add(elm.Dot().at(B).label("B", loc="left"))
    d.add(elm.Line().at(B).right().tox(3.6))
    d.add(elm.Line().up().toy(op.in1[1]))
    d.add(elm.Line().to(op.in1))
    O = (op.out[0] + 0.9, op.out[1])
    d.add(elm.Line().at(op.out).to(O))
    d.add(elm.Dot().at(O))
    d.add(elm.Line().at(O).right(1.5))
    d.add(elm.Dot(open=True).label("to amplifier\nand LED bar", loc="right"))
    d.add(elm.Line().at(O).down().toy(-4.6))
    d.add(elm.Resistor().left().tox(B[0]).label(f"Rx {EQ_RX/1e3:g} kΩ", loc="bottom"))
    d.add(elm.Line().up().toy(B[1]))
    d.add(elm.Line().at(pot.tap).left(1.8))
    d.add(elm.Capacitor().down(1.6).label("C", loc="bottom"))
    d.add(elm.Inductor2().down(1.8).label("L: gyrator\n(series RL)", loc="bottom"))
    d.add(elm.Ground())
    d.add(elm.Label().at((A[0] - 1.3, -5.0)).label("VREF", fontsize=10))
    rows = [(f"{c['f_target']:g} Hz" if c["f_target"] < 1000 else f"{c['f_target']/1000:g} kHz") +
            f": C {fmt_c(c['C'])}, CG {fmt_c(c['CG'])}" for c in comps]
    d.add(elm.Label().at((9.6, -1.6)).label(
        "5 band branches in parallel between A and B:\n" + "\n".join(rows) +
        f"\nRL {EQ_RL:g} Ω, RG {EQ_RG/1e3:g} kΩ in every gyrator", halign="left", valign="top"))
    save(d, "sch_eq")


def gyrator():
    d = schemdraw.Drawing(show=False)
    n = (0.8, 0)
    d.add(elm.Dot(open=True).at((0, 0)).label("to C", loc="left"))
    d.add(elm.Line().right().to(n))
    d.add(elm.Dot().at(n))
    d.add(elm.Capacitor().at(n).right(2.2).label("CG", loc="top"))
    x = (3.0, 0)
    d.add(elm.Dot().at(x))
    d.add(elm.Resistor().at(x).down(2.2).label(f"RG {EQ_RG/1e3:g} kΩ", loc="top"))
    d.add(elm.Ground())
    d.add(elm.Label().at((x[0] + 0.75, -2.75)).label("VREF", fontsize=10))
    op = d.add(elm.Opamp(leads=True).right().flip().anchor("in2").at((4.4, 0)))
    d.add(elm.Line().at(x).to(op.in2))
    o = (op.out[0] + 0.6, op.out[1])
    d.add(elm.Line().at(op.out).to(o))
    d.add(elm.Dot().at(o))
    d.add(elm.Line().at(o).down().toy(-1.9))
    d.add(elm.Line().left().tox(op.in1[0] - 0.4))
    d.add(elm.Line().up().toy(op.in1[1]))
    d.add(elm.Line().to(op.in1))
    d.add(elm.Line().at((o[0], -1.9)).down().toy(-3.6))
    d.add(elm.Resistor().left().tox(n[0]).label(f"RL {EQ_RL:g} Ω", loc="bottom"))
    d.add(elm.Line().up().toy(n[1]))
    d.add(elm.Label().at((3.4, -4.6)).label("Z ≈ RL + jω·L,  L = RL·RG·CG  (an inductor without a coil)"))
    save(d, "sch_gyrator")


def visualizer():
    """The LED meter as built (course reference circuit), redrawn."""
    d = schemdraw.Drawing(show=False)
    d.add(elm.Dot(open=True).at((0, 1.5)).label("from speaker\noutput", loc="left"))
    d.add(elm.Line().right(1.0))
    pot = d.add(elm.Potentiometer().at((1.0, 1.5)).down(2.6))
    d.add(elm.Ground())
    d.add(elm.Label().at((0.1, -0.6)).label("sensitivity\n10 kΩ", fontsize=9))
    yb = pot.tap[1]
    d.add(elm.Line().at(pot.tap).right().tox(2.4))
    d.add(elm.Capacitor().right(1.6).label("C1 10 µF", loc="top"))
    dn = d.here
    d.add(elm.Dot())
    d.add(elm.Diode().at(dn).down(1.8).reverse().label("D5", loc="bottom"))
    d.add(elm.Ground())
    d.add(elm.Diode().at(dn).right(1.8).label("D4", loc="top"))
    n0 = d.here
    d.add(elm.Dot())
    d.add(elm.Capacitor(polar=True).at(n0).down(1.8).label("C2 10 µF", loc="bottom"))
    d.add(elm.Ground())
    nodes = [n0]
    x = n0[0]
    for k in range(3):
        d.add(elm.Diode().at((x, yb)).right(3.0).label(f"D{k+1}", loc="bottom"))
        x += 3.0
        nodes.append((x, yb))
        d.add(elm.Dot().at((x, yb)))
    for k, n in enumerate(nodes):
        d.add(elm.Line().at(n).up(0.5))
        d.add(elm.Resistor().up(1.6).label("10 kΩ", loc="top"))
        q = d.add(elm.BjtNpn(circle=True).right().anchor("base").at(d.here)
                  .label(f"Q{k+1}", loc="right", ofst=(0.05, 0.1)))
        d.add(elm.Ground().at(q.emitter))
        cx, cy = q.collector
        top = cy + 0.4 + 5 * 0.9 + 1.4
        d.add(elm.Vdd().at((cx, top)).label("12 V"))
        d.add(elm.Resistor().at((cx, top)).down(1.4).label("100 Ω", loc="bottom"))
        for j in range(5):
            d.add(elm.LED().down(0.9))
        d.add(elm.Line().down().toy(cy))
    d.add(elm.Label().at((7.5, yb - 3.0)).label(
        "Doubler rectifier (C1, D5, D4, C2); each diode D1–D3 raises the level the next transistor needs by about 0.6 V.\n"
        "Each 2N3904 switches a column of 5 red LEDs: 4 columns, 20 LEDs.  Diodes are 1N4148."))
    save(d, "sch_visualizer")


def amp():
    """The LM386 stage as built (course reference circuit), redrawn."""
    d = schemdraw.Drawing(show=False)
    d.add(elm.Dot(open=True).at((0, 0)).label("from EQ", loc="left"))
    d.add(elm.Capacitor().right(1.8).label("1 µF", loc="top"))
    p = d.add(elm.Potentiometer().down(3))
    d.add(elm.Ground())
    d.add(elm.Label().at((1.0, -1.5)).label("volume\n10 kΩ", fontsize=9, halign="right"))
    op = d.add(elm.Opamp(leads=True).right().flip().anchor("in2").at((4.6, 0.0)))
    d.add(elm.Label().at((op.in2[0] + 1.3, op.in2[1] - 0.6)).label("LM386", fontsize=9))
    d.add(elm.Line().at(p.tap).right().tox(3.8))
    d.add(elm.Line().up().toy(op.in2[1]))
    d.add(elm.Line().to(op.in2))
    d.add(elm.Line().at(op.in1).left(0.5))
    d.add(elm.Ground())
    # gain pins 1 and 8 on the top of the package
    d.add(elm.Line().at(op.vs).up(1.4))
    d.add(elm.Resistor().right(1.6).label("1.2 kΩ", loc="top"))
    d.add(elm.Capacitor().right(1.2).label("10 µF", loc="top"))
    d.add(elm.Line().down().toy(op.n1[1]))
    d.add(elm.Line().left().tox(op.n1[0]))
    d.add(elm.Label().at((op.vs[0] - 0.25, op.vs[1] + 0.45)).label("1", fontsize=8))
    d.add(elm.Label().at((op.n1[0] + 0.2, op.n1[1] + 0.45)).label("8", fontsize=8))
    d.add(elm.Label().at((op.vs[0] + 1.4, op.vs[1] + 2.4)).label("pins 1–8: gain 50", fontsize=9))
    o = (op.out[0] + 1.0, op.out[1])
    d.add(elm.Line().at(op.out).to(o))
    d.add(elm.Dot().at(o))
    d.add(elm.Resistor().at(o).down(1.6).label("10 Ω", loc="bottom"))
    d.add(elm.Capacitor().down(1.6).label("0.1 µF", loc="bottom"))
    d.add(elm.Ground())
    d.add(elm.Capacitor(polar=True).at(o).right(2.4).label("220 µF", loc="top"))
    d.add(elm.Speaker().right().label("8 Ω", loc="top"))
    d.add(elm.Label().at((6.5, -4.9)).label(
        "Zobel network (10 Ω + 0.1 µF) keeps the output stable into the speaker.  Supply 12 V (pin 6); pin 7 bypassed with 10 µF (not modelled)."))
    save(d, "sch_amp")


def to_png():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(device_scale_factor=2)
        for f in sorted(MEDIA.glob("sch_*.svg")):
            pg.goto(f.resolve().as_uri())
            pg.query_selector("svg").screenshot(path=str(f.with_suffix(".png")))
        b.close()


if __name__ == "__main__":
    MEDIA.mkdir(exist_ok=True)
    mixer(); eq(); gyrator(); visualizer(); amp()
    to_png()
    print("done")
