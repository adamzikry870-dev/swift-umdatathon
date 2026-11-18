"""Pull the few aggregates the deck needs that are not already in dashboard/data.

Everything here is a one-off read of analysis/payments.parquet; the outputs are
small CSVs under deck/data/ so the deck itself can be rebuilt without the 1.3 GB
file.  Run:  python deck/extract.py
"""
import os
import numpy as np
import pandas as pd
import duckdb

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "analysis", "payments.parquet")
OUT = os.path.join(ROOT, "deck", "data")
os.makedirs(OUT, exist_ok=True)

con = duckdb.connect()
CLEAN = "ANOMALY_TYPE IS NULL"


def save(df, name):
    path = os.path.join(OUT, name)
    df.to_csv(path, index=False)
    print(f"  {name:34s} {len(df):>6d} rows")


# ----------------------------------------------------------------- g1: clocks
print("g1 · hourly curves and alignment")
h = con.sql(f"""
    SELECT substr(split_part(BIC8_PATH,';',1),5,2) AS cc,
           CAST((EPOCH_SECONDS // 3600) % 24 AS INTEGER) AS h,
           count(*) AS n
    FROM '{P}' WHERE {CLEAN}
    GROUP BY 1,2
""").df()
piv = h.pivot(index="cc", columns="h", values="n").fillna(0)
piv = piv[piv.sum(axis=1) >= 5000]
C = piv.div(piv.sum(axis=1), axis=0).to_numpy()
names = piv.index.to_numpy()


def mean_pair(X):
    Xc = X - X.mean(axis=1, keepdims=True)
    Xc /= np.linalg.norm(Xc, axis=1, keepdims=True)
    M = Xc @ Xc.T
    iu = np.triu_indices(len(X), 1)
    return float(M[iu].mean())


raw_pair = mean_pair(C)
# iterative centroid alignment, starting from each country's own peak
shifts = C.argmax(axis=1)
ref = np.vstack([np.roll(r, -k) for r, k in zip(C, shifts)]).mean(axis=0)
for _ in range(10):
    shifts = np.array([
        max(range(24), key=lambda k, r=r: np.corrcoef(np.roll(r, -k), ref)[0, 1])
        for r in C
    ])
    ref = np.vstack([np.roll(r, -k) for r, k in zip(C, shifts)]).mean(axis=0)

A = np.vstack([np.roll(r, -k) for r, k in zip(C, shifts)])
corr_to_ref = np.array([np.corrcoef(a, ref)[0, 1] for a in A])
print(f"  raw pairwise {raw_pair:+.3f} | aligned pairwise {mean_pair(A):+.3f}"
      f" | mean corr to template {corr_to_ref.mean():.3f} (min {corr_to_ref.min():.3f})"
      f" | distinct shifts {len(np.unique(shifts))}")

curve = pd.DataFrame({
    "hour": np.arange(24),
    "template": A.mean(axis=0) / A.mean(axis=0).sum(),
    "raw_utc": C.mean(axis=0) / C.mean(axis=0).sum(),
    "p10": np.percentile(A, 10, axis=0) / A.mean(axis=0).sum(),
    "p90": np.percentile(A, 90, axis=0) / A.mean(axis=0).sum(),
})
save(curve, "g1_template.csv")
save(pd.DataFrame({"cc": names, "shift": shifts, "corr": corr_to_ref,
                   "rows": piv.sum(axis=1).to_numpy()}),
     "g1_country_clocks.csv")
pd.DataFrame([{"raw_pair": raw_pair, "aligned_pair": mean_pair(A),
               "corr_to_template": corr_to_ref.mean(),
               "countries": len(C), "shifts": len(np.unique(shifts))}
              ]).to_csv(os.path.join(OUT, "g1_summary.csv"), index=False)

# ------------------------------------------------------- g3: ladder and shape
print("g3 · amount ladder")
lad = con.sql(f"""
    SELECT substr(split_part(BIC8_PATH,';',1),5,2) AS cc,
           count(*) AS n,
           median(USD_AMOUNT) AS median_usd,
           median(log10(USD_AMOUNT)) AS mu
    FROM '{P}' WHERE {CLEAN} AND USD_AMOUNT > 0
    GROUP BY 1 HAVING count(*) >= 2000
""").df()
save(lad, "g3_ladder.csv")

hist = con.sql(f"""
    SELECT CAST(floor(log10(USD_AMOUNT) * 20) AS INTEGER) AS b, count(*) AS n
    FROM '{P}' WHERE {CLEAN} AND USD_AMOUNT > 0
    GROUP BY 1 ORDER BY 1
""").df()
save(hist, "g3_shape.csv")

storms = con.sql(f"""
    WITH t AS (
      SELECT CURRENCY_CODE AS cur, round(USD_AMOUNT,2) AS amt,
             CAST(EPOCH_SECONDS/86400 AS INTEGER) AS d
      FROM '{P}' WHERE {CLEAN}
    ), g AS (
      SELECT cur, amt, d, count(*) AS n FROM t GROUP BY 1,2,3
    ), tot AS (
      SELECT cur, amt, sum(n) AS n_all FROM g GROUP BY 1,2
    )
    SELECT g.cur, g.amt, g.d, g.n, tot.n_all
    FROM g JOIN tot USING (cur, amt)
    WHERE g.n >= 100 AND g.n * 2 >= tot.n_all
    ORDER BY g.n DESC
""").df()
storms["date"] = pd.to_datetime(storms.d * 86400, unit="s").dt.strftime("%Y-%m-%d")
save(storms, "g3_storms.csv")

# ------------------------------------------------------- g4: B/C per country
print("g4 · country x client type")
bc = con.sql(f"""
    SELECT substr(split_part(BIC8_PATH,';',1),5,2) AS cc,
           median(CASE WHEN ORDERING_TYPE='C' THEN log10(USD_AMOUNT) END) AS retail,
           median(CASE WHEN ORDERING_TYPE='B' THEN log10(USD_AMOUNT) END) AS business,
           count(*) FILTER (WHERE ORDERING_TYPE='C') AS n_retail,
           count(*) FILTER (WHERE ORDERING_TYPE='B') AS n_business
    FROM '{P}' WHERE {CLEAN} AND USD_AMOUNT > 0
    GROUP BY 1
""").df()
bc = bc[(bc.n_retail >= 300) & (bc.n_business >= 300)]
save(bc, "g4_bc_countries.csv")

# ------------------------------------------------------------ g6: by length
print("g6 · duration by chain length")
dur = con.sql(f"""
    SELECT PARTICIPANT_COUNT AS pc, count(*) AS n,
           median(TOTAL_DURATION) AS med,
           quantile_cont(TOTAL_DURATION,0.25) AS p25,
           quantile_cont(TOTAL_DURATION,0.75) AS p75
    FROM '{P}' WHERE {CLEAN} AND PARTICIPANT_COUNT BETWEEN 2 AND 8
    GROUP BY 1 ORDER BY 1
""").df()
save(dur, "g6_length.csv")

# --------------------------------------------------- g7: sender concentration
print("g7 · sender concentration")
conc = con.sql(f"""
    WITH s AS (
      SELECT ORDERING_ACCOUNT AS a, count(*) AS n
      FROM '{P}' WHERE {CLEAN} GROUP BY 1
    ), r AS (
      SELECT n, row_number() OVER (ORDER BY n DESC) AS rk,
             sum(n) OVER () AS tot, count(*) OVER () AS nacc
      FROM s
    )
    SELECT rk, n, tot, nacc FROM r ORDER BY rk
""").df()
conc["cum_share"] = conc.n.cumsum() / conc.tot.iloc[0]
conc = conc.iloc[::200]
save(conc, "g7_sender_conc.csv")

# --------------------------------------------------------------- g8: labels
print("g8 · exception labels")
lab = con.sql(f"""
    SELECT ANOMALY_TYPE AS label, count(*) AS n,
           median(USD_AMOUNT) AS median_usd,
           median(TOTAL_DURATION) AS median_sec,
           avg(CASE WHEN TRANSACTION_TYPE_CODE='Covered' THEN 1 ELSE 0 END)*100 AS covered_pct
    FROM '{P}' WHERE ANOMALY_TYPE IS NOT NULL
    GROUP BY 1 ORDER BY 2 DESC
""").df()
save(lab, "g8_labels.csv")

base = con.sql(f"""
    SELECT count(*) AS n,
           avg(CASE WHEN TRANSACTION_TYPE_CODE='Covered' THEN 1 ELSE 0 END)*100 AS covered_pct,
           median(USD_AMOUNT) AS median_usd,
           median(TOTAL_DURATION) AS median_sec
    FROM '{P}' WHERE {CLEAN}
""").df()
base.to_csv(os.path.join(OUT, "g8_base.csv"), index=False)
print(base.to_string(index=False))

print("\nwrote ->", OUT)
