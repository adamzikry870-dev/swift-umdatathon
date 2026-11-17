"""Re-derive every headline number in the two documents and report PASS/FAIL.

Each check states the value quoted in `docs/`, recomputes it from the parquet,
and compares.  This is the regression suite for the analysis: if a query or the
dataset changes, a claim breaks here rather than in a figure.

    python analysis/verify.py             # all checks
    python analysis/verify.py --quick     # skip the two duration model fits
"""
import json
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .db import N_ROWS, PANEL_DATA, P, country, load, sql


@dataclass
class Report:
    rows: list = field(default_factory=list)

    def check(self, label, expected, actual, tol=0.0, unit=""):
        ok = abs(float(actual) - float(expected)) <= tol
        self.rows.append((label, f"{expected}{unit}", f"{actual}{unit}", ok))

    def exact(self, label, expected, actual):
        self.rows.append((label, str(expected), str(actual), expected == actual))

    @property
    def passed(self):
        return all(row[3] for row in self.rows)

    def table(self):
        widths = [max(len(str(row[i])) for row in self.rows) for i in range(3)]
        head = (f"{'check':<{widths[0]}}  {'documented':>{widths[1]}}  "
                f"{'recomputed':>{widths[2]}}  result")
        body = [f"{a:<{widths[0]}}  {b:>{widths[1]}}  {c:>{widths[2]}}  "
                f"{'ok' if ok else 'FAIL'}" for a, b, c, ok in self.rows]
        return "\n".join([head] + body)


# ------------------------------------------------------------------ dataset shape
def dataset(con, rep):
    rows = sql(con, f"select count(*) as n from '{P}'").iloc[0].n
    rep.exact("rows", N_ROWS, int(rows))
    columns = len(con.execute(f"describe select * from '{P}'").df())
    rep.exact("columns", 20, columns)
    span = sql(con, f"""
        select strftime(to_timestamp(min(EPOCH_SECONDS)), '%Y-%m-%d') as first_day,
               strftime(to_timestamp(max(EPOCH_SECONDS)), '%Y-%m-%d') as last_day
        from '{P}'""").iloc[0]
    print(f"  coverage {span.first_day} -> {span.last_day}")


# ------------------------------------------------------------------ path structure
def path_structure(con, rep):
    d = sql(con, f"""
        select avg(case when PARTICIPANT_COUNT =
                            len(list_filter(string_split(BIC8_PATH, ';'),
                                            lambda x: x <> '...'))
                        then 1 else 0 end) as pc_ok,
               avg(case when split_part(BIC8_PATH, ';', 1) = ORDERING_BIC8
                        then 1 else 0 end) as head_ok,
               avg(case when split_part(BIC8_PATH, ';', -1) = BENEFICIARY_BIC8
                        then 1 else 0 end) as tail_ok,
               avg(case when contains(BIC8_PATH, '...') = (CONTINUITY_QFLAG = 'N')
                        then 1 else 0 end) as flag_ok,
               avg(case when split_part(BIC8_PATH, ';', 1) = ORDERING_BIC8
                         and split_part(BIC8_PATH, ';', -1) = BENEFICIARY_BIC8
                        then 1 else 0 end) as both_ok
        from '{P}'""").iloc[0]
    rep.check("real nodes == PARTICIPANT_COUNT", 1.0, d.pc_ok, 0.0)
    rep.check("path head == ORDERING_BIC8", 0.95, d.head_ok, 5e-4)
    rep.check("path tail == BENEFICIARY_BIC8", 0.95, d.tail_ok, 5e-4)
    rep.check("both ends correct (0.95 x 0.95)", 0.9027, d.both_ok, 5e-4)
    rep.check("'...' agrees with CONTINUITY_QFLAG", 1.0, d.flag_ok, 0.0)


# ------------------------------------------------------------------ truncation law
def truncation(con, rep):
    d = load("gap_rate_by_participants.csv")
    p = d.loc[d.pc == 2, "gap_rate"].iloc[0]
    predicted = 1 - (1 - p) ** (d.pc - 1)
    z = (d.gap_rate - predicted) / np.sqrt(d.gap_rate * (1 - d.gap_rate) / d.n)
    rep.check("per-hop hide probability p", 0.0499, p, 5e-5)
    rep.check("gap rate at n=2", 0.0499, d.loc[d.pc == 2, "gap_rate"].iloc[0], 5e-5)
    rep.check("gap rate at n=12", 0.4323, d.loc[d.pc == 12, "gap_rate"].iloc[0], 5e-4)
    rep.check("max |z| across lengths", 2.34, float(np.abs(z).max()), 0.01)
    rep.exact("lengths tested", 11, len(d))


# ------------------------------------------------------------------ routing law
def routing(con, rep):
    d = load("participants_by_type.csv")
    indirect = d[(d.tt == "Indirect") & (d.pc >= 3)].sort_values("pc")
    share = indirect.n / indirect.n.sum()
    continuation = float((share.iloc[1:] / share.iloc[:-1].values).median())
    rep.check("continuation probability per hop", 0.368, continuation, 2e-3)
    rep.check("first geometric term (k=3)", 0.632, share.iloc[0], 2e-3)
    rep.exact("Direct payments not at pc=2",
              0, int(d[(d.tt == "Direct") & (d.pc != 2)].n.sum()))
    rep.exact("maximum chain length", 22, int(d.pc.max()))


# ------------------------------------------------------------------ conversion count
def conversions(con, rep):
    """Recompute every conversion count from the path and each country's currency."""
    sql(con, f"""
        create or replace temp table home as
        select cc, home_currency
        from read_csv_auto('{(PANEL_DATA / "country_home_currency.csv").as_posix()}')
    """)
    d = sql(con, f"""
        with m as (select map_from_entries(list_zip(list(cc), list(home_currency))) as cmap
                   from home),
        t as (
            select CURRENCY_CONVERSION_COUNT as stored, PARTICIPANT_COUNT as pc,
                   list_transform(
                       list_filter(string_split(BIC8_PATH, ';'), lambda x: x <> '...'),
                       lambda x: coalesce(m.cmap[substr(x, 5, 2)], '?')) as curs
            from '{P}', m
        )
        select avg(case when len(list_filter(range(1, len(curs)),
                        lambda i: curs[i] <> curs[i + 1])) = stored then 1 else 0 end) as exact,
               max(stored) as max_stored,
               max(pc) - 1 as max_allowed
        from t
    """).iloc[0]
    rep.check("conversions recomputed from path", 1.0, d.exact, 0.0)
    rep.exact("conversions <= participants - 1", True, bool(d.max_stored <= d.max_allowed))


# ------------------------------------------------------------------ currency choice
def currency(con, rep):
    d = load("currency_local_share.csv")
    rep.check("local-currency share, all payments",
              0.894, d.local.sum() / d.n.sum(), 5e-4)
    top20 = d.sort_values("n", ascending=False).head(20)
    rep.check("lowest local share in the top 20 (AU/CA)", 0.84,
              top20.local_share.min(), 0.005)
    mix = load("currency_foreign_mix.csv")
    share = mix.payments / mix.payments.sum()
    rep.check("EUR share of the foreign residual", 0.440, share.iloc[0], 2e-3)
    rep.check("USD share of the foreign residual", 0.219, share.iloc[1], 2e-3)


# ------------------------------------------------------------------ amount ladder
def amounts(con, rep):
    d = load("amount_pair_stats.csv").set_index("pair")
    for pair, expected in [("B\u2192B", 22888), ("B\u2192C", 3119),
                           ("C\u2192B", 3229), ("C\u2192C", 463)]:
        rep.check(f"median {pair}", expected, d.loc[pair, "median"], 1)
    ratio = d.loc["B\u2192B", "median"] / d.loc["C\u2192C", "median"]
    rep.check("B->B / C->C median ratio", 49.4, ratio, 0.1)


# ------------------------------------------------------------------ fx distribution
def fx(con, rep):
    fit = load("fx_binomial_fit.csv")
    rep.check("max |observed - binomial| share", 0.039, fit["diff"].abs().max(), 5e-4)
    d = load("fx_by_participants.csv")
    pc2 = d[d.pc == 2]
    rep.check("pc=2 conversions all 0 or 1", 1.0,
              pc2[pc2.fx.isin([0, 1])].n.sum() / pc2.n.sum(), 0.0)


# ------------------------------------------------------------------ latency
def duration(con, rep):
    d = load("duration_by_pc_fx.csv")
    fixed = d[d.fx == 1].set_index("pc")
    rep.check("median duration at n=2, fx=1", 38, fixed.loc[2, "med"], 1)
    rep.check("median duration at n=6, fx=1", 804, fixed.loc[6, "med"], 1)
    rep.check("end-to-end ratio n=6 / n=2", 21.2, fixed.loc[6, "med"] / fixed.loc[2, "med"], 0.3)

    spread = sql(con, f"""
        with p as (
            select count(*) as n,
                   quantile_cont(TOTAL_DURATION, 0.1) as p10,
                   quantile_cont(TOTAL_DURATION, 0.9) as p90
            from '{P}' where PARTICIPANT_COUNT = 2
            group by ORDERING_BIC8, BENEFICIARY_BIC8 having count(*) >= 200
        )
        select median(p90 - p10) as spread from p
    """).iloc[0].spread
    rep.check("within-pair p90 - p10 (seconds)", 17, spread, 3)


def duration_models(con, rep):
    """A route effect, not a bank effect: three fits, none of them good enough."""
    _additive_dense(con, rep)

    d = sql(con, f"""
        select ORDERING_BIC8 as o, BENEFICIARY_BIC8 as b,
               median(TOTAL_DURATION) as med, count(*) as n
        from '{P}' where PARTICIPANT_COUNT = 2
        group by 1, 2 having count(*) >= 100
    """)
    d["oc"] = d.o.str[4:6]
    d["bc"] = d.b.str[4:6]
    log_y = np.log(d.med.to_numpy(dtype=float))
    fold = np.random.default_rng(0).integers(0, 5, len(d))
    for label, columns, expected in [
        ("cross-validated log R2, bank effects", ["o", "b"], 0.46),
        ("cross-validated log R2, country pairs", ["oc", "bc"], 0.10),
    ]:
        predicted = np.zeros(len(d))
        for k in range(5):
            train = np.where(fold != k)[0]
            test = np.where(fold == k)[0]
            predicted[test] = _backfit(d, log_y, train, test, columns)
        r2_out = 1 - ((log_y - predicted) ** 2).sum() / ((log_y - log_y.mean()) ** 2).sum()
        rep.check(label, expected, r2_out, 0.03)


def _additive_dense(con, rep):
    """Per-bank delay added at each end, tested where both banks are well observed.

    The full pair list is too sparse to tell an additive model apart from noise
    (it fits almost anything).  Restricting to banks that appear in >= 10 of the
    >= 200-payment pairs gives a 712-pair dense graph, where an additive
    bank-effect model reaches only R2 = 0.21 in levels.
    """
    d = sql(con, f"""
        select ORDERING_BIC8 as o, BENEFICIARY_BIC8 as b,
               median(TOTAL_DURATION) as med, count(*) as n
        from '{P}' where PARTICIPANT_COUNT = 2
        group by 1, 2 having count(*) >= 200
    """)
    partners = pd.concat([d.o, d.b]).value_counts()
    dense = d[(d.o.map(partners) >= 10) & (d.b.map(partners) >= 10)]

    banks = sorted(set(dense.o) | set(dense.b))
    index = {b: i for i, b in enumerate(banks)}
    A = np.zeros((len(dense), len(banks)))
    A[:, 0] = 1                                  # intercept rides on column 0
    for row, (o, b) in enumerate(zip(dense.o, dense.b)):
        A[row, index[o]] += 1
        A[row, index[b]] += 1

    y = dense.med.to_numpy(dtype=float)
    fitted = A @ np.linalg.lstsq(A, y, rcond=None)[0]
    r2 = 1 - ((y - fitted) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    rep.check("additive bank model, dense subgraph, R2 in levels", 0.21, r2, 0.01)
    rep.exact("dense-subgraph pairs", 712, len(dense))


def _backfit(df, log_y, train, test, columns, iterations=40):
    """Two-way fixed effects fitted on the training rows, applied to the test rows."""
    levels = {c: sorted(set(df[c].iloc[train]) | set(df[c].iloc[test])) for c in columns}
    effects = {c: pd.Series(0.0, index=levels[c]) for c in columns}
    tr, te = df.iloc[train], df.iloc[test]
    pred = np.zeros(len(train))
    for _ in range(iterations):
        for c in columns:
            partial = pred - effects[c].reindex(tr[c]).to_numpy()
            means = pd.Series(log_y[train] - partial).groupby(tr[c].to_numpy()).mean()
            effects[c] = means.reindex(levels[c]).fillna(0.0)
        pred = sum(effects[c].reindex(tr[c]).to_numpy() for c in columns)
    offset = log_y[train].mean() - pred.mean()
    return sum(effects[c].reindex(te[c]).to_numpy() for c in columns) + offset


# ------------------------------------------------------------------ anomalies
def anomalies(con, rep):
    d = sql(con, f"""
        select coalesce(ANOMALY_TYPE, '') as a,
               {country('BENEFICIARY_BIC8')} as bc, count(*) as n
        from '{P}' group by 1, 2
    """)
    labelled = d[d.a != ""]
    rep.exact("labelled anomalies", 7006, int(labelled.n.sum()))
    per_country = load("anomaly_by_beneficiary_country.csv")
    rep.check("pooled rate across labelled countries, per 100k",
              70.7, per_country.anom.sum() / per_country.total.sum() * 1e5, 0.2)

    totals = d.groupby("bc").n.sum()
    for ctry, expected in [("PK", 7914), ("US", 32.7)]:
        rate = labelled[labelled.bc == ctry].n.sum() / totals[ctry] * 1e5
        rep.check(f"rate per 100k, {ctry}", expected, rate, 5 if expected > 100 else 0.5)

    mix = load("anomaly_typology_pair.csv")
    for typology, side in [("ROMANCE_SCAM", "C"), ("CEO_SCAM", "B")]:
        rows = mix[mix.a == typology]
        share = rows[rows.ot == side].n.sum() / rows.n.sum()
        rep.check(f"{typology} sent by {side}", 1.0, share, 0.0)


# ------------------------------------------------------------------ party text
def tokens(con, rep):
    a = json.loads((PANEL_DATA / "token_agreement.json").read_text(encoding="utf-8"))
    rep.check("ordering token present", 0.608, a["ordering_token_present"], 5e-4)
    rep.check("ordering address matches bank country",
              1.0, a["ordering_match_when_present"], 0.0)
    rep.check("beneficiary token present", 0.611, a["beneficiary_token_present"], 5e-4)
    rep.check("beneficiary address matches bank country",
              0.0098, a["beneficiary_match_when_present"], 2e-4)


# ------------------------------------------------------------------ banks
def banks(con, rep):
    d = sql(con, f"""
        select count(distinct ORDERING_BIC8) as banks,
               count(distinct {country('ORDERING_BIC8')}) as countries
        from '{P}'
    """).iloc[0]
    rep.exact("distinct banks", 8392, int(d.banks))
    rep.exact("bank countries", 228, int(d.countries))
    inter = load("intermediary_concentration.csv")
    for k, expected in [(10, 0.192), (100, 0.519), (1000, 0.928)]:
        rep.check(f"top {k:,} intermediaries, cumulative share",
                  expected, inter.cum.iloc[k - 1], 2e-3)


# ------------------------------------------------------------------ runner
SECTIONS = [
    ("dataset", dataset),
    ("path structure", path_structure),
    ("truncation", truncation),
    ("routing", routing),
    ("conversions", conversions),
    ("currency", currency),
    ("amounts", amounts),
    ("fx", fx),
    ("duration", duration),
    ("anomalies", anomalies),
    ("tokens", tokens),
    ("banks", banks),
]


def run(con, quick=False):
    rep = Report()
    sections = list(SECTIONS)
    if not quick:
        sections.insert(9, ("duration models", duration_models))
    for label, fn in sections:
        print(f"[{label}]", flush=True)
        fn(con, rep)
    return rep
