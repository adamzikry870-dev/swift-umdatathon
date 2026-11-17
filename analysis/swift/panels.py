"""Build every table the dashboard reads, from the 10M-row parquet.

One function per panel group.  `build_all()` runs them in order and writes into
`dashboard/data/`; nothing here draws anything, and the dashboard never queries
the parquet itself.  That split is what makes each figure auditable: every number
on a panel exists as a row in a CSV first.
"""
from math import comb

import numpy as np
import pandas as pd

from .db import N_ROWS, PANEL_DATA, P, country, panel_path, save, sql

Q_FX = 0.851          # per-hop currency-border probability (panel 5)


# --------------------------------------------------------------------------- panel 1
def currency_panel(con, out):
    """Local-currency share by ordering country, and the mix of the foreign residual."""
    home = sql(con, f"""
        select {country('ORDERING_BIC8')} as cc, CURRENCY_CODE as cur, count(*) as n,
               row_number() over (partition by {country('ORDERING_BIC8')}
                                  order by count(*) desc) as rk
        from '{P}' group by 1, 2 qualify rk = 1
    """)
    save(home[["cc", "cur", "n"]].rename(columns={"cur": "home_currency"}),
         "country_home_currency.csv", out)
    home_map = dict(zip(home.cc, home.cur))

    cur = sql(con, f"""
        select {country('ORDERING_BIC8')} as oc, CURRENCY_CODE as cur, count(*) as n
        from '{P}' group by 1, 2
    """)
    cur["is_local"] = cur.cur == cur.oc.map(home_map)

    share = cur.groupby("oc").agg(n=("n", "sum"))
    share["local"] = (cur[cur.is_local].groupby("oc").n.sum()
                      .reindex(share.index).fillna(0).astype("int64"))
    share["local_share"] = share.local / share.n
    share = share.sort_values("n", ascending=False).reset_index()
    save(share, "currency_local_share.csv", out)

    foreign = (cur[~cur.is_local].groupby("cur").n.sum()
               .sort_values(ascending=False)
               .reset_index().rename(columns={"cur": "currency", "n": "payments"}))
    save(foreign, "currency_foreign_mix.csv", out)


# --------------------------------------------------------------------------- panel 2
def amount_panel(con, out):
    """Amount ladders by party pair: summary stats plus log10 histograms."""
    d = sql(con, f"""
        select ORDERING_TYPE as ot, BENEFICIARY_TYPE as bt, USD_AMOUNT as a
        from '{P}' where USD_AMOUNT > 0
    """)
    d["pair"] = d.ot + "\u2192" + d.bt
    stats = (d.groupby("pair").a
             .agg(count="count", median="median", mean="mean",
                  p05=lambda s: s.quantile(0.05), p95=lambda s: s.quantile(0.95))
             .sort_index().reset_index())
    save(stats, "amount_pair_stats.csv", out)

    hist = sql(con, f"""
        select ORDERING_TYPE || BENEFICIARY_TYPE as pair_code,
               floor(log10(USD_AMOUNT) * 10) / 10 as b,
               count(*) as n
        from '{P}' where USD_AMOUNT > 0
        group by 1, 2 order by 1, 2
    """)
    save(hist, "amount_hist.csv", out)


# --------------------------------------------------------------------------- panel 3
def routing_panel(con, out):
    """Chain length by transaction type (the geometric stopping process)."""
    d = sql(con, f"""
        select TRANSACTION_TYPE_CODE as tt, PARTICIPANT_COUNT as pc, count(*) as n
        from '{P}' group by 1, 2 order by 1, 2
    """)
    save(d, "participants_by_type.csv", out)


# --------------------------------------------------------------------------- panel 4
def continuity_panel(con, out):
    """Observed share of paths hiding at least one hop in '...'."""
    d = sql(con, f"""
        with t as (
            select PARTICIPANT_COUNT as pc,
                   (len(BIC8_PATH) - len(replace(BIC8_PATH, '...', ''))) / 3 as ell
            from '{P}'
        )
        select pc, count(*) as n,
               avg(case when ell > 0 then 1 else 0 end) as gap_rate,
               avg(ell) as mean_gaps, max(ell) as max_gaps
        from t where pc between 2 and 12 group by 1 order by 1
    """)
    save(d, "gap_rate_by_participants.csv", out)


# --------------------------------------------------------------------------- panel 5
def fx_panel(con, out):
    """Conversion counts per chain length, the endpoint heat map, and the binomial fit."""
    fx = sql(con, f"""
        select PARTICIPANT_COUNT as pc, CURRENCY_CONVERSION_COUNT as fx, count(*) as n
        from '{P}' where PARTICIPANT_COUNT between 2 and 9
        group by 1, 2 order by 1, 2
    """)
    save(fx, "fx_by_participants.csv", out)

    heat = sql(con, f"""
        with t as (
            select string_split(BIC8_PATH, ';') as s, CURRENCY_CONVERSION_COUNT as fx
            from '{P}' where PARTICIPANT_COUNT = 2
        )
        select substr(s[1], 5, 2) as oc, substr(s[len(s)], 5, 2) as bc,
               avg(fx) as p, count(*) as n
        from t group by 1, 2 having count(*) >= 300
    """)
    save(heat, "fx_heatmap.csv", out)

    rows = []
    for pc, group in fx.groupby("pc"):
        total = group.n.sum()
        for k in range(min(pc, 8)):
            observed = group.loc[group.fx == k, "n"].sum() / total
            predicted = comb(pc - 1, k) * Q_FX**k * (1 - Q_FX) ** (pc - 1 - k)
            rows.append((pc, k, observed, predicted))
    fit = pd.DataFrame(rows, columns=["pc", "fx", "obs", "pred"])
    fit["diff"] = fit.obs - fit.pred
    save(fit, "fx_binomial_fit.csv", out)


# --------------------------------------------------------------------------- panel 6
def duration_panel(con, out):
    """Median and p10/p90 duration by chain length and conversion count."""
    d = sql(con, f"""
        select PARTICIPANT_COUNT as pc, CURRENCY_CONVERSION_COUNT as fx, count(*) as n,
               median(TOTAL_DURATION) as med,
               quantile_cont(TOTAL_DURATION, 0.1) as p10,
               quantile_cont(TOTAL_DURATION, 0.9) as p90
        from '{P}'
        where PARTICIPANT_COUNT between 2 and 10
          and CURRENCY_CONVERSION_COUNT between 0 and 6
        group by 1, 2 having count(*) >= 300 order by 1, 2
    """)
    save(d, "duration_by_pc_fx.csv", out)


# --------------------------------------------------------------------------- panel 7
def time_panel(con, out):
    """Hourly curves (raw and shifted) and daily volume."""
    hour = sql(con, f"""
        select {country('ORDERING_BIC8')} as oc, (EPOCH_SECONDS // 3600) % 24 as h,
               count(*) as n
        from '{P}' group by 1, 2
    """)
    piv = hour.pivot(index="oc", columns="h", values="n").fillna(0)
    piv = piv.loc[piv.sum(axis=1).sort_values(ascending=False).head(45).index]

    # panel 7 reads this file with index_col=0
    piv.to_csv(panel_path("hour_raw_top.csv", out))

    reference = piv.sum(axis=0).values.astype(float)
    rows = []
    for ctry in piv.index:
        curve = piv.loc[ctry].values.astype(float)
        corr, shift = max((np.corrcoef(np.roll(curve, s), reference)[0, 1], s)
                          for s in range(24))
        rows.append((ctry, corr, shift))
    tz = pd.DataFrame(rows, columns=["country", "corr", "shift"])
    tz["n"] = piv.sum(axis=1).values
    tz = tz.sort_values("n", ascending=False)
    save(tz, "tz_shift.csv", out)

    aligned = {}
    for ctry in tz.head(24).country:
        curve = piv.loc[ctry].values.astype(float)
        shift = int(tz.loc[tz.country == ctry, "shift"].iloc[0])
        aligned[ctry] = np.roll(curve, shift) / curve.sum()
    pd.DataFrame(aligned).to_csv(panel_path("hour_aligned.csv", out))

    daily = sql(con, f"""
        select (EPOCH_SECONDS // 86400) * 86400 as d0, count(*) as n
        from '{P}' group by 1 order by 1
    """)
    daily["date"] = pd.to_datetime(daily.d0, unit="s", utc=True)
    daily["dow"] = daily.date.dt.dayofweek
    daily["week"] = daily.date.dt.isocalendar().week.astype(int)
    save(daily, "daily_volume.csv", out)


# --------------------------------------------------------------------------- panel 8
def anomaly_panel(con, out):
    """Typology x party pair, and the labelled-anomaly rate by beneficiary country."""
    typ = sql(con, f"""
        select ANOMALY_TYPE as a, ORDERING_TYPE as ot, BENEFICIARY_TYPE as bt, count(*) as n
        from '{P}' where coalesce(ANOMALY_TYPE, '') <> ''
        group by 1, 2, 3
    """)
    save(typ, "anomaly_typology_pair.csv", out)

    per_country = sql(con, f"""
        select {country('BENEFICIARY_BIC8')} as bc,
               count(*) filter (where coalesce(ANOMALY_TYPE, '') <> '') as anom,
               count(*) as total
        from '{P}' group by 1
    """)
    per_country["rate"] = per_country.anom / per_country.total
    per_country = (per_country[per_country.anom > 0]
                   .sort_values("anom", ascending=False)
                   .reset_index(drop=True))
    save(per_country[["bc", "anom", "total", "rate"]],
         "anomaly_by_beneficiary_country.csv", out)


# --------------------------------------------------------------------------- panel 9
def bank_panel(con, out):
    """Bank population by country and the concentration of intermediate hops."""
    banks = sql(con, f"""
        select {country('ORDERING_BIC8')} as cc,
               count(distinct ORDERING_BIC8) as b, count(*) as n
        from '{P}' group by 1 order by 2 desc
    """)
    save(banks, "bank_count_by_country.csv", out)

    inter = sql(con, f"""
        with t as (
            select string_split(BIC8_PATH, ';') as parts from '{P}'
            where PARTICIPANT_COUNT >= 3 and not contains(BIC8_PATH, '...')
        )
        select unnest(list_slice(parts, 2, len(parts) - 1)) as bic, count(*) as n
        from t group by 1
    """)
    inter = (inter.sort_values(["n", "bic"], ascending=[False, True])
                  .reset_index(drop=True))
    inter["share"] = inter.n / inter.n.sum()
    inter["cum"] = inter.share.cumsum()
    save(inter, "intermediary_concentration.csv", out)


# --------------------------------------------------------------------------- panel 10
def token_panel(con, out):
    """Country-token agreement rates, and address share vs bank share."""
    counts = sql(con, f"""
        with t as (
            select regexp_extract(ORDERING_TOKENS, 'country_code:([A-Z]{{2}})', 1) as otok,
                   regexp_extract(BENEFICIARY_TOKENS, 'country_code:([A-Z]{{2}})', 1) as btok,
                   {country('ORDERING_BIC8')} as oc,
                   {country('BENEFICIARY_BIC8')} as bc
            from '{P}'
        )
        select count(*) as n_rows,
               count(*) filter (where otok <> '') as o_present,
               count(*) filter (where otok <> '' and otok = oc) as o_match,
               count(*) filter (where btok <> '') as b_present,
               count(*) filter (where btok <> '' and btok = bc) as b_match
        from t
    """).iloc[0]

    agreement = {
        "n_rows": int(counts.n_rows),
        "ordering_token_present": counts.o_present / counts.n_rows,
        "ordering_match_when_present": counts.o_match / counts.o_present,
        "beneficiary_token_present": counts.b_present / counts.n_rows,
        "beneficiary_match_when_present": counts.b_match / counts.b_present,
    }
    import json
    panel_path("token_agreement.json", out).write_text(
        json.dumps(agreement, indent=2), encoding="utf-8")

    top = sql(con, f"""
        select regexp_extract(BENEFICIARY_TOKENS, 'country_code:([A-Z]{{2}})', 1) as country,
               count(*) as tokens
        from '{P}' where BENEFICIARY_TOKENS like '%country_code:%'
        group by 1 order by 2 desc limit 12
    """)
    banks = sql(con, f"""
        select {country('BENEFICIARY_BIC8')} as country, count(*) as bank_n
        from '{P}' group by 1
    """)
    table = (top.merge(banks, on="country", how="left")
                .fillna({"bank_n": 0}).head(10))
    table["token_share"] = table.tokens / N_ROWS
    table["bank_share"] = table.bank_n / N_ROWS
    save(table.rename(columns={"tokens": "token_n"})[
        ["country", "token_n", "bank_n", "token_share", "bank_share"]],
        "token_vs_bank_share.csv", out)


SECTIONS = [
    ("1  currency", currency_panel),
    ("2  amounts", amount_panel),
    ("3  routing", routing_panel),
    ("4  continuity", continuity_panel),
    ("5  fx", fx_panel),
    ("6  duration", duration_panel),
    ("7  time", time_panel),
    ("8  anomalies", anomaly_panel),
    ("9  banks", bank_panel),
    ("10 tokens", token_panel),
]


def build_all(con, out="."):
    """Run every section, writing into `out` (relative to dashboard/data)."""
    for label, section in SECTIONS:
        print(f"panel {label} ...", flush=True)
        section(con, out)
    print(f"done -> {PANEL_DATA / out}")
