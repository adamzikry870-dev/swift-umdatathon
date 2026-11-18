"""Regenerate the panel tables that the dashboard rebuild reads.

Two definitions change relative to `swift/panels.py`:

  * sender country  = chars 5-6 of the FIRST bank in BIC8_PATH, not ORDERING_BIC8
    (the two disagree on ~5% of rows; the path is the record of what happened)
  * amount and duration statistics = clean rows only (ANOMALY_TYPE IS NULL),
    because 7,006 injected rows otherwise leak into every median

It also writes five tables the previous dashboard did not have, for charts that
compare a finding against a baseline rather than showing a lone distribution.

    python analysis/refresh_panels.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from swift.db import DATA, PANEL_DATA, connect  # noqa: E402

P = DATA.as_posix()
OUT = PANEL_DATA
PATH_C = "substr(split_part(BIC8_PATH, ';', 1), 5, 2)"   # sender country, from the path
PATH_B = "substr(string_split(BIC8_PATH, ';')[len(string_split(BIC8_PATH, ';'))], 5, 2)"
CLEAN = "ANOMALY_TYPE IS NULL"


def save(df: pd.DataFrame, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / name, index=False)
    print(f"  wrote {name}  ({len(df):,} rows)")


def step(msg: str) -> None:
    print(f"\n>> {msg}")


def currency(con) -> None:
    step("currency: home currency and local share, keyed on the path's first bank")
    home = con.execute(f"""
        with t as (
            select {PATH_C} as oc, CURRENCY_CODE as cur, count(*) as n
            from '{P}' group by 1, 2
        )
        select oc as cc, cur as home_currency, n
        from (select *, row_number() over (partition by oc order by n desc) rk from t)
        where rk = 1 order by n desc
    """).df()
    save(home, "country_home_currency.csv")

    share = con.execute(f"""
        with t as (
            select {PATH_C} as oc, CURRENCY_CODE as cur, count(*) as n
            from '{P}' group by 1, 2
        ), h as (
            select oc, cur as hc
            from (select *, row_number() over (partition by oc order by n desc) rk from t)
            where rk = 1
        )
        select t.oc as oc, sum(t.n) as n,
               sum(case when t.cur = h.hc then t.n else 0 end) as local
        from t left join h using (oc) group by 1 order by n desc
    """).df()
    share["local"] = share.local.astype("int64")
    share["local_share"] = share.local / share.n
    save(share, "currency_local_share.csv")
    print(f"  weighted local share {(share.local.sum() / share.n.sum() * 100):.2f}%")

    foreign = con.execute(f"""
        with t as (
            select {PATH_C} as oc, CURRENCY_CODE as cur, count(*) as n
            from '{P}' group by 1, 2
        ), h as (
            select oc, cur as hc
            from (select *, row_number() over (partition by oc order by n desc) rk from t)
            where rk = 1
        )
        select t.cur as currency, sum(t.n) as payments
        from t join h using (oc) where t.cur <> h.hc
        group by 1 order by 2 desc
    """).df()
    save(foreign, "currency_foreign_mix.csv")


def amounts(con) -> None:
    step("amounts: pair statistics and histogram, clean rows only")
    stats = con.execute(f"""
        select ORDERING_TYPE || BENEFICIARY_TYPE as pair_code,
               count(*) as count, median(USD_AMOUNT) as median, avg(USD_AMOUNT) as mean,
               quantile_cont(USD_AMOUNT, 0.05) as p05, quantile_cont(USD_AMOUNT, 0.95) as p95
        from '{P}' where USD_AMOUNT > 0 and {CLEAN}
        group by 1 order by 1
    """).df()
    stats["pair"] = stats.pair_code.str[0] + "\u2192" + stats.pair_code.str[1]
    save(stats[["pair", "count", "median", "mean", "p05", "p95"]], "amount_pair_stats.csv")
    print(stats[["pair", "count", "median"]].to_string(index=False))

    hist = con.execute(f"""
        select ORDERING_TYPE || BENEFICIARY_TYPE as pair_code,
               floor(log10(USD_AMOUNT) * 10) / 10 as b, count(*) as n
        from '{P}' where USD_AMOUNT > 0 and {CLEAN}
        group by 1, 2 order by 1, 2
    """).df()
    save(hist, "amount_hist.csv")

    ladder = con.execute(f"""
        select {PATH_C} as cc, median(USD_AMOUNT) as med, count(*) as n
        from '{P}' where USD_AMOUNT > 0 and {CLEAN}
        group by 1 having count(*) >= 2000 order by med
    """).df()
    save(ladder, "country_median_amount.csv")
    print(f"  {len(ladder)} markets, ${ladder.med.min():,.0f} to ${ladder.med.max():,.0f}")

    roundness = con.execute(f"""
        select case when CURRENCY_CODE = 'USD' then 'USD' else 'Other' end as k,
               avg(case when USD_AMOUNT = floor(USD_AMOUNT) then 1.0 else 0.0 end) as whole,
               count(*) as n
        from '{P}' where USD_AMOUNT >= 1 and {CLEAN} group by 1 order by 1
    """).df()
    save(roundness, "usd_roundness.csv")


def duration(con) -> None:
    step("duration: median and p10/p90 by chain length, clean rows only")
    d = con.execute(f"""
        select PARTICIPANT_COUNT as pc, CURRENCY_CONVERSION_COUNT as fx, count(*) as n,
               median(TOTAL_DURATION) as med,
               quantile_cont(TOTAL_DURATION, 0.1) as p10,
               quantile_cont(TOTAL_DURATION, 0.9) as p90
        from '{P}'
        where PARTICIPANT_COUNT between 2 and 10 and CURRENCY_CONVERSION_COUNT between 0 and 6
          and {CLEAN}
        group by 1, 2 having count(*) >= 300 order by 1, 2
    """).df()
    save(d, "duration_by_pc_fx.csv")

    pooled = con.execute(f"""
        select PARTICIPANT_COUNT as pc, count(*) as n,
               median(TOTAL_DURATION) as med,
               quantile_cont(TOTAL_DURATION, 0.1) as p10,
               quantile_cont(TOTAL_DURATION, 0.9) as p90
        from '{P}' where PARTICIPANT_COUNT between 2 and 10 and {CLEAN}
        group by 1 having count(*) >= 500 order by 1
    """).df()
    save(pooled, "duration_by_pc.csv")
    print(pooled[["pc", "n", "med"]].to_string(index=False))


def hours(con) -> None:
    step("time: hour-of-day curve for every country, plus the aligned profile")
    curve = con.execute(f"""
        select {PATH_C} as oc, (EPOCH_SECONDS // 3600) % 24 as h, count(*) as n
        from '{P}' group by 1, 2
    """).df()
    piv = curve.pivot(index="oc", columns="h", values="n").fillna(0).sort_index()
    piv.columns = [f"h{int(c)}" for c in piv.columns]
    piv.index.name = "oc"
    piv.to_csv(OUT / "hour_curves.csv")
    print(f"  wrote hour_curves.csv  ({len(piv)} countries x 24 hours)")

    total = piv.sum(axis=1)
    keep = total[total >= 5000].index.astype(str).tolist()
    print(f"  {len(keep)} countries with at least 5,000 payments")

    ref = piv.loc[keep].sum(axis=0).values.astype(float)
    ref = ref / ref.sum()

    rows, aligned, normalised = [], [], []
    for c in keep:
        curve = piv.loc[c].values.astype(float)
        norm = curve / curve.sum()
        raw_r = float(np.corrcoef(norm, ref)[0, 1])
        best = max(((float(np.corrcoef(np.roll(norm, s), ref)[0, 1]), s) for s in range(24)))
        rows.append((c, raw_r, best[0], best[1], int(curve.sum())))
        aligned.append(np.roll(norm, best[1]))
        normalised.append(norm)

    tz = pd.DataFrame(rows, columns=["country", "corr_raw", "corr_aligned", "offset", "n"])
    tz = tz.sort_values("n", ascending=False)
    save(tz, "tz_shift.csv")

    # two ways of asking "do the country curves agree with each other":
    # against the pooled curve, and pairwise across all countries
    def pairwise(m):
        c = np.corrcoef(np.vstack(m))
        k = len(m)
        return float((c.sum() - np.trace(c)) / (k * (k - 1)))

    pair_raw, pair_align = pairwise(normalised), pairwise(aligned)
    print(f"  vs pooled:   before {tz.corr_raw.mean():.3f}  after {tz.corr_aligned.mean():.3f}")
    print(f"  pairwise:    before {pair_raw:.3f}  after {pair_align:.3f}")
    print(f"  distinct whole-hour offsets: {tz.offset.nunique()}")

    prof = pd.DataFrame({
        "h": range(24),
        "aligned": np.mean(aligned, axis=0),
        "unaligned": piv.loc[keep].div(total.loc[keep], axis=0).mean(axis=0).values,
        "flat": np.full(24, 1 / 24),
    })
    save(prof, "hour_profile.csv")
    (OUT / "hour_meta.json").write_text(json.dumps({
        "countries": len(keep), "offsets": int(tz.offset.nunique()),
        "pairwise_before": pair_raw, "pairwise_after": pair_align,
        "pooled_before": float(tz.corr_raw.mean()),
        "pooled_after": float(tz.corr_aligned.mean()),
    }, indent=2), encoding="utf-8")


def business_vs_retail(con) -> None:
    step("banks: median ticket by client class, per market")
    d = con.execute(f"""
        select {PATH_C} as cc, ORDERING_TYPE as ot, median(USD_AMOUNT) as med, count(*) as n
        from '{P}'
        where USD_AMOUNT > 0 and {CLEAN} and ORDERING_TYPE in ('B', 'C')
        group by 1, 2 having count(*) >= 300
    """).df()
    wide = d.pivot(index="cc", columns="ot", values="med")
    counts = d.pivot(index="cc", columns="ot", values="n")
    wide.columns = [f"{c.lower()}_med" for c in wide.columns]
    counts.columns = [f"{c.lower()}_n" for c in counts.columns]
    both = wide.dropna().join(counts)
    both["ratio"] = both.b_med / both.c_med
    both = both.reset_index().sort_values("b_med")
    save(both, "country_bc_medians.csv")
    print(f"  {len(both)} markets; median ratio {both.ratio.median():.2f}x")


def parties(con) -> None:
    step("parties: concentration of sending accounts, and the address decoy")
    d = con.execute(f"""
        select ORDERING_ACCOUNT as acct, count(*) as n
        from '{P}' where {CLEAN} group by 1 order by 2 desc
    """).df()
    n_accounts = len(d)
    whale = int((d.n >= 50).sum())
    whale_share = float(d.loc[d.n >= 50, "n"].sum() / d.n.sum())
    ben = int(con.execute(
        f"select count(distinct BENEFICIARY_ACCOUNT) b from '{P}' where {CLEAN}"
    ).df().b.iloc[0])

    cum = d.n.cumsum() / d.n.sum()
    share = np.arange(1, n_accounts + 1) / n_accounts
    pick = np.unique(np.linspace(0, n_accounts - 1, 400).astype(int))
    lorenz = pd.DataFrame({"share_accounts": share[pick], "share_payments": cum.values[pick]})
    save(lorenz, "sender_lorenz.csv")

    meta = {"accounts": n_accounts, "whales": whale, "whale_share": whale_share,
            "beneficiary_accounts": ben, "total_payments": int(d.n.sum())}
    (OUT / "party_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"  {n_accounts:,} accounts; {whale:,} with 50+ rows carry {whale_share*100:.1f}%")
    print(f"  {ben:,} distinct beneficiaries")


def main() -> None:
    con = connect()
    currency(con)
    amounts(con)
    duration(con)
    hours(con)
    business_vs_retail(con)
    parties(con)
    print("\ndone")


if __name__ == "__main__":
    main()
