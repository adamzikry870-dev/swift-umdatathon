"""Regenerate every table in dashboard/data from analysis/payments.parquet.

Usage
    python analysis/build_data.py            # writes dashboard/data/
    python analysis/build_data.py --out tmp  # writes dashboard/data/tmp/ for a diff

The dashboard only reads these CSVs, so this script is the single place where
dataset -> figure numbers happens.
"""
import argparse

from swift import db, panels


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=".", help="subfolder of dashboard/data to write")
    args = ap.parse_args()
    con = db.connect()
    panels.build_all(con, args.out)


if __name__ == "__main__":
    main()
