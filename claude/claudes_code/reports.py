"""
PDF report rendering for the CS amplifier stage.

This module only draws and formats. Every number shown comes from the
student's own functions (Circuit_Sol getters, analyzeCSAmpModel,
CSAmpModelScoreBreakdown, scoreCSAmpModel) -- no circuit analysis happens here.

When spec.USE_MONTE_CARLO is on, the nominal values are produced by temporarily
switching it off. The Monte Carlo columns are the min/max seen over repeated calls
to the same functions with it switched back on.
"""

import os
import datetime
from contextlib import contextmanager

import lab_specific_code.specs as spec

import matplotlib
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle

from lab_specific_code.CS_Amp import (
    analyzeCSAmpModel,
    CSAmpModelScoreBreakdown,
    scoreCSAmpModel,
)


# ---------------------------------------------------------------- fonts

def _register_fonts():
    # DejaVu ships with matplotlib and has the Ω / µ glyphs Helvetica lacks
    font_dir = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
    try:
        pdfmetrics.registerFont(TTFont("DejaVu", os.path.join(font_dir, "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", os.path.join(font_dir, "DejaVuSans-Bold.ttf")))
        return "DejaVu", "DejaVu-Bold", "Ω", "µ"
    except Exception:
        return "Helvetica", "Helvetica-Bold", "Ohm", "u"


FONT, FONT_BOLD, OHM, MICRO = _register_fonts()

INK = colors.HexColor("#1f2933")
WIRE = colors.HexColor("#1f2933")
COMP = colors.HexColor("#1d4ed8")     # component value labels
NODE = colors.HexColor("#b45309")     # operating-point annotations
MUTED = colors.HexColor("#6b7280")
GOOD = colors.HexColor("#15803d")
WARN = colors.HexColor("#b45309")
BAD = colors.HexColor("#b91c1c")
RULE = colors.HexColor("#d1d5db")
HEADER_BG = colors.HexColor("#eef2f7")


# ---------------------------------------------------------------- formatting

_PREFIXES = [(1e9, "G"), (1e6, "M"), (1e3, "k"), (1, ""), (1e-3, "m"), (1e-6, MICRO), (1e-9, "n")]


def _si(value, unit, digits=4):
    """Format a number with an SI prefix, e.g. 0.00499 A -> '4.992 mA'."""
    if value is None:
        return "-"
    if value == 0:
        return "0 " + unit
    mag = abs(value)
    for scale, prefix in _PREFIXES:
        if mag >= scale:
            return f"{value / scale:.{digits}g} {prefix}{unit}"
    scale, prefix = _PREFIXES[-1]
    return f"{value / scale:.{digits}g} {prefix}{unit}"


def _ohms(value):
    return _si(value, OHM)


# key in analyzeCSAmpModel output -> (display name, unit)
_ANALYSIS_LABELS = {
    "Vov": ("Overdrive voltage  V_OV", "V"),
    "ID": ("Drain current  I_D", "A"),
    "VG": ("Gate voltage  V_G", "V"),
    "VS": ("Source voltage  V_S", "V"),
    "VD": ("Drain voltage  V_D", "V"),
    "VDS": ("Drain-source  V_DS", "V"),
    "VGS": ("Gate-source  V_GS", "V"),
    "gm": ("Transconductance  g_m", "S"),
    "Ri": ("Input resistance  R_i", OHM),
    "Avo": ("Open-circuit gain  A_vo", "V/V"),
    "Ro": ("Output resistance  R_o", OHM),
    "Av": ("Loaded gain  A_v", "V/V"),
    "PD": ("Power  R_D", "W"),
    "PG1": ("Power  R_G1", "W"),
    "PG2": ("Power  R_G2", "W"),
    "PS1": ("Power  R_S1", "W"),
    "PS2": ("Power  R_S2", "W"),
    "downward_margin": ("Swing margin, downward", "V"),
    "upward_margin": ("Swing margin, upward", "V"),
    "HD2": ("Distortion estimate  HD_2", "%"),
    "Vt": ("Threshold voltage  V_t", "V"),
}

MC_SAMPLES = 200        # repeated analysis / breakdown calls for the Monte Carlo columns
MC_SCORE_SAMPLES = 20   # repeated scoreCSAmpModel calls (each already averages its own reps)


def _fmt_analysis_value(key, value):
    if value is None:
        return "-"
    unit = _ANALYSIS_LABELS.get(key, ("", ""))[1]
    if unit == "%":
        return f"{value * 100:.3g} %"
    if unit == "V/V":
        return f"{value:.4g} V/V"
    if unit == "":
        return f"{value:.4g}"
    return _si(value, unit)


_LABEL_STYLE = ParagraphStyle("label", fontName=FONT, fontSize=8, leading=9.5, textColor=INK)


def _label_para(label):
    """'Drain current  I_D' -> Paragraph with a real subscript."""
    head, _, sym = label.rpartition("  ")
    if "_" not in sym:
        return Paragraph(label, _LABEL_STYLE)
    base, sub = sym.split("_", 1)
    return Paragraph(f"{head}&nbsp;&nbsp;<i>{base}</i><sub>{sub}</sub>", _LABEL_STYLE)


def _resistor_text(mod, name):
    """'330k + 680 = 330.7 kΩ' style description of a (possibly 2-part) resistor."""
    r = mod.get_resistor(name)
    parts = [_si(p, "").replace(" ", "") for p in r.resistors]
    with _monte_carlo(False):          # nominal value, even if Monte Carlo is on elsewhere
        total = _ohms(mod.get_r(name))
    if len(parts) == 1:
        return total
    joiner = " || " if r.in_parallel else " + "
    return joiner.join(parts) + " = " + total


# ---------------------------------------------------------------- schematic primitives

class _Schematic:
    """Tiny helper that maps schematic units onto the page and draws symbols."""

    def __init__(self, c, ox, oy, scale):
        self.c = c
        self.ox = ox
        self.oy = oy
        self.s = scale

    def P(self, x, y):
        return self.ox + x * self.s, self.oy + y * self.s

    def wire(self, *pts):
        c = self.c
        c.setStrokeColor(WIRE)
        c.setLineWidth(1.1)
        path = c.beginPath()
        path.moveTo(*self.P(*pts[0]))
        for p in pts[1:]:
            path.lineTo(*self.P(*p))
        c.drawPath(path, stroke=1, fill=0)

    def dot(self, x, y):
        c = self.c
        c.setFillColor(WIRE)
        c.circle(*self.P(x, y), 2.2, stroke=0, fill=1)

    def resistor_v(self, x, y_top, y_bot, body=34):
        """Vertical resistor from y_top down to y_bot (zigzag centred)."""
        mid = (y_top + y_bot) / 2
        z_top, z_bot = mid + body / 2, mid - body / 2
        self.wire((x, y_top), (x, z_top))
        self.wire((x, z_bot), (x, y_bot))
        n, w = 6, 6
        pts = [(x, z_top)]
        for i in range(n):
            yy = z_top - (i + 0.5) * (body / n)
            pts.append((x + (w if i % 2 == 0 else -w), yy))
        pts.append((x, z_bot))
        self.wire(*pts)

    def cap_h(self, x_left, x_right, y, gap=5, plate=11):
        """Horizontal-axis capacitor between x_left and x_right."""
        mid = (x_left + x_right) / 2
        self.wire((x_left, y), (mid - gap / 2, y))
        self.wire((mid + gap / 2, y), (x_right, y))
        self._plate_v(mid - gap / 2, y, plate)
        self._plate_v(mid + gap / 2, y, plate)

    def cap_v(self, x, y_top, y_bot, gap=5, plate=11):
        """Vertical-axis capacitor between y_top and y_bot."""
        mid = (y_top + y_bot) / 2
        self.wire((x, y_top), (x, mid + gap / 2))
        self.wire((x, mid - gap / 2), (x, y_bot))
        self.wire((x - plate, mid + gap / 2), (x + plate, mid + gap / 2))
        self.wire((x - plate, mid - gap / 2), (x + plate, mid - gap / 2))

    def _plate_v(self, x, y, plate):
        self.c.setLineWidth(1.6)
        self.wire((x, y - plate), (x, y + plate))

    def ground(self, x, y):
        self.wire((x, y), (x, y - 6))
        for i, half in enumerate((10, 6.5, 3)):
            yy = y - 6 - i * 3.5
            self.wire((x - half, yy), (x + half, yy))

    def source(self, x, y, r=13):
        c = self.c
        c.setStrokeColor(WIRE)
        c.setLineWidth(1.1)
        c.circle(*self.P(x, y), r * self.s, stroke=1, fill=0)
        self.text(x, y + 3, "+", size=9, center=True)
        self.text(x, y - 8, "−", size=9, center=True)

    def nmos(self, gx, cy, ch_x, sd_x, half=22):
        """Enhancement NMOS. Gate lead enters at (gx, cy); drain/source leads exit at sd_x."""
        g_plate = ch_x - 6
        self.wire((gx, cy), (g_plate, cy))
        self.c.setLineWidth(1.6)
        self.wire((g_plate, cy - half + 4), (g_plate, cy + half - 4))
        seg = (2 * half) / 3
        for i in range(3):
            y0 = cy + half - i * seg - 2
            self.c.setLineWidth(1.6)
            self.wire((ch_x, y0), (ch_x, y0 - seg + 4))
        d_y, b_y, s_y = cy + half - 6, cy, cy - half + 6
        self.wire((ch_x, d_y), (sd_x, d_y))
        self.wire((ch_x, b_y), (sd_x, b_y), (sd_x, s_y))
        self.wire((ch_x, s_y), (sd_x, s_y))
        # body arrow pointing into the channel (N-channel)
        c = self.c
        tip = self.P(ch_x + 1, b_y)
        c.setFillColor(WIRE)
        p = c.beginPath()
        p.moveTo(*tip)
        p.lineTo(*self.P(ch_x + 9, b_y + 4))
        p.lineTo(*self.P(ch_x + 9, b_y - 4))
        p.close()
        c.drawPath(p, stroke=0, fill=1)
        return d_y, s_y

    def text(self, x, y, s, size=8.5, color=INK, center=False, right=False, bold=False):
        c = self.c
        c.setFillColor(color)
        c.setFont(FONT_BOLD if bold else FONT, size)
        X, Y = self.P(x, y)
        if center:
            c.drawCentredString(X, Y, s)
        elif right:
            c.drawRightString(X, Y, s)
        else:
            c.drawString(X, Y, s)

    def sub_label(self, x, y, main, sub, size=9, color=INK, right=False):
        """Draw e.g. R with subscript G1."""
        c = self.c
        w_main = pdfmetrics.stringWidth(main, FONT_BOLD, size)
        w_sub = pdfmetrics.stringWidth(sub, FONT, size * 0.72)
        X, Y = self.P(x, y)
        if right:
            X -= w_main + w_sub
        c.setFillColor(color)
        c.setFont(FONT_BOLD, size)
        c.drawString(X, Y, main)
        c.setFont(FONT, size * 0.72)
        c.drawString(X + w_main, Y - size * 0.25, sub)

    def box_dashed(self, x0, y0, x1, y1):
        c = self.c
        c.setStrokeColor(MUTED)
        c.setDash(2, 2)
        c.setLineWidth(0.7)
        X0, Y0 = self.P(x0, y0)
        X1, Y1 = self.P(x1, y1)
        c.rect(X0, Y0, X1 - X0, Y1 - Y0, stroke=1, fill=0)
        c.setDash()


# ---------------------------------------------------------------- schematic

def _draw_cs_schematic(c, mod, an, ox, oy, scale):
    sc = _Schematic(c, ox, oy, scale)

    GND = 20
    VDD_Y = 290
    GATE_Y = 165
    X_FG = 40
    X_G = 175
    X_MOS = 300
    X_CBY = 360
    X_OUT = 455
    X_RL = 500
    MID_Y = 72

    vdd_txt = _si(mod.get_n("VDD"), "V")

    # rails
    sc.wire((X_FG, GND), (X_RL, GND))
    sc.ground(240, GND)
    sc.wire((X_G, VDD_Y), (X_MOS, VDD_Y))
    sc.wire((X_MOS - 60, VDD_Y), (X_MOS - 60, VDD_Y + 14))
    sc.sub_label(X_MOS - 60, VDD_Y + 18, "V", "DD", size=9, right=True)
    sc.text(X_MOS - 56, VDD_Y + 18, "= " + vdd_txt, size=9, color=COMP)

    # function generator (V_FG with R_FG)
    sc.box_dashed(X_FG - 32, GND + 8, X_FG + 24, GATE_Y + 32)
    sc.text(X_FG - 4, GATE_Y + 36, "Function generator", size=7.5, color=MUTED, center=True)
    sc.source(X_FG, 62)
    sc.wire((X_FG, 49), (X_FG, GND))
    sc.resistor_v(X_FG, GATE_Y, 75, body=40)
    sc.sub_label(X_FG - 10, 128, "R", "FG", right=True)
    sc.sub_label(X_FG - 18, 58, "V", "FG", right=True)

    # Cc1 into the gate
    sc.wire((X_FG, GATE_Y), (X_FG + 52, GATE_Y))
    sc.cap_h(X_FG + 52, X_FG + 92, GATE_Y)
    sc.wire((X_FG + 92, GATE_Y), (X_G, GATE_Y))
    sc.sub_label(X_FG + 62, GATE_Y + 18, "C", "c1")
    sc.text(X_FG + 72, GATE_Y - 24, _si(mod.get_c("1"), "F"), size=8, color=COMP, center=True)

    # gate divider
    sc.resistor_v(X_G, VDD_Y, GATE_Y)
    sc.sub_label(X_G - 12, (VDD_Y + GATE_Y) / 2 + 4, "R", "G1", right=True)
    sc.text(X_G - 12, (VDD_Y + GATE_Y) / 2 - 8, _resistor_text(mod, "G1"), size=7.5, color=COMP, right=True)

    sc.resistor_v(X_G, GATE_Y, GND)
    sc.sub_label(X_G - 12, (GATE_Y + GND) / 2 + 4, "R", "G2", right=True)
    sc.text(X_G - 12, (GATE_Y + GND) / 2 - 8, _resistor_text(mod, "G2"), size=7.5, color=COMP, right=True)
    sc.dot(X_G, GATE_Y)
    sc.dot(X_G, VDD_Y)
    sc.dot(X_G, GND)

    # transistor
    d_y, s_y = sc.nmos(X_G, GATE_Y, X_MOS - 18, X_MOS)
    sc.text(X_MOS + 8, GATE_Y - 3, "Q", size=9, bold=True)
    sc.text(X_MOS + 16, GATE_Y - 3, "ZVN2106", size=7, color=MUTED)

    # drain resistor
    DRAIN_Y = 222
    sc.wire((X_MOS, d_y), (X_MOS, DRAIN_Y))
    sc.resistor_v(X_MOS, VDD_Y, DRAIN_Y, body=36)
    sc.sub_label(X_MOS + 12, (VDD_Y + DRAIN_Y) / 2 + 4, "R", "D")
    sc.text(X_MOS + 12, (VDD_Y + DRAIN_Y) / 2 - 8, _resistor_text(mod, "D"), size=7.5, color=COMP)
    sc.dot(X_MOS, VDD_Y)
    sc.dot(X_MOS, DRAIN_Y)

    # source resistors and bypass cap
    SRC_Y = 122
    sc.wire((X_MOS, s_y), (X_MOS, SRC_Y))
    sc.resistor_v(X_MOS, SRC_Y, MID_Y, body=30)
    sc.sub_label(X_MOS - 12, (SRC_Y + MID_Y) / 2 + 4, "R", "S1", right=True)
    sc.text(X_MOS - 12, (SRC_Y + MID_Y) / 2 - 8, _resistor_text(mod, "S1"), size=7.5, color=COMP, right=True)
    sc.resistor_v(X_MOS, MID_Y, GND, body=28)
    sc.sub_label(X_MOS - 12, (MID_Y + GND) / 2 + 4, "R", "S2", right=True)
    sc.text(X_MOS - 12, (MID_Y + GND) / 2 - 8, _resistor_text(mod, "S2"), size=7.5, color=COMP, right=True)
    sc.dot(X_MOS, SRC_Y)
    sc.dot(X_MOS, MID_Y)
    sc.dot(X_MOS, GND)

    sc.wire((X_MOS, MID_Y), (X_CBY, MID_Y))
    sc.cap_v(X_CBY, MID_Y, GND)
    sc.dot(X_CBY, GND)
    sc.sub_label(X_CBY + 15, (MID_Y + GND) / 2 + 4, "C", "by1")
    sc.text(X_CBY + 15, (MID_Y + GND) / 2 - 8, _si(mod.get_c("by"), "F"), size=7.5, color=COMP)

    # output coupling + load
    sc.wire((X_MOS, DRAIN_Y), (X_OUT - 25, DRAIN_Y))
    sc.cap_h(X_OUT - 25, X_OUT + 15, DRAIN_Y)
    sc.wire((X_OUT + 15, DRAIN_Y), (X_RL, DRAIN_Y))
    sc.sub_label(X_OUT - 13, DRAIN_Y + 18, "C", "c2")
    sc.resistor_v(X_RL, DRAIN_Y, GND)
    sc.sub_label(X_RL + 12, (DRAIN_Y + GND) / 2 + 4, "R", "Load")
    sc.text(X_RL + 12, (DRAIN_Y + GND) / 2 - 8, _ohms(spec.CS_RL(exact=True)), size=7.5, color=COMP)
    sc.dot(X_RL, GND)
    sc.text(X_RL - 14, DRAIN_Y - 22, "+", size=9)
    sc.text(X_RL - 14, GND + 12, "−", size=9)
    sc.sub_label(X_RL - 32, (DRAIN_Y + GND) / 2 - 2, "v", "o")

    # operating point annotations from analyzeCSAmpModel
    if an is not None:
        sc.text(X_G + 6, GATE_Y + 8, "VG = " + _si(an["VG"], "V"), size=7.5, color=NODE)
        sc.text(X_MOS + 8, DRAIN_Y - 12, "VD = " + _si(an["VD"], "V"), size=7.5, color=NODE)
        sc.text(X_MOS + 8, SRC_Y + 3, "VS = " + _si(an["VS"], "V"), size=7.5, color=NODE)
        sc.text(X_MOS - 12, DRAIN_Y + 10, "ID = " + _si(an["ID"], "A") + " ↓", size=7.5, color=NODE, right=True)

    # legend
    lx = X_FG - 32
    sc.text(lx, -6, "■", size=8, color=COMP)
    sc.text(lx + 9, -6, "component values (from Circuit_Sol)", size=7, color=MUTED)
    sc.text(lx + 175, -6, "■", size=8, color=NODE)
    sc.text(lx + 184, -6, "DC operating point (from analyzeCSAmpModel)", size=7, color=MUTED)
    sc.text(lx + 385, -6, "Cc2 value not part of model", size=7, color=MUTED)


# ---------------------------------------------------------------- tables

def _table_style(n_rows):
    style = [
        ("FONT", (0, 0), (-1, -1), FONT, 8),
        ("FONT", (0, 0), (-1, 0), FONT_BOLD, 8),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
        ("TOPPADDING", (0, 0), (-1, -1), 1.7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.7),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    for r in range(2, n_rows, 2):
        style.append(("BACKGROUND", (0, r), (-1, r), colors.HexColor("#f8fafc")))
    style.append(("LINEBELOW", (0, n_rows - 1), (-1, n_rows - 1), 0.5, RULE))
    return style


def _analysis_table(an, mc, width):
    """Nominal values, plus Monte Carlo min/max columns when mc is given."""
    if an is None:
        rows = [["Quantity", "Value"], ["analyzeCSAmpModel returned None", "invalid design"]]
        t = Table(rows, colWidths=[width * 0.62, width * 0.38])
        t.setStyle(TableStyle(_table_style(len(rows))))
        return t

    if mc is None:
        rows = [["Quantity", "Nominal"]]
        for key, val in an.items():
            label = _ANALYSIS_LABELS.get(key, (key, ""))[0]
            rows.append([_label_para(label), _fmt_analysis_value(key, val)])
        widths = [width * 0.62, width * 0.38]
    else:
        rows = [["Quantity", "Nominal", "MC min", "MC max"]]
        for key, val in an.items():
            label = _ANALYSIS_LABELS.get(key, (key, ""))[0]
            lo, hi = mc["ranges"].get(key, (None, None))
            rows.append([_label_para(label), _fmt_analysis_value(key, val),
                         _fmt_analysis_value(key, lo), _fmt_analysis_value(key, hi)])
        widths = [width * 0.40, width * 0.20, width * 0.20, width * 0.20]
    t = Table(rows, colWidths=widths)
    t.setStyle(TableStyle(_table_style(len(rows))))
    return t


def _mc_table(mc, width):
    rows = [
        ["Monte Carlo", ""],
        ["Analysis samples", f"{mc['n']}  (invalid: {mc['invalid']})"],
        ["Meets req pass rate", f"{100 * mc['pass_rate']:.1f} %"],
        ["scoreCSAmpModel mean", f"{mc['score_mean']:.4f}"],
        ["scoreCSAmpModel min / max", f"{mc['score_min']:.4f} / {mc['score_max']:.4f}"],
        ["Deviation σ (parts / FET)", _deviation_text()],
        ["Reps per score", f"{spec.MONTE_CARLO_REPS}"],
    ]
    t = Table(rows, colWidths=[width * 0.48, width * 0.52])
    style = _table_style(len(rows)) + [("SPAN", (0, 0), (-1, 0))]
    color = GOOD if mc["pass_rate"] >= 0.95 else (WARN if mc["pass_rate"] >= 0.8 else BAD)
    style.append(("TEXTCOLOR", (1, 2), (1, 2), color))
    t.setStyle(TableStyle(style))
    return t


def _deviation_text():
    """Whatever standard deviations specs.py defines, e.g. '2 % / 5 %'."""
    parts = [getattr(spec, name) for name in ("COMP_DEV_PERC_STDEV", "TRANS_DEV_PERC_STDEV") if hasattr(spec, name)]
    return " / ".join(f"{100 * v:g} %" for v in parts) if parts else "-"


@contextmanager
def _monte_carlo(enabled):
    """Temporarily set spec.USE_MONTE_CARLO, restoring the caller's setting afterwards."""
    saved = spec.USE_MONTE_CARLO
    spec.USE_MONTE_CARLO = enabled
    try:
        yield
    finally:
        spec.USE_MONTE_CARLO = saved


def _collect_monte_carlo(mod):
    """Call the student's functions repeatedly with Monte Carlo on and record what they return."""
    ranges = {}
    invalid = 0
    passes = 0
    with _monte_carlo(True):
        for _ in range(MC_SAMPLES):
            an = analyzeCSAmpModel(mod)
            if an is None:
                invalid += 1
            else:
                for key, val in an.items():
                    lo, hi = ranges.get(key, (val, val))
                    ranges[key] = (min(lo, val), max(hi, val))
            bdown = CSAmpModelScoreBreakdown(mod)
            if bdown.get("Meets req", (0, 0))[0] == 1:
                passes += 1
        scores = [scoreCSAmpModel(mod) for _ in range(MC_SCORE_SAMPLES)]
    return {
        "n": MC_SAMPLES,
        "invalid": invalid,
        "ranges": ranges,
        "pass_rate": passes / MC_SAMPLES,
        "score_mean": sum(scores) / len(scores),
        "score_min": min(scores),
        "score_max": max(scores),
    }


def _score_table(bdown, total, width):
    rows = [["Category", "Score", "Weight"]]
    style_extra = []
    for i, (cat, (s, w)) in enumerate(bdown.items(), start=1):
        rows.append([cat, f"{s:.4f}", f"{w:g}"])
        frac = s / w if w else s   # weighted terms are colored by their fraction of the weight
        color = GOOD if frac >= 0.9 else (WARN if frac >= 0.5 else BAD)
        style_extra.append(("TEXTCOLOR", (1, i), (1, i), color))
    n = len(rows)
    rows.append(["Total (nominal)", f"{total:.4f}", ""])
    t = Table(rows, colWidths=[width * 0.58, width * 0.24, width * 0.18])
    style = _table_style(n) + style_extra + [
        ("FONT", (0, n), (-1, n), FONT_BOLD, 8.5),
        ("LINEABOVE", (0, n), (-1, n), 0.8, INK),
        ("TOPPADDING", (0, n), (-1, n), 4),
    ]
    t.setStyle(TableStyle(style))
    return t


# ---------------------------------------------------------------- public entry point

def renderCSAmpReport(mod, path):
    """Write a one-page PDF: schematic on top, analysis + score breakdown below."""
    # Nominal values (Monte Carlo off), so the schematic and tables show the design as drawn.
    with _monte_carlo(False):
        an = analyzeCSAmpModel(mod)
        bdown = CSAmpModelScoreBreakdown(mod)
        total = scoreCSAmpModel(mod)

    mc = _collect_monte_carlo(mod) if spec.USE_MONTE_CARLO else None

    page_w, page_h = letter
    margin = 40
    c = canvas.Canvas(path, pagesize=letter)
    c.setTitle("CS Amplifier Design Report")

    # header
    c.setFillColor(INK)
    c.setFont(FONT_BOLD, 15)
    c.drawString(margin, page_h - margin - 6, "Common-Source Stage — Optimized Design")
    c.setFont(FONT, 8.5)
    c.setFillColor(MUTED)
    c.drawString(margin, page_h - margin - 20,
                 "ECE321 Lab 3 · generated " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    c.setFont(FONT_BOLD, 10)
    c.setFillColor(GOOD if total >= 0.9 else (WARN if total >= 0.5 else BAD))
    c.drawRightString(page_w - margin, page_h - margin - 6, f"Nominal score {total:.4f}")
    if mc is not None:
        c.setFont(FONT, 8.5)
        c.setFillColor(MUTED)
        c.drawRightString(page_w - margin, page_h - margin - 20,
                          f"Monte Carlo mean {mc['score_mean']:.4f} · pass rate {100 * mc['pass_rate']:.0f} %")
    c.setStrokeColor(RULE)
    c.setLineWidth(0.8)
    c.line(margin, page_h - margin - 28, page_w - margin, page_h - margin - 28)

    # schematic (schematic units: x 0..~540, y -10..~310)
    _draw_cs_schematic(c, mod, an, ox=margin + 20, oy=page_h - 392, scale=0.92)

    c.setStrokeColor(RULE)
    c.line(margin, page_h - 410, page_w - margin, page_h - 410)

    # tables: analysis on the left (wider when it has Monte Carlo columns), scores on the right
    gutter = 16
    usable = page_w - 2 * margin - gutter
    left_w = usable * (0.58 if mc is not None else 0.5)
    right_w = usable - left_w
    right_x = margin + left_w + gutter
    top = page_h - 424

    c.setFillColor(INK)
    c.setFont(FONT_BOLD, 10)
    c.drawString(margin, top, "Analyzed values")
    c.drawString(right_x, top, "Score breakdown (nominal)")

    t1 = _analysis_table(an, mc, left_w)
    _, h1 = t1.wrapOn(c, left_w, top)
    t1.drawOn(c, margin, top - 8 - h1)

    t2 = _score_table(bdown, total, right_w)
    _, h2 = t2.wrapOn(c, right_w, top)
    t2.drawOn(c, right_x, top - 8 - h2)

    if mc is not None:
        t3 = _mc_table(mc, right_w)
        _, h3 = t3.wrapOn(c, right_w, top)
        t3.drawOn(c, right_x, top - 8 - h2 - 10 - h3)

    c.setFont(FONT, 7)
    c.setFillColor(MUTED)
    c.drawString(margin, margin - 22,
                 "All values computed by the student's analyzeCSAmpModel / CSAmpModelScoreBreakdown; "
                 "this report only renders them.")

    c.showPage()
    c.save()
    print("Report written to " + os.path.abspath(path))
