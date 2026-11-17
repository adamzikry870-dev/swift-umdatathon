"""Build `analysis/payments.parquet` from the raw 5 GB CSV (run once).

The CSV opens with a quoted, multi-line DISCLAIMER column; this keeps only the
20 analysis columns, in a fixed order, typed by DuckDB's sniffer.

    python analysis/convert_csv.py           # skip if the parquet already exists
    python analysis/convert_csv.py --force   # rebuild
"""
import argparse
import time

import duckdb

from swift.db import DATA, RAW_CSV

COLUMNS = [
    "EPOCH_SECONDS", "CURRENCY_CODE", "USD_AMOUNT",
    "ORDERING_BIC8", "BENEFICIARY_BIC8", "BIC8_PATH", "TOTAL_DURATION",
    "CONTINUITY_QFLAG", "CURRENCY_CONVERSION_COUNT", "PARTICIPANT_COUNT",
    "TRANSACTION_TYPE_CODE", "ORDERING_ACCOUNT", "BENEFICIARY_ACCOUNT",
    "ORDERING_DETAILS", "ORDERING_TOKENS",
    "BENEFICIARY_DETAILS", "BENEFICIARY_TOKENS",
    "ORDERING_TYPE", "BENEFICIARY_TYPE", "ANOMALY_TYPE",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="rebuild even if present")
    args = parser.parse_args()

    if DATA.exists() and not args.force:
        print(f"{DATA} already exists ({DATA.stat().st_size/1e9:.1f} GB); use --force to rebuild")
        return
    if not RAW_CSV.exists():
        raise SystemExit(f"raw CSV not found: {RAW_CSV}")

    started = time.time()
    con = duckdb.connect()
    con.execute("SET threads=8")
    con.execute("SET memory_limit='10GB'")
    con.execute(f"""
        COPY (
            SELECT {", ".join(COLUMNS)}
            FROM read_csv('{RAW_CSV.as_posix()}', header=true)
        ) TO '{DATA.as_posix()}'
        (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 200000)
    """)
    rows = con.execute(f"select count(*) from '{DATA.as_posix()}'").fetchone()[0]
    print(f"wrote {DATA} · {rows:,} rows · {time.time() - started:.0f}s")


if __name__ == "__main__":
    main()
