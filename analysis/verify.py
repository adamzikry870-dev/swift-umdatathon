"""Check that the documented numbers still hold.  Exit code 1 on any failure.

    python analysis/verify.py            # everything (includes two 5-fold model fits)
    python analysis/verify.py --quick    # skip the model fits, ~10 seconds
"""
import argparse

from swift import db, rules


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quick", action="store_true", help="skip the duration model fits")
    args = ap.parse_args()

    report = rules.run(db.connect(), quick=args.quick)
    print()
    print(report.table())
    print()
    print(f"{sum(r[3] for r in report.rows)}/{len(report.rows)} checks passed")
    raise SystemExit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
