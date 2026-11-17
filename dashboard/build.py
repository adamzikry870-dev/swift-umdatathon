"""The ten dashboard panels: one function per panel, one registry at the bottom.

Each function reads one or two CSVs from `data/` (built by `analysis/build_data.py`),
draws a single 16:9 page, and hands it to `finish()` for the shared furniture and
the PNG write.  Nothing here touches the parquet.

    python dashboard/build.py            # all ten
    python dashboard/build.py 3 7        # only panels 3 and 7
"""
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import style as S  # noqa: E402

DATA = HERE / "data"
OUT = HERE / "png"
PAGE = (13.33, 7.5)          # inches, 16:9
DPI = 200


def read(name, **kw):
    """Read a panel table by bare name: read('amount_hist') -> data/amount_hist.csv."""
    return pd.read_csv(DATA / f"{name}.csv", **kw)


def new_figure(rows=1, cols=2, left=0.07, right=0.975, bottom=0.20, top=0.80, **kw):
    """A blank page plus the gridspec every panel uses.

    The insets leave room for the title block (top) and the takeaway strip
    (bottom) that `finish()` adds, so panels only lay out their own axes.
    """
    fig = plt.figure(figsize=PAGE)
    gs = fig.add_gridspec(rows, cols, left=left, right=right,
                          bottom=bottom, top=top, **kw)
    return fig, gs


def finish(fig, name, title, kicker, takeaway):
    """Title block, takeaway strip, footer, then write `png/<name>.png`."""
    S.frame(fig, title, kicker, takeaway)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.png"
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    print(f"saved {path.relative_to(HERE.parent)}")


# ------------------------------------------------------------------ 1 currency
def panel_currency():
    share = read("currency_local_share")
    mean = share.local.sum() / share.n.sum()
    top = share.sort_values("n", ascending=False).head(20).iloc[::-1]

    mix_all = read("currency_foreign_mix")
    mix = mix_all.head(10).iloc[::-1]
    mix_total = mix_all.payments.sum()

    fig, gs = new_figure(left=0.075, wspace=0.42, width_ratios=[1, 0.9])
    ax = fig.add_subplot(gs[0])
    ax.barh(top.oc, top.local_share,
            color=[S.NAVY if v >= mean else S.TEAL for v in top.local_share], height=0.72)
    ax.axvline(mean, color=S.CORAL, lw=1.4, ls="--", zorder=5,
               label=f"all-country mean {mean*100:.1f}%")
    for y, v in enumerate(top.local_share):
        ax.text(1.03, y, f"{v*100:.0f}%", va="center", ha="left", fontsize=8.4, color="#374151")
    ax.set_xlim(0, 1.10)
    ax.set_ylim(-1.3, len(top) - 0.4)
    ax.text(mean, -0.75, f"all-country mean {mean*100:.1f}%", ha="center", va="center",
            color=S.CORAL, fontsize=8.4, zorder=6,
            bbox=dict(facecolor="white", edgecolor="none", pad=1.5))
    S.percent_axis(ax, "x")
    ax.set_title("Share of payments denominated in the sender country's own currency",
                 loc="left", pad=10)
    ax.set_xlabel("local-currency share of payment volume")
    S.clean(ax, "x")

    ax2 = fig.add_subplot(gs[1])
    foreign = (mix.payments / mix_total).values
    ax2.barh(mix.currency, foreign, height=0.7,
             color=[S.GOLD if c in ("EUR", "USD") else S.LGREY for c in mix.currency])
    for y, v in enumerate(foreign):
        ax2.text(v + 0.008, y, f"{v*100:.1f}%", va="center", fontsize=8.4, color="#374151")
    ax2.set_xlim(0, foreign.max() * 1.18)
    S.percent_axis(ax2, "x")
    ax2.set_title("When it is not local: which currency is used", loc="left", pad=10)
    ax2.set_xlabel("share of all non-local payments")
    S.clean(ax2, "x")

    finish(fig, "01_currency",
           "Currency is chosen by the sender, not by the corridor",
           "Panel 1 · currency",
           "84–94% of payments use the ordering country's home currency (US 91%, DE 94%, AU 84%). "
           "The remaining 6–16% is overwhelmingly EUR (44%) and USD (22%): a deliberate foreign-currency option, not corridor geography.")


# ------------------------------------------------------------------ 2 amounts
def panel_amounts():
    stats = read("amount_pair_stats").set_index("pair").loc[["B→B", "B→C", "C→B", "C→C"]]
    hist = read("amount_hist")
    code = {"B→B": "BB", "B→C": "BC", "C→B": "CB", "C→C": "CC"}

    fig, gs = new_figure(left=0.07, wspace=0.30, width_ratios=[1.25, 1])
    ax = fig.add_subplot(gs[0])
    for pair in ["B→B", "B→C", "C→B", "C→C"]:
        d = hist[hist.pair_code == code[pair]].sort_values("b")
        ax.step(10 ** d.b, (d.n / d.n.sum()).cumsum(), where="post", lw=2,
                color=S.PAIRS[pair], label=pair)
        ax.plot([stats.loc[pair, "median"]], [0.5], "o", color=S.PAIRS[pair],
                ms=7, mec="white", mew=1.2, zorder=5)
    ax.axhline(0.5, color=S.LGREY, lw=1, zorder=1)
    ax.set_xscale("log")
    ax.set_xlim(1, 1e8)
    ax.set_ylim(0, 1)
    S.percent_axis(ax, "y")
    S.money_axis(ax, "x")
    ax.set_xlabel("payment amount (USD, log scale)")
    ax.set_ylabel("share of payments below this amount")
    ax.set_title("Same curve, shifted ~7× per business side", loc="left", pad=10)
    ax.legend(loc="upper left", ncol=2, title="ordering → beneficiary")
    for pair in ["C→C", "B→C", "B→B"]:
        m = stats.loc[pair, "median"]
        ax.annotate(S.money(m), (m, 0.5), textcoords="offset points", xytext=(8, -14),
                    fontsize=8.4, color=S.PAIRS[pair], fontweight="bold")
    S.clean(ax)

    ax2 = fig.add_subplot(gs[1])
    medians = stats["median"].values
    bars = ax2.bar(stats.index, medians, color=[S.PAIRS[p] for p in stats.index], width=0.6)
    for bar, v in zip(bars, medians):
        ax2.text(bar.get_x() + bar.get_width() / 2, v * 1.12, S.money(v), ha="center",
                 fontsize=10, fontweight="bold", color="#1F2937")
    base = stats.loc["C→C", "median"]
    ax2.set_yscale("log")
    ax2.set_ylim(100, 1e5)
    S.money_axis(ax2, "y")
    ax2.set_ylabel("median payment (USD, log scale)")
    ax2.set_title("Median amount by party class", loc="left", pad=10)
    for i, (pair, v) in enumerate(zip(stats.index, medians)):
        label = f"×{v/base:.1f}" if pair != "C→C" else "baseline"
        ax2.text(i, v * 0.55, label, ha="center", fontsize=9,
                 color="white" if pair != "C→C" else "#1F2937", fontweight="bold")
    S.clean(ax2)

    finish(fig, "02_amounts",
           "Who pays whom sets the amount — a 49× gap between B→B and C→C",
           "Panel 2 · values",
           "Each business counterparty multiplies the median by ≈6.8× (B→B $22,888 · B→C $3,119 · C→B $3,229 · C→C $463). "
           "The shapes are parallel log-normals: the class shifts the level, not the dispersion.")


# ------------------------------------------------------------------ 3 routing
def panel_routing():
    d = read("participants_by_type")
    d["share"] = d.n / d.groupby("tt").n.transform("sum")

    fig, gs = new_figure(wspace=0.26, width_ratios=[1, 1])
    ax = fig.add_subplot(gs[0])
    for tt, col, marker in [("Direct", S.NAVY, "o"), ("Indirect", S.TEAL, "s"),
                            ("Covered", S.GOLD, "^")]:
        sub = d[(d.tt == tt) & (d.pc <= 9)].sort_values("pc")
        ax.plot(sub.pc, sub.share, marker=marker, color=col, lw=2, ms=6, label=tt)
    k = np.arange(2, 10)
    ax.plot(k[k >= 3], 0.6321 * 0.368 ** (k[k >= 3] - 3), ls="--", lw=1.3, color=S.CORAL,
            label="geometric fit  0.632 × 0.368^(k−3)")
    ax.set_yscale("log")
    ax.set_ylim(5e-5, 3)
    ax.set_yticks([1e-4, 1e-3, 1e-2, 1e-1, 1])
    S.percent_axis(ax, "y", decimals=None)
    ax.set_xticks(range(2, 10))
    ax.set_xlabel("visible participants in BIC8 path")
    ax.set_ylabel("share within transaction type (log)")
    ax.set_title("Chain length is geometric — except Direct, which stops at 2", loc="left", pad=10)
    ax.annotate("Direct: 100% at k=2,\nno tail", (2, 1), xytext=(4.3, 0.42), fontsize=8.5,
                color=S.NAVY, arrowprops=dict(arrowstyle="-", color=S.NAVY, lw=0.8))
    ax.legend(loc="lower left")
    S.clean(ax)

    ax2 = fig.add_subplot(gs[1])
    sub = (d[d.tt.isin(["Indirect", "Covered"])]
           .pivot_table(index="pc", columns="tt", values="n", fill_value=0).loc[:9])
    sub = sub.div(d.groupby("tt").n.sum(), axis=1)          # share within each type
    ratio = sub["Covered"] / sub["Indirect"]
    ax2.axhline(1, color=S.NAVY, lw=1.2, ls="--")
    ax2.plot(ratio.index, ratio.values, "o", ms=8, color=S.GOLD, zorder=3)
    for x, v in zip(ratio.index, ratio.values):
        ax2.text(x, v + 0.012, f"{v:.2f}", ha="center", fontsize=8.5, color="#374151")
    ax2.set_ylim(0.9, 1.12)
    ax2.set_xticks(range(3, 10))
    ax2.set_xlabel("visible participants")
    ax2.set_ylabel("Covered share ÷ Indirect share")
    ax2.set_title("Indirect and Covered are the same length law", loc="left", pad=10)
    ax2.text(0.02, 0.06, "axis truncated · identical law = 1.00", transform=ax2.transAxes,
             fontsize=8, color=S.GREY, style="italic")
    S.clean(ax2)

    finish(fig, "03_routing",
           "Every extra bank in the chain is a 37% coin flip",
           "Panel 3 · routing",
           "Indirect and Covered share one geometric law, P(k)=0.632·0.368^(k−3). Direct is a hard rule: exactly 2 participants, no tail — "
           "transaction type is a label on chain length.")


# ------------------------------------------------------------------ 4 continuity
def panel_continuity():
    d = read("gap_rate_by_participants")
    d = d[d.pc <= 12].copy()
    p = d.loc[d.pc == 2, "gap_rate"].iloc[0]
    d["pred"] = 1 - (1 - p) ** (d.pc - 1)
    d["se"] = np.sqrt(d.gap_rate * (1 - d.gap_rate) / d.n) * 1.96
    d["z"] = (d.gap_rate - d.pred) / np.sqrt(d.gap_rate * (1 - d.gap_rate) / d.n)

    fig, gs = new_figure(wspace=0.28, width_ratios=[1.15, 1])
    ax = fig.add_subplot(gs[0])
    lim = [0, 0.5]
    ax.plot(lim, lim, color=S.GREY, lw=1, ls="--", label="perfect fit (45°)")
    ax.errorbar(d.pred, d.gap_rate, yerr=d.se, fmt="o", ms=8, color=S.NAVY,
                ecolor="#9AA3AE", elinewidth=1.1, capsize=3, zorder=3,
                label="observed ±95% CI")
    for r in d.itertuples():
        ax.annotate(f"n={int(r.pc)}", (r.pred, r.gap_rate), textcoords="offset points",
                    xytext=(8, -3), fontsize=8, color=S.GREY)
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    S.percent_axis(ax, "x")
    S.percent_axis(ax, "y")
    ax.set_xlabel("predicted gap rate  1 − 0.95^(n−1)")
    ax.set_ylabel("observed share of payments with '...'")
    ax.set_title("Observed vs predicted truncation rate", loc="left", pad=10)
    ax.legend(loc="upper left")
    S.clean(ax)

    ax2 = fig.add_subplot(gs[1])
    ax2.bar(d.pc.astype(str), d.z, width=0.62, zorder=2,
            color=[S.GREEN if abs(v) <= 2 else S.GOLD for v in d.z])
    for s in (-2, 2):
        ax2.axhline(s, color=S.CORAL, lw=1, ls="--", zorder=3)
    ax2.axhline(0, color="#374151", lw=1)
    ax2.set_xlabel("visible participants")
    ax2.set_ylabel("(observed − predicted) ÷ standard error")
    ax2.set_title("Standardised residuals: 9 of 11 inside ±2σ, none beyond 2.4σ",
                  loc="left", pad=10)
    ax2.text(0.985, 0.06, "green = inside the 2σ band · gold = outside\n±2σ reference in coral",
             transform=ax2.transAxes, ha="right", fontsize=8.2, color=S.GREY, style="italic")
    ax2.set_ylim(-3.2, 3.2)
    S.clean(ax2)

    finish(fig, "04_continuity",
           "The strongest exact rule in the file: truncation is 1 − 0.95^(n−1)",
           "Panel 4 · path continuity",
           "Each hop is collapsed into '...' with probability 5% (n=2: 4.99%, n=6: 22.5%, n=10: 38.3%). Every standardised residual stays within ±2.4 SE "
           "across 10M rows — sampling noise, not a second rule.")


# ------------------------------------------------------------------ 5 fx
def panel_fx():
    fx = read("fx_by_participants")
    fit = read("fx_binomial_fit")
    heat = read("fx_heatmap")
    home = read("country_home_currency").set_index("cc")["home_currency"].to_dict()

    fig, gs = new_figure(left=0.065, right=0.935, wspace=0.26, width_ratios=[1, 1.12])

    inner = gs[0].subgridspec(2, 3, hspace=0.62, wspace=0.30)
    for i, pc in enumerate([2, 3, 4, 5, 6, 7]):
        ax = fig.add_subplot(inner[i // 3, i % 3])
        obs = fx[fx.pc == pc].sort_values("fx")
        ax.bar(obs.fx, obs.n / obs.n.sum(), color=S.TEAL, width=0.55, label="observed")
        f = fit[(fit.pc == pc) & (fit.pred > 1e-4)].sort_values("fx")
        ax.plot(f.fx, f.pred, "o--", color=S.CORAL, ms=3.5, lw=1.1,
                label="binomial p=0.851")
        ax.set_title(f"{pc} participants", fontsize=9.5, loc="left", pad=3)
        ax.set_xticks(range(0, pc))
        S.percent_axis(ax, "y")
        ax.tick_params(labelsize=8)
        S.clean(ax)
    fig.text(0.065, 0.845, "Conversion-count distribution per chain length", fontsize=11,
             fontweight="bold", color=S.NAVY)

    ax2 = fig.add_subplot(gs[1])
    totals = heat.groupby("oc").n.sum().sort_values(ascending=False)
    keep = sorted(list(totals.head(22).index), key=lambda c: (home.get(c, "ZZ"), -totals[c]))
    m = heat[heat.oc.isin(keep) & heat.bc.isin(keep)].pivot_table(index="oc", columns="bc", values="p")
    m = m.reindex(index=keep, columns=keep)
    cmap = LinearSegmentedColormap.from_list("b", ["#EEF4F8", S.NAVY])
    im = ax2.imshow(m.values, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    ax2.set_xticks(range(len(keep)))
    ax2.set_xticklabels(keep, fontsize=6.6, rotation=90)
    ax2.set_yticks(range(len(keep)))
    ax2.set_yticklabels(keep, fontsize=6.6)
    ax2.set_title("P(currency conversion) for direct payments, path endpoints\n"
                  "0 = both endpoints use the same currency · 1 = a currency border is crossed",
                  loc="left", pad=10, fontsize=10.2)
    ax2.grid(False)
    for s in ax2.spines.values():
        s.set_visible(False)
    # separators between currency blocks
    previous = None
    for i, c in enumerate(keep):
        currency = home.get(c, "ZZ")
        if previous is not None and currency != previous:
            ax2.axhline(i - 0.5, color=S.GOLD, lw=1.1)
            ax2.axvline(i - 0.5, color=S.GOLD, lw=1.1)
        previous = currency
    euro = [i for i, c in enumerate(keep) if home.get(c) == "EUR"]
    if len(euro) > 1:
        mid = (euro[0] + euro[-1]) / 2
        ax2.text(mid, mid, "EUR → EUR\nalways 0", ha="center", va="center",
                 fontsize=8.6, color=S.NAVY, fontweight="bold")
    cb = fig.colorbar(im, ax=ax2, fraction=0.030, pad=0.012, ticks=[0, 1])
    cb.ax.set_yticklabels(["same", "cross"], fontsize=7.4)
    cb.outline.set_visible(False)

    finish(fig, "05_fx",
           "Currency conversion is a property of the country chain, not a random event",
           "Panel 5 · FX",
           "Conversion count = adjacent currency changes along the displayed path — 100% exact. "
           "Each hop crosses a currency border with p=0.851, so the count follows Binomial(n−1, 0.851), max error 3.9 pp.")


# ------------------------------------------------------------------ 6 duration
def panel_duration():
    d = read("duration_by_pc_fx")
    fixed = d[(d.fx == 1) & (d.pc <= 8)].sort_values("pc")

    fig, gs = new_figure(left=0.075, wspace=0.30, width_ratios=[1, 1])
    ax = fig.add_subplot(gs[0])
    ax.fill_between(fixed.pc, fixed.p10, fixed.p90, color=S.NAVY, alpha=0.07, lw=0)
    ax.plot(fixed.pc, fixed["med"], "o-", color=S.NAVY, lw=2.4, ms=7, label="median")
    ax.plot(fixed.pc, fixed.p10, color=S.TEAL, lw=1.1, ls="--", label="p10")
    ax.plot(fixed.pc, fixed.p90, color=S.GOLD, lw=1.1, ls="--", label="p90")
    for r in fixed.itertuples():
        ax.annotate(f"{r.med:,.0f}s", (r.pc, r.med), textcoords="offset points",
                    xytext=(7, -4), fontsize=8.2, color=S.NAVY, fontweight="bold")
    ax.set_yscale("log")
    ax.set_xticks(range(2, 7))
    ax.set_xlim(1.8, 6.5)
    ax.set_ylim(6, 12000)
    ax.set_xlabel("visible participants in the path")
    ax.set_ylabel("TOTAL_DURATION (seconds, log)")
    ax.set_title("Median latency rises 21× as the chain grows from 2 to 6 banks",
                 loc="left", pad=10)
    ax.legend(loc="lower right", ncol=3, fontsize=8.6)
    ax.annotate("×3.5", (2.5, 92), fontsize=9, color=S.CORAL, fontweight="bold", ha="center")
    ax.annotate("×3.1", (3.5, 300), fontsize=9, color=S.CORAL, fontweight="bold", ha="center")
    ax.annotate("×1.4", (4.5, 660), fontsize=9, color=S.CORAL, fontweight="bold", ha="center")
    ax.text(0.98, 0.94, "band = p10–p90 across payments\none currency conversion fixed",
            transform=ax.transAxes, ha="right", va="top", fontsize=8.2, color=S.GREY,
            style="italic")
    S.clean(ax)

    ax2 = fig.add_subplot(gs[1])
    for pc, col in [(3, S.TEAL), (4, S.NAVY), (5, S.GOLD), (6, S.CORAL), (7, S.GREEN)]:
        sub = d[d.pc == pc].sort_values("fx")
        if len(sub) < 2:
            continue
        ax2.plot(sub.fx, sub["med"], "o-", color=col, lw=2, ms=5.5)
        ax2.annotate(f"{pc}", (sub.fx.iloc[-1], sub["med"].iloc[-1]),
                     textcoords="offset points", xytext=(9, -3), fontsize=8.4,
                     color=col, fontweight="bold")
    ax2.set_yscale("log")
    ax2.set_ylim(60, 3000)
    ax2.set_xlabel("currency conversions on the path")
    ax2.set_ylabel("median TOTAL_DURATION (seconds, log)")
    ax2.set_title("Chain length sets the level; conversions barely move it", loc="left", pad=10)
    ax2.set_xticks(range(0, 7))
    ax2.text(0.02, 0.94, "line labels = participants", transform=ax2.transAxes,
             fontsize=8.4, color=S.GREY)
    ax2.text(0.98, 0.04, "each line spans <1.7× end to end;\none extra bank triples the median",
             transform=ax2.transAxes, ha="right", fontsize=8.2, color=S.GREY, style="italic")
    S.clean(ax2)

    finish(fig, "06_duration",
           "Latency is bought by hand-offs, not by conversions",
           "Panel 6 · duration",
           "With one conversion fixed, the median rises 38 s → 804 s as a chain grows from 2 to 6 banks (21×). "
           "At a fixed length, moving across 0–5 conversions changes it by at most 1.7×.")


# ------------------------------------------------------------------ 7 time
def panel_time():
    raw = read("hour_raw_top", index_col=0)
    aligned = read("hour_aligned", index_col=0)
    tz = read("tz_shift")
    daily = read("daily_volume")
    daily["date"] = pd.to_datetime(daily["date"], utc=True)
    first, last = daily.date.min(), daily.date.max()
    daily = daily[(daily.date > first) & (daily.date < last)].copy()   # drop partial days
    show = ["US", "GB", "CH", "SG", "JP", "AU"]
    hours = [0, 6, 12, 18, 23]

    fig, gs = new_figure(rows=2, cols=2, wspace=0.24, hspace=0.62,
                         width_ratios=[1, 1], height_ratios=[1, 1])

    ax = fig.add_subplot(gs[0, 0])
    for country, col in zip(show, S.CYCLE):
        v = raw.loc[country].values.astype(float)
        ax.plot(range(24), v / v.sum(), color=col, lw=1.6, label=country)
    ax.set_title("a · as stored (UTC hour)", loc="left", pad=6, fontsize=10.5)
    ax.set_ylabel("share of country volume")
    ax.set_xticks(hours)
    S.percent_axis(ax, "y")
    ax.legend(ncol=3, fontsize=8, loc="upper center")
    ax.set_ylim(0, 0.115)
    S.clean(ax)

    ax2 = fig.add_subplot(gs[1, 0])
    for country, col in zip(show, S.CYCLE):
        ax2.plot(range(24), aligned[country].values.astype(float), color=col, lw=1.6,
                 label=country)
    ax2.set_title("b · shifted to local time — the curves collapse", loc="left", pad=6,
                  fontsize=10.5)
    ax2.set_ylabel("share of country volume")
    ax2.set_xlabel("local hour")
    ax2.set_xticks(hours)
    S.percent_axis(ax2, "y")
    ax2.set_ylim(0, 0.115)
    ax2.text(0.02, 0.90, f"median alignment r = {tz['corr'].median():.3f}",
             transform=ax2.transAxes, fontsize=8.4, color=S.GREY, style="italic")
    S.clean(ax2)

    ax3 = fig.add_subplot(gs[:, 1])
    ax3.bar(daily.date, daily.n / 1000, width=1.0,
            color=[S.CORAL if d >= 5 else S.NAVY for d in daily.dow])
    ax3.set_ylabel("payments per day (thousands)")
    ax3.set_title("Volume by day: a 4× weekend trough and a 5-day June surge", loc="left", pad=10)
    S.thousands_axis(ax3, "y")
    ax3.legend(handles=[Line2D([], [], marker="s", ls="", color=S.NAVY, label="weekday"),
                        Line2D([], [], marker="s", ls="", color=S.CORAL, label="weekend")],
               loc="upper left", ncol=2, fontsize=8.6, frameon=True, facecolor="white",
               edgecolor="none", framealpha=0.85)
    ax3.set_ylim(0, 245)
    surge = daily[daily.n > 200_000]
    if len(surge):
        peak = surge.loc[surge.n.idxmax()]
        ax3.annotate("19–23 Jun\n205–220k/day", (peak.date, peak.n / 1000),
                     xytext=(-92, -6), textcoords="offset points", fontsize=8.2,
                     color=S.NAVY, arrowprops=dict(arrowstyle="-", color=S.GREY, lw=0.8))
    S.clean(ax3)

    finish(fig, "07_time",
           "One global business-hours curve, rotated by timezone",
           "Panel 7 · time",
           "Every country's hourly profile is the same shape shifted by its UTC offset (median r=0.94 after alignment). "
           "Weekday volume averages 131–141k payments/day, Saturday 33k and Sunday 49k — a 4× weekend trough.")


# ------------------------------------------------------------------ 8 anomalies
def panel_anomalies():
    raw = read("anomaly_by_beneficiary_country")
    raw["per100k"] = raw.rate * 1e5
    top = raw[raw.total >= 1000].sort_values("per100k", ascending=False).head(16).iloc[::-1]
    typology = read("anomaly_typology_pair")
    overall = typology.n.sum() / 10_000_000

    fig, gs = new_figure(left=0.075, wspace=0.40, width_ratios=[1, 0.95])
    ax = fig.add_subplot(gs[0])
    lo, hi = top.per100k.min(), top.per100k.max()
    cmap = LinearSegmentedColormap.from_list("r", [S.TEAL, S.GOLD, S.CORAL])
    ax.barh(top.bc, top.per100k, height=0.72,
            color=[cmap(0.15 + 0.85 * (np.log10(v) - np.log10(lo)) / (np.log10(hi) - np.log10(lo)))
                   for v in top.per100k])
    ref = overall * 1e5
    ax.axvline(ref, color=S.NAVY, lw=1.4, ls="--", zorder=5)
    ax.set_xscale("log")
    ax.set_xlim(10, 2e4)
    ax.set_ylim(-1.9, len(top) - 0.4)
    ax.set_xlabel("labelled anomalies per 100,000 payments (log)")
    ax.set_title("Anomaly rate by beneficiary bank country", loc="left", pad=10)
    for y, (r, n) in enumerate(zip(top.per100k, top.anom)):
        ax.text(r * 1.15, y, f"{r:,.0f}  ·  n={n:,}", va="center", fontsize=8, color="#374151")
    ax.text(ref, -1.2, f"all countries  {ref:.0f} per 100k", fontsize=8.2, ha="center",
            color=S.NAVY, zorder=6, bbox=dict(facecolor="white", edgecolor="none", pad=1.6))
    ax.text(0.98, 0.02, "countries with ≥1,000 payments", transform=ax.transAxes,
            ha="right", fontsize=8, color=S.GREY, style="italic")
    S.clean(ax, "x")

    ax2 = fig.add_subplot(gs[1])
    totals = typology.groupby("a").n.sum()
    order = totals.sort_values().index
    pairs = ["B→B", "C→B", "B→C", "C→C"]
    left = np.zeros(len(order))
    for pair, col in zip(pairs, [S.NAVY, S.GOLD, S.TEAL, S.CORAL]):
        v = np.array([typology[(typology.a == a) & (typology.ot + "→" + typology.bt == pair)].n.sum()
                      / totals[a] for a in order])
        ax2.barh(order, v, left=left, color=col, label=pair, height=0.66)
        left += v
    ax2.set_xlim(0, 1)
    S.percent_axis(ax2, "x")
    ax2.set_title("Party mix inside each typology", loc="left", pad=10)
    ax2.set_yticks(range(len(order)))
    ax2.set_yticklabels([f"{a}   ({totals[a]:,})" for a in order], fontsize=8.8)
    ax2.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.42, -0.09), fontsize=8.5,
               title=None)
    S.clean(ax2, "x")

    finish(fig, "08_anomalies",
           "Anomalies are injected, not random: they cluster by typology and by destination",
           "Panel 8 · anomalies",
           "Romance is 100% consumer-sent, CEO 100% business-sent; the other four are business-heavy (57–58% B→C). "
           "Rates span 0.03% (US, 1.9M payments) to 7.9% (PK, 1,491) — 7,006 labels in all.")


# ------------------------------------------------------------------ 9 geography
def panel_geography():
    banks = read("bank_count_by_country").head(14).iloc[::-1]
    inter = read("intermediary_concentration")

    fig, gs = new_figure(left=0.075, wspace=0.32, width_ratios=[1, 1])
    ax = fig.add_subplot(gs[0])
    ax.barh(banks.cc, banks.b, color=S.TEAL, height=0.72)
    for y, b in enumerate(banks.b):
        ax.text(b * 1.02, y, f"{b:,}", va="center", fontsize=8.3, color="#374151")
    ax.set_xlim(0, 1150)
    ax.set_xlabel("distinct BIC8 banks observed")
    ax.set_title("Bank population by country (8,392 banks in total)", loc="left", pad=10)
    S.clean(ax, "x")

    ax2 = fig.add_subplot(gs[1])
    ax2.plot(np.arange(1, len(inter) + 1), inter.cum, color=S.NAVY, lw=2.4)
    ax2.set_xscale("log")
    ax2.set_ylim(0, 1.02)
    S.percent_axis(ax2, "y")
    ax2.set_xlabel("intermediary rank (log)")
    ax2.set_ylabel("cumulative share of intermediate hops")
    ax2.set_title("Correspondent concentration", loc="left", pad=10)
    for k, label in [(10, "top 10 = 19%"), (100, "top 100 = 52%"), (1000, "top 1,000 = 93%")]:
        y = inter.cum.iloc[k - 1]
        ax2.plot([k], [y], "o", color=S.GOLD, ms=7, zorder=5)
        ax2.annotate(label, (k, y), xytext=(10, -14), textcoords="offset points",
                     fontsize=8.6, color=S.NAVY)
    S.clean(ax2)

    finish(fig, "09_geography",
           "A handful of banks carry the network",
           "Panel 9 · geography",
           "Banks are spread over 228 countries but 100 correspondents handle 52% of all intermediate hops and the top 1,000 handle 93%. "
           "The graph is a hub-and-spoke network, not a uniform mesh.")


# ------------------------------------------------------------------ 10 tokens
def panel_tokens():
    agreement = json.loads((DATA / "token_agreement.json").read_text(encoding="utf-8"))
    shares = read("token_vs_bank_share").iloc[::-1]

    fig, gs = new_figure(left=0.085, wspace=0.42, width_ratios=[0.78, 1.12])
    ax = fig.add_subplot(gs[0])
    labels = ["Ordering address\nvs ordering bank", "Beneficiary address\nvs beneficiary bank"]
    values = [agreement["ordering_match_when_present"],
              agreement["beneficiary_match_when_present"]]
    bars = ax.bar(labels, values, color=[S.NAVY, S.CORAL], width=0.5)
    for bar, v in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 0.025, f"{v*100:.1f}%", ha="center",
                fontsize=15, fontweight="bold", color="#1F2937")
    ax.set_ylim(0, 1.1)
    S.percent_axis(ax, "y")
    ax.set_ylabel("share of rows where the country token\nmatches the party's bank country")
    ax.set_title("Country token agreement\nof rows that carry a token (61% of the file)",
                 loc="left", pad=10, fontsize=10.5)
    ax.set_xticks(range(2))
    ax.set_xticklabels(labels, fontsize=9)
    S.clean(ax)

    ax2 = fig.add_subplot(gs[1])
    y = np.arange(len(shares))
    ax2.barh(y + 0.19, shares.token_share, height=0.36, color=S.GOLD,
             label="beneficiary address token")
    ax2.barh(y - 0.19, shares.bank_share, height=0.36, color=S.NAVY,
             label="beneficiary bank country")
    ax2.set_yticks(y)
    ax2.set_yticklabels(shares.country, fontsize=9)
    ax2.set_xlim(0, 0.23)
    S.percent_axis(ax2, "x")
    ax2.set_xlabel("share of all 10 million payments")
    ax2.set_title("Same country list — two unrelated distributions", loc="left", pad=10)
    ax2.text(0.985, 0.965, "ratio = address share ÷ bank share", transform=ax2.transAxes,
             ha="right", va="top", fontsize=7.8, color=S.GREY, style="italic")
    for yy, (t, b) in enumerate(zip(shares.token_share, shares.bank_share)):
        ax2.text(max(t, b) + 0.004, yy, f"{t/b:.2f}×" if b > 0 else "", va="center",
                 fontsize=7.8, color=S.GREY)
    ax2.legend(loc="lower right", fontsize=8.4, ncol=1)
    S.clean(ax2, "x")

    finish(fig, "10_tokens",
           "The sender's address is domestic; the beneficiary's is anywhere",
           "Panel 10 · party text",
           "When a token exists, the ordering address matches its bank country 100.0% of the time, the beneficiary address only 1.0%. "
           "Addresses (CN 8.8%, BR 5.5%, UA 4.4%) are a different draw from banks (US 19.2%, CH 8.3%, GB 6.6%).")


PANELS = {
    "1": panel_currency,
    "2": panel_amounts,
    "3": panel_routing,
    "4": panel_continuity,
    "5": panel_fx,
    "6": panel_duration,
    "7": panel_time,
    "8": panel_anomalies,
    "9": panel_geography,
    "10": panel_tokens,
}


def main(argv):
    S.setup()
    for number in argv or PANELS:
        PANELS[number]()


if __name__ == "__main__":
    main(sys.argv[1:])
