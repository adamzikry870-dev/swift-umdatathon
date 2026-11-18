"""Shared visual identity for the UMDAC dashboard set."""
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from matplotlib.patches import FancyBboxPatch

NAVY   = "#0B3D6B"   # observed
TEAL   = "#1F6F8B"
GOLD   = "#B8862B"   # baseline / comparator
CORAL  = "#C0504D"
GREEN  = "#3C7A5A"
GREY   = "#6B7280"
LGREY  = "#D9DEE5"
BG     = "#FFFFFF"

# page furniture
INK    = "#14212B"
BODY   = "#33404D"
MUTED  = "#6B7684"
RULE   = "#DDE3EA"
TINT   = "#F4F6F9"

PAIRS = {"B→B": NAVY, "B→C": TEAL, "C→B": GOLD, "C→C": CORAL}
CYCLE = [NAVY, TEAL, GOLD, CORAL, GREEN, "#7B5EA7", "#8C6D46", "#4F8FA6"]


def setup():
    mpl.rcParams.update({
        "figure.facecolor": BG,
        "axes.facecolor": BG,
        "savefig.facecolor": BG,
        "font.family": "Segoe UI",
        "font.size": 10,
        # dollar signs are text here, never math
        "text.parse_math": False,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "axes.edgecolor": "#9AA3AE",
        "axes.linewidth": 0.8,
        "axes.labelcolor": "#1F2937",
        "axes.titlesize": 11,
        "axes.titleweight": "bold",
        "axes.titlecolor": NAVY,
        "axes.grid": True,
        "grid.color": "#E5E9EF",
        "grid.linewidth": 0.8,
        "xtick.color": "#374151",
        "ytick.color": "#374151",
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.frameon": False,
        "legend.fontsize": 9,
        "figure.dpi": 110,
    })


def frame(fig, title, kicker, takeaway, source="Swift UMDAC Datathon 2026 · synthetic payment data · 10,000,000 records"):
    """Standard page furniture: kicker, title, takeaway strip, source footer."""
    fig.text(0.045, 0.955, kicker.upper(), fontsize=8.5, color=TEAL, fontweight="bold", va="top")
    fig.text(0.045, 0.925, title, fontsize=17, color=NAVY, fontweight="bold", va="top")
    # takeaway strip
    fig.patches.append(FancyBboxPatch((0.045, 0.038), 0.91, 0.062, boxstyle="round,pad=0.004,rounding_size=0.008",
                                      transform=fig.transFigure, facecolor="#F2F5F9", edgecolor="none",
                                      zorder=-10))
    fig.text(0.058, 0.069, takeaway, fontsize=9.8, color="#1F2937", va="center", wrap=True)
    fig.text(0.045, 0.018, source, fontsize=7.5, color=GREY, va="center")
    fig.text(0.955, 0.018, "fictitious data", fontsize=7.5, color=GREY, va="center", ha="right")


def clean(ax, grid_axis="y"):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis=grid_axis, color="#E5E9EF", lw=0.8)
    ax.set_axisbelow(True)


# --- axis formatters: one line per panel instead of a ticker import each time
def _axis(ax, axis):
    return ax.yaxis if axis == "y" else ax.xaxis


def percent_axis(ax, axis="y", decimals=0):
    """Label a 0-1 axis as percentages: 0.42 -> 42%.  decimals=None keeps %g."""
    fmt = (mtick.FuncFormatter(lambda v, _: f"{v*100:g}%") if decimals is None
           else mtick.PercentFormatter(1.0, decimals=decimals))
    _axis(ax, axis).set_major_formatter(fmt)


def money_axis(ax, axis="x"):
    """Label an axis in short USD: 22_888 -> $23k."""
    _axis(ax, axis).set_major_formatter(mtick.FuncFormatter(money))


def thousands_axis(ax, axis="y", suffix="k"):
    """Label an axis already divided by 1,000: 131 -> 131k."""
    _axis(ax, axis).set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v:,.0f}{suffix}"))


def pct(x, _=None):
    return f"{x*100:.0f}%"


def money(x, _=None):
    if x >= 1e9: return f"${x/1e9:.0f}bn"
    if x >= 1e6: return f"${x/1e6:.0f}m"
    if x >= 1e3: return f"${x/1e3:,.0f}k"
    return f"${x:,.0f}"
