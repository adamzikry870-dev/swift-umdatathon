"""Build the 17-slide submission deck (16:9), as PDF and as editable PPTX.

    python deck/build_deck.py             -> PDF + PPTX
    python deck/build_deck.py --preview   -> also writes deck/preview/sNN.png

Every slide is drawn once, on a canvas measured in inches.  Each drawing call
is also recorded as an operation, so the PPTX renderer can replay the same
layout with native text boxes, native shapes and the charts lifted from the
vector PDF at 300 dpi.  Text stays editable in PowerPoint; charts are pictures.
"""
import os
import sys
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Rectangle, FancyBboxPatch
from matplotlib.ticker import FuncFormatter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D1 = os.path.join(ROOT, "dashboard", "data")
D2 = os.path.join(ROOT, "deck", "data")
OUT_PDF = os.path.join(ROOT, "deck", "UM_Datathon_2026_Swift_Deck.pdf")
OUT_PPTX = os.path.join(ROOT, "deck", "UM_Datathon_2026_Swift_Deck.pptx")
PREVIEW = os.path.join(ROOT, "deck", "preview")

W, H = 13.333, 7.5
M = 0.62
RIGHT = W - 0.62

# --- palette: deliberately away from the case-study brand's blue ------------
PLUM = "#5b2a3d"
PLUM_SOFT = "#eadfe4"
OCHRE = "#a9762f"
OCHRE_SOFT = "#f6ebdc"
INK = "#1d1d1b"
BODY = "#3a3a37"
MUTED = "#6c6c67"
FAINT = "#9b9b94"
RULE = "#e2ded7"
TINT = "#f6f3ef"
WHITE = "#ffffff"

SANS = "Segoe UI"

plt.rcParams.update({
    "font.family": SANS,
    "font.size": 10,
    "axes.edgecolor": RULE,
    "axes.labelcolor": MUTED,
    "axes.titlecolor": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.grid": True,
    "grid.color": "#ece7e1",
    "grid.linewidth": 0.9,
    "axes.axisbelow": True,
    "figure.facecolor": WHITE,
    "savefig.facecolor": WHITE,
})

A = None
OPS = []
PAGES = []


# --------------------------------------------------------------- primitives
def load(name):
    for d in (D2, D1):
        p = os.path.join(d, name)
        if os.path.exists(p):
            return pd.read_csv(p)
    raise FileNotFoundError(name)


def fx(x):
    return x / W


def fy(y):
    return y / H


def new_slide():
    global A, OPS
    fig = plt.figure(figsize=(W, H))
    fig.patch.set_facecolor(WHITE)
    A = fig.add_axes([0, 0, 1, 1])
    A.set_xlim(0, W)
    A.set_ylim(0, H)
    A.set_axis_off()
    A.set_zorder(0)
    OPS = []
    return fig


def T(x, y, s, size=10, color=BODY, weight="normal", ha="left", va="top",
      ls=1.2, style="normal"):
    A.text(x, y, s, fontsize=size, color=color, fontweight=weight, ha=ha,
           va=va, linespacing=ls, style=style, zorder=3)
    OPS.append(dict(kind="text", x=x, y=y, s=s, size=size, color=color,
                    weight=weight, ha=ha, va=va, ls=ls))


def box(x, y, w, h, fill, edge=None, r=0.0, lw=0.9):
    if r:
        A.add_patch(FancyBboxPatch((x, y), w, h,
                                   boxstyle=f"round,pad=0,rounding_size={r}",
                                   facecolor=fill, edgecolor=edge or "none",
                                   lw=lw, zorder=1))
    else:
        A.add_patch(Rectangle((x, y), w, h, facecolor=fill,
                              edgecolor=edge or "none", lw=lw, zorder=1))
    OPS.append(dict(kind="rect", x=x, y=y, w=w, h=h, fill=fill,
                    edge=edge, r=r))


def hline(x0, x1, y, color=RULE, lw=1.0, style="-"):
    A.plot([x0, x1], [y, y], color=color, lw=lw, ls=style,
           solid_capstyle="butt", zorder=2)
    OPS.append(dict(kind="line", x0=x0, x1=x1, y=y, color=color, lw=lw))


def chart(box_):
    x, y, w, h = box_
    ax = A.figure.add_axes([fx(x), fy(y), fx(w), fy(h)])
    ax.set_facecolor("none")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(RULE)
    ax.spines["bottom"].set_color(RULE)
    ax.tick_params(labelsize=9)
    OPS.append(dict(kind="chart", box=box_, ax=ax))
    return ax


def kicker(text, y=7.03):
    T(M, y, text.upper(), size=8.6, color=PLUM, weight="bold", va="center")


def headline(text, size=24.5, y=6.84, width=74):
    T(M, y, "\n".join(textwrap.wrap(text, width=width)), size=size,
      color=INK, weight="bold", ls=1.12)


def footer(n, total=17):
    T(M, 0.26, "UM Datathon 2026  ·  Swift case study", size=8, color=FAINT,
      va="center")
    T(RIGHT, 0.26, f"{n:02d} / {total}", size=8.5, color=MUTED, va="center",
      ha="right", weight="bold")


def strip(text, label="What this means in the real economy", y=1.54, base=0.50):
    box(0, base, W, y - base, TINT)
    box(M, base + 0.10, 0.045, (y - base) - 0.20, PLUM)
    T(M + 0.18, y - 0.26, label.upper(), size=8, color=PLUM, weight="bold",
      va="center")
    T(M + 0.18, y - 0.46, textwrap.fill(text, 162), size=10, color=BODY,
      ls=1.34)


def caption(text, y=5.80, x=5.95):
    T(x, y, text, size=8.3, color=FAINT, va="bottom", style="italic")


def stat(x, y, value, label, color=PLUM, width=24, size=23):
    T(x, y, value, size=size, color=color, weight="bold", va="baseline")
    T(x, y - 0.30, textwrap.fill(label, width), size=8.4, color=MUTED)


def para(x, y, text, size=12.0, width=58, color=BODY, lh=1.5):
    T(x, y, textwrap.fill(text, width=width), size=size, color=color, ls=lh)


def money(v):
    if v >= 1e9:
        return f"${v/1e9:.1f}bn"
    if v >= 1e6:
        return f"${v/1e6:.1f}M"
    if v >= 1e3:
        return f"${v/1e3:.0f}k"
    return f"${v:.0f}"


def save(fig, pdf, n):
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    inv = fig.transFigure.inverted()
    for o in OPS:
        ax = o.get("ax")
        if o["kind"] != "chart" or ax is None:
            continue
        bb = ax.get_tightbbox(rend)
        fx0, fy0 = inv.transform((bb.x0, bb.y0))
        fx1, fy1 = inv.transform((bb.x1, bb.y1))
        x0 = max(0.0, fx0 * W)
        y0 = max(0.0, fy0 * H)
        x1 = min(W, fx1 * W)
        y1 = min(H, fy1 * H)
        o["crop"] = (x0, y0, x1 - x0, y1 - y0)
    pdf.savefig(fig)
    PAGES.append(list(OPS))
    if "--preview" in sys.argv:
        os.makedirs(PREVIEW, exist_ok=True)
        fig.savefig(os.path.join(PREVIEW, f"s{n:02d}.png"), dpi=100)
    plt.close(fig)


# ------------------------------------------------------------------- data
daily = load("daily_volume.csv")
daily["date"] = pd.to_datetime(daily["date"]).dt.tz_localize(None)
tmpl = load("g1_template.csv")
loc_share = load("g2_country_local.csv")
ladder = load("g3_ladder.csv").sort_values("mu").reset_index(drop=True)
bc = load("g4_bc_countries.csv")
pairs = load("participants_by_type.csv")
dur = load("g6_length.csv")
dur_amt = load("g6_amount_by_len.csv")
conc = load("g7_sender_conc.csv")
anom = load("anomaly_by_beneficiary_country.csv")
fmt_pairs = load("amount_pair_stats.csv")

TOTAL_SENDERS = 390_725

pdf = PdfPages(OUT_PDF)
n = 0

# ============================================================ 01 · title
n += 1
fig = new_slide()
box(0, 0, 0.22, H, PLUM)
kicker("Universiti Malaya UMDAC Datathon 2026  ·  Swift case study", 6.95)
T(M, 6.24, "The rulebook behind", size=44, color=INK, weight="bold", va="top")
T(M, 5.44, "ten million payments", size=44, color=PLUM, weight="bold", va="top")
hline(M, M + 2.2, 4.70, OCHRE, 3.2)
T(M, 4.34, textwrap.fill(
    "What one synthetic SWIFT payment file reveals about ticket size, routing, "
    "settlement speed and fraud, and the method that proved it.", 62),
  size=14.5, color=BODY, ls=1.5)

ax = plt.gcf().add_axes([fx(8.35), fy(2.05), fx(4.4), fy(2.9)])
ax.set_axis_off()
ax.set_xlim(0, 10)
ax.set_ylim(0, 6)
xs = [0.9, 3.2, 5.6, 8.0]
ys = [3.7, 1.7, 3.7, 1.7]
for i in range(3):
    ax.plot([xs[i], xs[i + 1]], [ys[i], ys[i + 1]], color=PLUM_SOFT, lw=2.0,
            solid_capstyle="round", zorder=1)
for i, (x, y) in enumerate(zip(xs, ys)):
    ax.scatter([x], [y], s=190 if i in (0, 3) else 130,
               color=PLUM if i in (0, 3) else "white",
               edgecolor=PLUM, linewidth=1.8, zorder=2)
ax.text(0.9, 4.75, "payer", fontsize=9, color=MUTED, ha="center")
ax.text(8.0, 0.85, "payee", fontsize=9, color=MUTED, ha="center")
ax.text(5.6, 4.75, "correspondents", fontsize=9, color=MUTED, ha="center")
OPS.append(dict(kind="chart", box=(8.35, 2.05, 4.4, 2.9)))

for i, (v, l) in enumerate([("10.0 M", "payments analysed\nin full"),
                            ("8", "rules that survived\ntesting"),
                            ("3", "claims we withdrew\nafter testing")]):
    stat(M + i * 1.92, 2.72, v, l, color=PLUM if i else INK, width=19, size=21)

T(M, 1.62, "17 slides  ·  8 feature groups  ·  every figure recomputed on all 10,000,000 rows",
  size=10, color=MUTED)
T(M, 0.55, "Prepared for submission  ·  No external data was used at any point",
  size=8.5, color=FAINT)
footer(n)
save(fig, pdf, n)

# ============================================================ 02 · the file
n += 1
fig = new_slide()
kicker("The starting point")
headline("One file, ten million payments, no outside data")
hline(M, RIGHT, 6.02)

para(M, 5.88, (
    "We were handed a single file of synthetic SWIFT-like payment messages "
    "covering three months of a payments business. It has twenty fields: who "
    "paid, who was paid, through which banks, in what currency, how much, "
    "when, and how long it took."), size=11.8, width=52)
para(M, 4.34, (
    "A small share of rows carry an exception label. Everything that follows "
    "is derived from that one file. Where we needed a benchmark, we built it "
    "from the file's own controls rather than importing one."),
     size=10.8, width=52, color=MUTED)

stats = [("10.0 M", "payments, 20 fields,\n30 Apr – 31 Jul 2023"),
         ("8,727", "banks across\n229 country codes"),
         ("155", "currencies in use,\nnot one rate table")]
for i, (v, l) in enumerate(stats):
    stat(M + i * 1.74, 3.12, v, l, color=INK, width=21)

T(M, 1.86, "TWENTY FIELDS, FIVE ROLES", size=8.2, color=PLUM, weight="bold",
  va="center")
roles = [("2", "when"), ("2", "how much"), ("7", "route"), ("8", "who"), ("1", "label")]
for i, (k, v) in enumerate(roles):
    x = M + i * 1.00
    box(x, 1.10, 0.94, 0.62, WHITE, RULE, r=0.05)
    T(x + 0.10, 1.55, k, size=14, color=PLUM, weight="bold", va="center")
    T(x + 0.10, 1.27, v, size=8.4, color=MUTED, va="center")

ax = chart((5.95, 1.25, 6.78, 4.40))
ax.plot(daily.date, daily.n / 1000, color=PLUM, lw=1.9)
ax.fill_between(daily.date, daily.n / 1000, color=PLUM, alpha=0.10)
wk = daily.dow.isin([5, 6])
ax.scatter(daily.date[wk], daily.n[wk] / 1000, s=16, color=OCHRE, zorder=3,
           label="Saturday / Sunday")
peak = daily.loc[daily.n.idxmax()]
ax.annotate(f"19–26 June surge: {peak.n/1000:.0f}k payments a day",
            xy=(peak.date, peak.n / 1000),
            xytext=(0.36, 0.985), textcoords="axes fraction",
            fontsize=8.8, color=OCHRE, ha="left", va="top")
ax.set_ylabel("payments per day (thousands)")
ax.set_ylim(0, 250)
ax.set_xlim(daily.date.min(), daily.date.max())
ax.legend(loc="lower left", frameon=False, fontsize=9, labelcolor=MUTED)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
caption("Daily volume, 30 Apr – 31 Jul 2023. Weekdays hold 131–141k; weekends fall to a third of that.")
footer(n)
save(fig, pdf, n)

# ============================================================ 03 · eight rules
n += 1
fig = new_slide()
kicker("The answer in one page")
headline("Eight rules explain the whole file")
hline(M, RIGHT, 6.02)
T(M, 5.76, "Each feature group reduces to one mechanism, and each mechanism is a business rule with a number attached.",
  size=10.8, color=MUTED, va="top")

rules = [
    ("01  When payments happen", "Each country runs the same working-day template on its own whole-hour clock."),
    ("02  Which currency", "The payer chooses its own currency: 93.4% of payments stay at home."),
    ("03  How much", "One amount shape everywhere; the centre is set by the payer's market, a 650× ladder."),
    ("04  Through which banks", "A fixed bank code, a 7.3× corporate premium, and a stable per-bank tilt."),
    ("05  How long the chain", "63% use two banks; each extra bank is 37% as likely as the last."),
    ("06  How long it takes", "Duration is the sum of the legs; currency and hidden hops add nothing."),
    ("07  Who is paying whom", "390k senders carry the volume; 2.6M beneficiaries are effectively one-off."),
    ("08  What goes wrong", "Six exception labels, six mechanisms, and a strong country pattern."),
]
x0, y0 = M, 5.20
cw, ch = 6.02, 0.98
for i, (k, t) in enumerate(rules):
    col, row = i % 2, i // 2
    x = x0 + col * (cw + 0.14)
    y = y0 - row * (ch + 0.08) - ch
    box(x, y, cw, ch, TINT if i % 2 == 0 else WHITE, RULE, r=0.06)
    T(x + 0.18, y + ch - 0.22, k.upper(), size=7.8, color=PLUM, weight="bold",
      va="center")
    T(x + 0.18, y + ch - 0.48, textwrap.fill(t, 66), size=10.2, color=INK,
      ls=1.35)
T(M, 0.66, "Three earlier claims were corrected or withdrawn on slide 7. The rules on this page are the replacements.",
  size=9.6, color=OCHRE, va="center", weight="bold")
footer(n)
save(fig, pdf, n)

# ============================================================ 04 · method 1
n += 1
fig = new_slide()
kicker("Methodology  ·  1 of 4")
headline("How we test a rule")
hline(M, RIGHT, 6.02)
T(M, 5.80, "Four tests, applied to every one of the eight rules. A rule we could not pass all four is not on the deck.",
  size=11, color=MUTED, va="top")

steps = [
    ("Full data", "The population is the file. No sample, so no confidence interval is needed."),
    ("A control", "Hold the country, corridor or chain fixed and check the effect survives."),
    ("Replication", "Recover the same number from two disjoint halves of the rows."),
    ("Scope", "State where the rule applies, and where it stops."),
]
bw, bh = 2.95, 1.12
for i, (t, body) in enumerate(steps):
    x = M + i * (bw + 0.10)
    box(x, 4.28, bw, bh, TINT, None, r=0.06)
    T(x + 0.16, 5.22, f"{i+1}  " + t.upper(), size=8.2, color=PLUM, weight="bold",
      va="center")
    T(x + 0.16, 4.98, textwrap.fill(body, 40), size=9.2, color=BODY, ls=1.35)

T(M, 3.98, "WORKED EXAMPLE  ·  THE 7.3× CLIENT PREMIUM", size=8.2, color=PLUM,
  weight="bold", va="center")
worked = [
    ("Raw split", "Business median is 7.3× the retail median (0.865 in log amount) across 167 markets."),
    ("Control", "Positive in 167 of 167 markets; 101 sit inside 0.80–0.95; the range is 0.52 to 1.18."),
    ("Replication", "0.869 and 0.861 in two halves of the rows; country-level r = 0.75."),
    ("Scope", "49× when both ends are business. The gap belongs to the market, not to the corridor."),
]
yy = 3.62
for t, body in worked:
    T(M, yy, t, size=9.4, color=INK, weight="bold", va="top")
    T(M + 1.12, yy, textwrap.fill(body, 66), size=9.4, color=BODY, va="top", ls=1.35)
    yy -= 0.66

box(6.95, 1.55, RIGHT - 6.95, 2.34, WHITE, RULE, r=0.06)
T(7.15, 3.66, "TOOLS AND DATA", size=8.2, color=PLUM, weight="bold", va="center")
T(7.15, 3.42, textwrap.fill(
    "One supplied file of 10,000,000 rows, read in full with Python and DuckDB; "
    "charts in matplotlib. Queries and build scripts accompany the submission, "
    "so every figure on these slides can be recomputed from the file alone.", 58),
  size=9.4, color=BODY, ls=1.4)
T(7.15, 2.42, "WHAT WE DELIBERATELY DID NOT DO", size=8.2, color=OCHRE,
  weight="bold", va="center")
for i, t in enumerate(["No external data of any kind.",
                       "No sample, no synthetic top-up, no imputed value.",
                       "No model fitted before the rule was stated."]):
    T(7.15, 2.18 - i * 0.24, "·", size=9.4, color=OCHRE, va="center")
    T(7.32, 2.18 - i * 0.24, t, size=9.4, color=BODY, va="center")
footer(n)
save(fig, pdf, n)

# ============================================================ 05 · method 2
n += 1
fig = new_slide()
kicker("Methodology  ·  2 of 4")
headline("The questions we set, and what would have shown us we were wrong")
hline(M, RIGHT, 6.02)

T(M, 5.74, "FEATURE GROUP", size=7.8, color=MUTED, weight="bold", va="center")
T(M + 1.72, 5.74, "THE QUESTION", size=7.8, color=MUTED, weight="bold", va="center")
T(M + 5.66, 5.74, "WHAT WOULD HAVE REFUTED IT", size=7.8, color=MUTED,
  weight="bold", va="center")

questions = [
    ("When payments happen", "Do countries share one clock, or many?",
     "Country curves would fail to align under any single whole-hour shift."),
    ("Which currency", "Does the payer choose the currency, or the corridor?",
     "Local share would track the destination rather than the sending bank."),
    ("How much", "Is the ticket set by the deal, or by the payer's market?",
     "Country medians would be flat, and would not reproduce across halves."),
    ("Through which banks", "Is the 7.3× premium a client effect or a country effect?",
     "The gap would vanish once each market is measured on its own."),
    ("How long the chain", "Is chain length policy, a queue, or a geometric draw?",
     "The decay would break at some length, or drift with daily volume."),
    ("How long it takes", "Is duration the chain, the money, or the corridor?",
     "Duration would rise with amount at a fixed chain length."),
    ("Who is paying whom", "Does the payee's address carry information?",
     "It would agree with the payee's bank more often than chance."),
    ("What goes wrong", "Do labels mutate fields, or describe populations?",
     "Labelled rows would differ across all twenty fields, not a chosen few."),
]
yy = 5.36
for i, (g, q, r) in enumerate(questions):
    if i % 2 == 0:
        box(M - 0.10, yy - 0.49, RIGHT - M + 0.20, 0.47, TINT)
    T(M, yy - 0.02, g, size=8.8, color=INK, weight="bold", va="top")
    T(M + 1.72, yy - 0.02, textwrap.fill(q, 54), size=8.8, color=BODY, va="top", ls=1.25)
    T(M + 5.66, yy - 0.02, textwrap.fill(r, 60), size=8.8, color=MUTED, va="top", ls=1.25)
    yy -= 0.56
footer(n)
save(fig, pdf, n)

# ============================================================ 06 · method 3
n += 1
fig = new_slide()
kicker("Methodology  ·  3 of 4")
headline("Data preparation: six decisions, and what each one cost")
hline(M, RIGHT, 6.02)
T(M, 5.76, "Nothing was removed without a reason, and each decision is stated here so a reader can see which findings depend on it.",
  size=10.6, color=MUTED, va="top")

T(M, 5.22, "WHAT WE FOUND", size=7.8, color=MUTED, weight="bold", va="center")
T(M + 4.20, 5.22, "DECISION", size=7.8, color=MUTED, weight="bold", va="center")
T(M + 7.60, 5.22, "EFFECT ON THE RESULTS", size=7.8, color=MUTED, weight="bold",
  va="center")

issues = [
    ("No missing values in 19 of 20 fields; only the exception label is empty (99.93%).",
     "Treat a blank label as ordinary traffic.",
     "Clean base of 9,992,994 rows, used for every rule."),
    ("7,006 rows carry an injected exception label (0.07%).",
     "Analyse them separately; exclude from rule-fitting.",
     "Rules describe clean traffic, not the injected tail."),
    ("The ordering bank field disagrees with the first bank on the route in 498,399 rows (4.98%).",
     "Read the sender from the route's first bank, not the ordering field.",
     "Local-currency share moves from 89.4% to 93.4%."),
    ("Timestamps form 18 whole-hour clocks, not 24 real time zones.",
     "Never convert to a global clock; align each country to its own peak.",
     "Cross-country agreement rises from 0.19 to 0.99."),
    ("One amount column, already in a common unit, and no local-currency value.",
     "No exchange rate can be recovered; do not model conversion as a price.",
     "Retires the daily-rate-table hypothesis outright."),
    ("679 rows repeat another payment's sender, payee, amount and currency.",
     "Keep them. They are mutations, not input errors.",
     "Duplication becomes a rule, not a cleaning step."),
]
yy = 4.90
for i, (a, b, c) in enumerate(issues):
    if i % 2 == 0:
        box(M - 0.10, yy - 0.50, RIGHT - M + 0.20, 0.48, TINT)
    T(M, yy - 0.06, textwrap.fill(a, 62), size=8.6, color=INK, va="top", ls=1.25)
    T(M + 4.20, yy - 0.06, textwrap.fill(b, 54), size=8.6, color=BODY, va="top", ls=1.25)
    T(M + 7.60, yy - 0.06, textwrap.fill(c, 46), size=8.6, color=MUTED, va="top", ls=1.25)
    yy -= 0.63
footer(n)
save(fig, pdf, n)

# ============================================================ 07 · method 4
n += 1
fig = new_slide()
kicker("Methodology  ·  4 of 4")
headline("Three claims we published, tested and withdrew")
hline(M, RIGHT, 6.02)
T(M, 5.76, "The retraction is the strongest evidence in the pack: we found the error, measured it, and replaced it with a number we can defend.",
  size=10.8, color=OCHRE, va="top")

rows = [
    ("Daily FX rate table\nwith a weekend freeze",
     "Refuted. The file holds one amount column, already converted to a common unit, so no rate can be computed at all. There is nothing to freeze at the weekend.",
     "Now · one amount per payment, no rate anywhere in the row."),
    ("“89.4% of payments\nstay in local currency”",
     "Corrected. That figure came from the ordering-bank column, which disagrees with the route on 4.98% of rows. Reading the true sending bank gives 93.4%.",
     "Now · 93.4% weighted, and no market below 73%."),
    ("“Real UTC time zones”",
     "Refuted. There are 18 whole-hour clocks, not 24 time zones. Half-hour zones such as India land 30 minutes out, and the ±1-hour ties are exact.",
     "Now · 18 whole-hour clocks, each aligned to its own peak."),
]
yy = 5.40
for i, (a, b, c) in enumerate(rows):
    box(M, yy - 1.05, RIGHT - M, 1.05, OCHRE_SOFT if i == 1 else TINT, None, r=0.05)
    T(M + 0.20, yy - 0.19, a, size=9.8, color=INK, weight="bold", va="top", ls=1.28)
    T(M + 2.95, yy - 0.19, textwrap.fill(b, 74), size=9.2, color=BODY, va="top",
      ls=1.36)
    T(M + 8.30, yy - 0.19, textwrap.fill(c, 44), size=8.6, color=OCHRE, va="top",
      ls=1.36)
    yy -= 1.14

box(M, 1.12, RIGHT - M, 0.76, WHITE, RULE, r=0.05)
T(M + 0.20, 1.68, "WHAT SURVIVED UNCHANGED", size=8.2, color=PLUM, weight="bold",
  va="center")
T(M + 0.20, 1.40, "The 650× country ladder (0.998 across two halves) and the 37% chain decay "
  "(holds at every length).", size=9.4, color=BODY, va="center")
footer(n)
save(fig, pdf, n)

# ============================================================ 08 · g1 time
n += 1
fig = new_slide()
kicker("Group 1 of 8  ·  When payments happen")
headline("Payments follow the sun, not a global clock")
hline(M, RIGHT, 6.02)
para(M, 5.78, (
    "Each country runs the same working-day template: a sharp morning peak and "
    "a second hump after lunch, stamped on its own whole-hour clock. Read on a "
    "single global clock the 113 country curves agree only weakly. Shifted onto "
    "their own hour they collapse onto one shape."), size=11.4, width=50)
stat(M, 3.60, "0.19 → 0.99", "agreement between country curves, before and after alignment", width=22, size=19)
stat(M + 2.00, 3.60, "18", "distinct whole-hour clocks cover 113 countries", width=20)
stat(M + 3.34, 3.60, "11.2%", "of volume arrives at the weekend, against 28.6% if days were equal", width=23)

ax = chart((5.95, 2.06, 6.78, 3.50))
hrs = tmpl.hour.values
ax.fill_between(hrs, 0, tmpl.template * 100, color=PLUM, alpha=0.13)
ax.plot(hrs, tmpl.template * 100, color=PLUM, lw=2.4)
ax.plot(hrs, tmpl.raw_utc * 100, color=FAINT, lw=1.6, ls="--")
for lo, hi in [(-2, 2), (13, 16)]:
    ax.axvspan(lo, hi, color=PLUM, alpha=0.06, lw=0, zorder=0)
ax.set_xlim(-3, 23)
ax.set_ylim(0, 9.4)
ax.set_xticks([0, 3, 6, 9, 12, 15, 18, 21])
ax.set_xlabel("hours from each country's own busiest hour")
ax.set_ylabel("share of payments in that hour (%)")
ax.text(0.2, 8.75, "34% of the day in five hours", fontsize=8.6, color=PLUM,
        va="center", fontweight="bold")
ax.annotate("afternoon\nhump", xy=(14.5, 4.7), xytext=(17.2, 6.7), fontsize=8.6,
            color=PLUM, ha="center",
            arrowprops=dict(arrowstyle="-", color=PLUM, lw=0.9))
caption("Average of 113 country curves after alignment (solid) and the same data on one global clock (dashed).")
strip("Settlement follows local banking hours. A “global peak” is the hour when many local "
      "business days overlap, a treasury clock rather than a market clock. Weekends collapse "
      "because treasuries do not initiate on Saturdays.")
footer(n)
save(fig, pdf, n)

# ============================================================ 09 · g2 currency
n += 1
fig = new_slide()
kicker("Group 2 of 8  ·  Which currency")
headline("Payers pay in their own currency, and there is no FX desk in this file")
hline(M, RIGHT, 6.02)
para(M, 5.78, (
    "The currency is a sender-side choice: 93.4% of payments are denominated in "
    "the home currency of the sending bank. The 6.6% that are foreign lean "
    "heavily to the euro and the dollar. Amounts are already stated in one "
    "common unit, so there is no daily rate table and no conversion leg to "
    "price."), size=11.4, width=50)
stat(M, 3.52, "93.4%", "of payments in the sender bank's home currency", width=21)
stat(M + 1.66, 3.52, "56%", "of the foreign 6.6% are in euros; a further 26% in dollars", width=22)
stat(M + 3.36, 3.52, "0.00", "difference in typical ticket, foreign versus home, market held fixed", width=22)

ax = chart((5.95, 2.06, 6.78, 3.50))
top = loc_share.sort_values("n", ascending=False).head(12).sort_values("local_share")
ypos = np.arange(len(top))
ax.hlines(ypos, 85, top.local_share * 100, color=PLUM_SOFT, lw=1.6, zorder=1)
ax.scatter(top.local_share * 100, ypos, s=46, color=PLUM, zorder=3)
ax.axvline(93.4, color=OCHRE, lw=1.4, ls="--", zorder=2)
ax.text(93.0, len(top) + 0.02, "93.4% average", color=OCHRE, fontsize=8.6,
        va="center", ha="right")
for y, (_, r) in zip(ypos, top.iterrows()):
    ax.text(r.local_share * 100 + 0.45, y, f"{r.local_share*100:.0f}%", color=BODY,
            fontsize=8.6, va="center", ha="left", fontweight="bold",
            bbox=dict(facecolor="white", edgecolor="none", pad=0.6))
ax.set_yticks(ypos)
ax.set_yticklabels(top.cc, fontsize=9.2)
ax.set_xlim(85, 101)
ax.set_ylim(-0.7, len(top) + 0.30)
ax.set_xticks([85, 90, 95, 100])
ax.set_xlabel("share of that country's payments in its own currency (%; axis starts at 85%)")
ax.grid(axis="y", visible=False)
caption("Twelve largest sender markets; across all 113 the share runs 73% to 98%. The line is the 93.4% average.")
strip("A payer books the ticket in its own currency and leaves conversion to the correspondent, so FX "
      "is priced into the amount rather than settled as a separate leg. That is why any “implied rate” "
      "computed from this file is an artefact.")
footer(n)
save(fig, pdf, n)

# ============================================================ 10 · g3 amounts
n += 1
fig = new_slide()
kicker("Group 3 of 8  ·  How much")
headline("Deal size is set by the payer's market, not by the deal itself")
hline(M, RIGHT, 6.02)
para(M, 5.78, (
    "Amounts share one shape in every country: the same spread, the same mild "
    "skew. What moves is the centre. The typical ticket runs from $48 in "
    "Guinea-Bissau to $31,219 in Monaco, and only dollar payments carry a "
    "round-number habit."), size=11.4, width=50)
stat(M, 3.52, "650×", "between the poorest and richest market's typical ticket", width=21)
stat(M + 1.80, 3.52, "0.998", "correlation of the country centre across two halves", width=21)
stat(M + 3.24, 3.52, "38.7%", "of dollar payments are whole dollars, against 1.0% elsewhere", width=22)

ax = chart((5.95, 2.06, 6.78, 3.50))
lad = ladder.sort_values("median_usd").reset_index(drop=True)
rk = np.arange(1, len(lad) + 1)
edge = (rk <= 8) | (rk > len(lad) - 8)
ax.plot(lad.median_usd, rk, color=PLUM_SOFT, lw=1.2, zorder=1)
ax.scatter(lad.median_usd[~edge], rk[~edge], s=10, color=FAINT, alpha=0.60,
           lw=0, zorder=2)
ax.scatter(lad.median_usd[edge], rk[edge], s=26, color=PLUM, lw=0, zorder=3)
ax.set_xscale("log")
ax.set_xlim(30, 60000)
ax.set_ylim(0, len(lad) + 4)
ax.set_xlabel("typical payment in that market (US$, log scale)")
ax.set_ylabel("sender markets, ranked by typical ticket")
ax.grid(axis="y", visible=False)
ax.xaxis.set_major_formatter(FuncFormatter(lambda v, p: money(v)))
caption("All 158 sender markets, ranked by typical ticket. The eight smallest and eight largest are in plum.")
strip("Ticket size tracks the wealth of the payer's market. It is a country dial, not a deal dial, and "
      "the largest single source of variation in the book. The dollar rounding is a human fingerprint: "
      "people round in the currency they think in.")
footer(n)
save(fig, pdf, n)

# ============================================================ 11 · g4 banks
n += 1
fig = new_slide()
kicker("Group 4 of 8  ·  Through which banks, for which client")
headline("Every bank has a fingerprint. Client type is a second dial")
hline(M, RIGHT, 6.02)
para(M, 5.78, (
    "A bank identifier is a rigid eight-slot code: a four-digit number, a "
    "country, a house letter fixed per country, and a constant. Beyond the "
    "country ladder, business payers send 7.3× the retail median in all 167 "
    "measurable markets, and the two ends of a payment stack to 49×."),
    size=11.4, width=50)
stat(M, 3.52, "25.8 M", "bank appearances, zero exceptions to the code layout", width=21)
stat(M + 1.80, 3.52, "7.3×", "corporate over retail median, in 167 of 167 markets", width=21)
stat(M + 3.18, 3.52, "49×", "business-to-business over consumer-to-consumer", width=21)

ax = chart((5.95, 2.06, 6.78, 3.50))
x = bc.retail.values
y = bc.business.values
lim = (2.2, 4.9)
ax.plot(lim, lim, color=FAINT, lw=1.2, ls="--", zorder=1)
ax.annotate("", xy=(2.45, 3.315), xytext=(2.45, 2.45),
            arrowprops=dict(arrowstyle="<->", color=OCHRE, lw=1.3,
                            shrinkA=0, shrinkB=0), zorder=2)
ax.text(2.53, 2.88, "7.3×", color=OCHRE, fontsize=9.5, va="center",
        fontweight="bold")
ax.scatter(x, y, s=22, color=PLUM, alpha=0.55, edgecolor="none", zorder=3)
ax.text(4.14, 3.86, "same ticket\non both sides", color=FAINT, fontsize=8.2,
        ha="center", va="top", linespacing=1.3)
ax.set_xlim(*lim); ax.set_ylim(*lim)
ax.set_xlabel("typical retail ticket in that market (US$, log scale)")
ax.set_ylabel("typical business ticket (US$)")
ticks = [2.5, 3.0, 3.5, 4.0, 4.5]
ax.set_xticks(ticks); ax.set_yticks(ticks)
ax.set_xticklabels([money(10 ** v) for v in ticks])
ax.set_yticklabels([money(10 ** v) for v in ticks])
caption("One dot per market, 167 markets with 300 payments each side; 101 sit inside 0.80–0.95.")
strip("Corporate and retail are two different books: a corporate ticket is about seven times a retail "
      "one in every market, and business-to-business about forty-nine times consumer-to-consumer. "
      "Average ticket says more about client mix than geography.")
footer(n)
save(fig, pdf, n)

# ============================================================ 12 · g5 routing
n += 1
fig = new_slide()
kicker("Group 5 of 8  ·  How long the chain")
headline("Chains grow by a fixed rule, and conversion belongs to the corridor")
hline(M, RIGHT, 6.02)
para(M, 5.78, (
    "63% of payments pass through exactly two banks. Each extra bank is 37% as "
    "likely as the one before, out to twenty-two. A payment converts exactly "
    "when the banks on either side use different currencies, and across 2,338 "
    "country pairs every pair is all or nothing."), size=11.2, width=50)
stat(M, 3.55, "63%", "of payments use two banks; the tail reaches 22", width=21)
stat(M + 1.70, 3.55, "0.368", "the chance of one more bank at every step", width=21)
stat(M + 3.26, 3.55, "0", "country pairs that convert only sometimes", width=21)

T(M, 2.58, "EVERY ONE OF THE 2,338 COUNTRY PAIRS IS ALL-OR-NOTHING",
  size=8.2, color=PLUM, weight="bold", va="center")
box(M, 2.10, 3.54, 0.30, PLUM)
box(M + 3.54, 2.10, 0.36, 0.30, "#ddd6ce")
T(M + 0.14, 2.25, "2,124 pairs always convert", size=8.6, color=WHITE,
  va="center", weight="bold")
T(M + 3.98, 2.25, "214 never do", size=8.6, color=MUTED, va="center")

ax = chart((5.95, 2.06, 6.78, 3.50))
pv = pairs.pivot(index="pc", columns="tt", values="n").fillna(0)
ks = np.array([2, 3, 4, 5, 6, 7, 8, 9])
tot = pv.sum(axis=1)
obs = tot.loc[ks].values / 1e6
fit = 0.6323 * 0.3681 ** (ks - 2) * 10.0
ax.bar(ks, obs, color=PLUM, width=0.62, alpha=0.9, label="observed")
ax.plot(ks, fit, color=OCHRE, lw=2.2, marker="o", ms=4.5,
        label="one rule: 0.632 × 0.368$^{k-2}$")
ax.set_yscale("log")
ax.set_ylim(0.004, 30)
ax.set_xlim(1.4, 9.6)
ax.set_xticks(ks)
ax.set_xlabel("banks in the visible chain")
ax.set_ylabel("payments (log scale)")
ax.yaxis.set_major_formatter(FuncFormatter(
    lambda v, p: f"{v*1e6/1e6:,.0f}M" if v >= 1 else (f"{v*1e6/1e3:,.0f}k" if v >= 1e-3 else f"{v*1e6:,.0f}")))
ax.legend(loc="upper right", frameon=False, fontsize=8.6)
caption("The vertical scale is logarithmic, so a constant 37% decay is a straight line.")
strip("Chains lengthen only when an intermediary is genuinely required, so long chains are rare by "
      "construction, not by policy. Conversion is a corridor property: a euro-zone payment never needs "
      "an FX desk, a dollar payment into Asia almost always does.")
footer(n)
save(fig, pdf, n)

# ============================================================ 13 · g6 speed
n += 1
fig = new_slide()
kicker("Group 6 of 8  ·  How long it takes")
headline("Speed is the chain, not the money")
hline(M, RIGHT, 6.02)
para(M, 5.78, (
    "A payment's duration is the sum of its legs. The typical wait rises from 39 "
    "seconds at two banks to 796 seconds at six. A currency conversion adds "
    "nothing, and an unreported intermediary adds nothing. What looks like a 3× "
    "penalty for covered routes is a mix of corridors."), size=11.4, width=50)
stat(M, 3.52, "20×", "slower at six banks than at two", width=20)
stat(M + 1.44, 3.52, "+0 s", "added by a currency conversion, at every chain length", width=21)
stat(M + 3.02, 3.52, "0.7×", "covered versus ordinary inside the same bank pair", width=22)

ax = chart((5.95, 2.06, 6.78, 3.50))
d = dur[dur.pc <= 8]
ax.fill_between(d.pc, d.p25, d.p75, color=PLUM, alpha=0.13, lw=0,
                label="middle half of payments")
ax.plot(d.pc, d.med, color=PLUM, lw=2.4, marker="o", ms=6, label="median")
for _, r in d.iterrows():
    if r.pc in (2, 4, 6):
        ax.annotate(f"{r.med:.0f} s", xy=(r.pc, r.med), xytext=(0, 11),
                    textcoords="offset points", ha="center", fontsize=9,
                    color=PLUM, fontweight="bold")
ax.set_yscale("log")
ax.set_xlim(1.7, 8.4)
ax.set_ylim(10, 6000)
ax.set_xticks(d.pc)
ax.set_xlabel("banks in the visible chain")
ax.set_ylabel("settlement time (seconds, log scale)")
ax.yaxis.set_major_formatter(FuncFormatter(lambda v, p: f"{v:,.0f}"))
ax.legend(loc="lower right", frameon=False, fontsize=8.8)
caption("Median and interquartile range of settlement time, 9.99 M clean payments.")
strip("Latency is operational, not financial: every extra bank brings its own cut-off and queue, so a "
      "slow payment is a long chain of ordinary processors, not a large amount or a flagged route.")
footer(n)
save(fig, pdf, n)

# ============================================================ 14 · g7 parties
n += 1
fig = new_slide()
kicker("Group 7 of 8  ·  Who is paying whom")
headline("Senders repeat. Beneficiaries do not, and the payee address is decoration")
hline(M, RIGHT, 6.02)
para(M, 5.78, (
    "390,725 sending accounts produce ten million payments, and 28,889 of them "
    "carry 78.6% of the volume. Beneficiaries are effectively one-off: 2.59 "
    "million accounts. The payer's address always sits in the country of the "
    "bank named on the payment; the payee's address agrees only 0.98% of the "
    "time."), size=11.4, width=50)
stat(M, 3.52, "391k", "sending accounts, against 2.59 M beneficiaries", width=21)
stat(M + 1.72, 3.52, "78.6%", "of payments come from 7% of the sending accounts", width=21)
stat(M + 3.16, 3.52, "100% / 1%", "payer address matches the named bank; the payee's does not", width=23)

ax = chart((5.95, 2.06, 6.78, 3.50))
c = conc.copy()
c["x"] = c.rk / TOTAL_SENDERS * 100
ax.plot(c.x, c.cum_share * 100, color=PLUM, lw=2.4)
ax.fill_between(c.x, c.cum_share * 100, c.x, color=PLUM, alpha=0.13, lw=0)
ax.plot([0, 100], [0, 100], color=FAINT, lw=1.1, ls="--", label="equal volume per account")
ax.scatter([28889 / TOTAL_SENDERS * 100], [78.6], s=55, color=OCHRE, zorder=4)
ax.annotate("28,889 accounts (7.4%)\ncarry 78.6% of volume",
            xy=(28889 / TOTAL_SENDERS * 100, 78.6), xytext=(30, 52),
            fontsize=9, color=OCHRE, linespacing=1.35,
            arrowprops=dict(arrowstyle="-", color=OCHRE, lw=1))
ax.set_xlim(0, 100)
ax.set_ylim(0, 100)
ax.set_xlabel("sending accounts, largest first (share of all accounts)")
ax.set_ylabel("cumulative share of payments (%)")
ax.legend(loc="lower right", frameon=False, fontsize=8.8)
caption("Concentration curve over 390,725 sending accounts. The dashed line is a book with no large senders.")
strip("This is the shape of a business payments platform: a few corporate originators push volume to a "
      "long tail of suppliers. It is also a warning. Free-text geography on the payee side is noise, so "
      "a model that learns from it learns nothing.")
footer(n)
save(fig, pdf, n)

# ============================================================ 15 · g8 anomalies
n += 1
fig = new_slide()
kicker("Group 8 of 8  ·  What goes wrong")
headline("Six exception types, six fingerprints, and they cluster by country")
hline(M, RIGHT, 6.02)
para(M, 5.78, (
    "Each label is a distinct mechanism, not a severity score. A fat-finger is "
    "an honest amount with the decimal point moved; a duplicate is the same "
    "trio re-sent within eighteen minutes; a romance scam is two to eight "
    "escalating payments inside the hour. The three scams avoid covered routes; "
    "the three operational errors use them normally."), size=11.2, width=50)
stat(M, 3.30, "7,006", "flagged rows, 0.07% of the file", width=21)
stat(M + 1.52, 3.30, "56%", "of fat-finger rows return to normal after ÷100 or ÷1,000", width=23)
stat(M + 3.26, 3.30, "7,914", "flags per 100k in Pakistan, against 33 in the United States", width=23)

ax = chart((5.95, 2.06, 6.78, 3.50))
a = anom[anom.total >= 1000].copy()
a["per100k"] = a.rate * 1e5
top = a.sort_values("per100k", ascending=False).head(11)
top = pd.concat([top, a[a.bc == "US"]]).sort_values("per100k")
cols = [FAINT if cc == "US" else PLUM for cc in top.bc]
ax.barh(np.arange(len(top)), top.per100k, color=cols, height=0.62)
ax.set_xscale("log")
ax.set_yticks(np.arange(len(top)))
ax.set_yticklabels(top.bc, fontsize=9.2)
ax.axvline(68.4, color=OCHRE, lw=1.3, ls="--")
ax.text(64, len(top) - 0.13, "all-country average 68", color=OCHRE, fontsize=8.5,
        ha="right", va="bottom")
for i, (_, r) in enumerate(top.iterrows()):
    ax.text(r.per100k * 1.07, i, f"{r.per100k:,.0f}", fontsize=8.6, color=BODY, va="center")
ax.set_xlim(20, 20000)
ax.set_ylim(-0.7, len(top) + 0.12)
ax.set_xticks([10, 100, 1000, 10000])
ax.set_xticklabels(["10", "100", "1,000", "10,000"])
ax.set_xlabel("flagged payments per 100,000, log scale")
ax.grid(axis="y", visible=False)
caption("Beneficiary countries with at least 1,000 payments; the United States is shown in grey.")
strip("Three labels are social engineering and three are operational error, which is why they differ in "
      "the route mix: a fraudster chooses a cheap route, an honest mistake rides the normal one. Geography "
      "is a portfolio effect, not a format one.")
footer(n)
save(fig, pdf, n)

# ============================================================ 16 · composition
n += 1
fig = new_slide()
kicker("Putting it together")
headline("Four dials set the money. Two coins set the structure")
hline(M, RIGHT, 6.02)
para(M, 5.74, (
    "The value fields are not eight independent stories. Four dials, the payer's "
    "market, the client type at each end, the bank, and the currency, set the "
    "ticket, and they compose additively. Two coins, how many banks and whether "
    "the corridor converts, set everything structural, independently of the "
    "amount."), size=11.2, width=52)

cards = [("Market", "650×\n$48 → $31,219"),
         ("Client type", "7.3× each end\n49× stacked"),
         ("Bank", "own-book tilt\nstable across halves"),
         ("Currency", "38.7% vs 1.0%\nround dollars")]
for i, (t, v) in enumerate(cards):
    x = M + i * 1.30
    y = 3.36
    col = OCHRE if t == "Currency" else PLUM
    box(x, y, 1.18, 1.02, WHITE, RULE, r=0.06)
    T(x + 0.11, y + 0.82, t.upper(), size=7.4, color=col, weight="bold")
    T(x + 0.11, y + 0.55, v, size=9.0, color=INK, ls=1.45)
T(M, 3.05, "SETS TICKET SIZE", size=8.6, color=PLUM, weight="bold")

coins = [("Chain length", "63% two banks · 37% decay per step"),
         ("Corridor", "binary conversion · 2,338 pairs")]
for i, (t, v) in enumerate(coins):
    x = M + i * 2.62
    y = 1.92
    box(x, y, 2.44, 0.94, TINT, RULE, r=0.06)
    T(x + 0.14, y + 0.72, t.upper(), size=7.4, color=OCHRE, weight="bold")
    T(x + 0.14, y + 0.44, v, size=9.0, color=INK, ls=1.4)
T(M, 1.76, "SETS ROUTE, COST AND SPEED, INDEPENDENT OF THE AMOUNT", size=8.6,
  color=OCHRE, weight="bold")

ax = chart((6.30, 2.75, 2.95, 2.62))
fp = fmt_pairs.sort_values("median").reset_index(drop=True)
cols4 = [FAINT, PLUM, PLUM, PLUM]
ax.bar(np.arange(4), fp["median"], color=cols4, width=0.62)
for i, (_, r) in enumerate(fp.iterrows()):
    ax.text(i, r["median"] * 1.20, f"${r['median']:,.0f}", ha="center", fontsize=8.2,
            color=BODY, fontweight="bold")
ax.set_yscale("log")
ax.set_ylim(200, 150000)
ax.set_xticks(np.arange(4))
ax.set_xticklabels(fp.pair, fontsize=8.8)
ax.set_title("client type: both ends stack (US$)", fontsize=9.2, color=MUTED, pad=6, loc="left")
ax.yaxis.set_major_formatter(FuncFormatter(lambda v, p: money(v)))
ax.grid(axis="x", visible=False)
T(6.30, 2.44, "C = consumer payer, B = business payer", size=8.0, color=FAINT)

ax2 = chart((9.85, 2.75, 2.85, 2.62))
ax2.plot(dur_amt.pc, dur_amt.med, color=PLUM, lw=2, marker="o", ms=5)
ax2.axhline(3650, color=OCHRE, lw=1.4, ls="--")
ax2.set_ylim(3000, 4400)
ax2.set_xticks([2, 3, 4, 5, 6, 7, 8])
ax2.set_xlabel("banks in chain")
ax2.set_title("routing: amount stays flat (US$)", fontsize=9.2, color=MUTED, pad=6, loc="left")
ax2.yaxis.set_major_formatter(FuncFormatter(lambda v, p: f"${v/1000:.1f}k"))
ax2.text(0.03, 0.10, "all within 4% of $3,650", transform=ax2.transAxes,
         fontsize=8.2, color=OCHRE, fontweight="bold")
strip("This turns eight findings into one model. Because the structural coins are independent of the "
      "amount dials, a bank can forecast ticket size and route cost separately: price the money one way "
      "and the plumbing another.")
footer(n)
save(fig, pdf, n)

# ============================================================ 17 · close
n += 1
fig = new_slide()
kicker("Close")
headline("What a bank should do with this, and what it cannot")
hline(M, RIGHT, 6.02)

uses = [("Price by market and client mix",
         "Ticket size is a country dial times a client-type dial. A single average price "
         "mis-prices both the small retail corridor and the large corporate one."),
        ("Manage correspondents by chain length",
         "Duration is set by how many banks a payment touches, not by its size or currency. "
         "Route policy is latency policy."),
        ("Triage fraud on route and counterparty",
         "Scams avoid covered routes; honest errors do not. Pair the route signature with "
         "beneficiary geography, and never with the payee's free-text address.")]
for i, (t, b) in enumerate(uses):
    y = 5.18 - i * 1.30
    box(M, y - 0.10, 0.05, 0.88, PLUM)
    T(M + 0.22, y + 0.70, t, size=12.2, color=INK, weight="bold", va="center")
    T(M + 0.22, y + 0.46, textwrap.fill(b, 64), size=9.8, color=BODY, ls=1.42)

box(6.85, 2.68, RIGHT - 6.85, 3.26, TINT, r=0.06)
T(7.05, 5.66, "THE HONEST LIMITS", size=8.2, color=OCHRE, weight="bold")
lims = [
    "The file is synthetic. Every rule describes this generator, not the market.",
    "Country wealth is a dial here, not a causal claim about GDP: the file contains no GDP.",
    "Medians add; individual payments do not. Row-level duration is not forecastable (R² ≈ 0.2).",
    "Three earlier claims were corrected or withdrawn after testing. Treat any single number as provisional until it replicates.",
]
yy = 5.36
for t in lims:
    body = textwrap.fill(t, 58)
    T(7.05, yy, "·", size=9.6, color=OCHRE)
    T(7.20, yy, body, size=9.4, color=BODY, ls=1.34)
    yy -= 0.24 * (body.count("\n") + 1) + 0.20

box(M, 0.92, RIGHT - M, 0.96, TINT)
T(M + 0.28, 1.48, "The value is not the eight rules.", size=13.5, color=INK,
  weight="bold", va="center")
T(M + 0.28, 1.16, "It is the method that let us keep them, and the discipline to withdraw the ones that did not survive.",
  size=10.4, color=MUTED, va="center")
footer(n)
save(fig, pdf, n)

pdf.close()
print(f"wrote {OUT_PDF}  ({n} slides)")


# ------------------------------------------------------------------- pptx
def build_pptx(pages, pdf_path, out_path):
    try:
        import fitz
        from PIL import Image
        from pptx import Presentation
        from pptx.util import Inches, Pt, Emu
        from pptx.dml.color import RGBColor
        from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
        from pptx.enum.shapes import MSO_SHAPE
        from pptx.enum.shapes import MSO_CONNECTOR
    except Exception as e:                       # pragma: no cover
        print("pptx skipped:", e)
        return

    dpi = 300
    doc = fitz.open(pdf_path)
    prs = Presentation()
    prs.slide_width = Inches(W)
    prs.slide_height = Inches(H)
    blank = prs.slide_layouts[6]

    def rgb(hexstr):
        return RGBColor.from_string(hexstr.lstrip("#").upper())

    tmp = os.path.join(PREVIEW, "_crop.png")
    os.makedirs(PREVIEW, exist_ok=True)

    for ops, page in zip(pages, doc):
        slide = prs.slides.add_slide(blank)
        pix = page.get_pixmap(dpi=dpi)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

        charts = [o for o in ops if o["kind"] == "chart"]
        rest = [o for o in ops if o["kind"] != "chart"]

        for o in charts:
            x, y, w, h = o.get("crop", o["box"])
            px = img.crop((int(x * dpi), int((H - y - h) * dpi),
                           int((x + w) * dpi), int((H - y) * dpi)))
            px.save(tmp)
            slide.shapes.add_picture(tmp, Inches(x), Inches(H - y - h),
                                     Inches(w), Inches(h))

        for o in rest:
            if o["kind"] == "rect":
                shape = slide.shapes.add_shape(
                    MSO_SHAPE.ROUNDED_RECTANGLE if o["r"] else MSO_SHAPE.RECTANGLE,
                    Inches(o["x"]), Inches(H - o["y"] - o["h"]),
                    Inches(o["w"]), Inches(o["h"]))
                if o["r"]:
                    shape.adjustments[0] = min(0.5, o["r"] / min(o["w"], o["h"]))
                shape.fill.solid()
                shape.fill.fore_color.rgb = rgb(o["fill"])
                if o["edge"]:
                    shape.line.color.rgb = rgb(o["edge"])
                    shape.line.width = Pt(0.9)
                else:
                    shape.line.fill.background()
                shape.shadow.inherit = False
                continue

            if o["kind"] == "line":
                conn = slide.shapes.add_connector(
                    MSO_CONNECTOR.STRAIGHT,
                    Inches(o["x0"]), Inches(H - o["y"]),
                    Inches(o["x1"]), Inches(H - o["y"]))
                conn.line.color.rgb = rgb(o["color"])
                conn.line.width = Pt(o["lw"])
                conn.shadow.inherit = False
                continue

            if o["kind"] == "text":
                x, y = o["x"], o["y"]
                ha = o["ha"]
                if ha == "right":
                    left, width = 0.02, max(0.4, x - 0.02)
                elif ha == "center":
                    left, width = max(0.02, x - 4.0), 8.0
                else:
                    left, width = x, max(0.5, W - 0.15 - x)

                lines = o["s"].split("\n")
                block = len(lines) * o["size"] * o["ls"] / 72.0 + 0.06

                if o["va"] == "center":
                    top_pdf = y + block / 2.0
                elif o["va"] == "baseline":
                    top_pdf = y + 0.70 * o["size"] / 72.0
                else:
                    top_pdf = y

                tb = slide.shapes.add_textbox(Inches(left), Inches(H - top_pdf),
                                              Inches(width), Inches(block))
                tf = tb.text_frame
                tf.word_wrap = False
                tf.margin_left = tf.margin_right = 0
                tf.margin_top = tf.margin_bottom = 0
                tf.vertical_anchor = MSO_ANCHOR.TOP

                for i, line in enumerate(lines):
                    p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                    p.alignment = {"right": PP_ALIGN.RIGHT,
                                   "center": PP_ALIGN.CENTER}.get(ha, PP_ALIGN.LEFT)
                    p.line_spacing = max(0.80, o["ls"] / 1.2)
                    run = p.add_run()
                    run.text = line
                    f = run.font
                    f.name = SANS
                    f.size = Pt(o["size"])
                    f.bold = o["weight"] == "bold"
                    f.color.rgb = rgb(o["color"])

    prs.save(out_path)
    print(f"wrote {out_path}  ({len(prs.slides)} slides)")


build_pptx(PAGES, OUT_PDF, OUT_PPTX)
