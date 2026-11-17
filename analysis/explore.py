"""Look at the dataset without writing a throwaway script.

    python analysis/explore.py                    # schema, coverage, five sample rows
    python analysis/explore.py --head 20          # more sample rows
    python analysis/explore.py --count ANOMALY_TYPE
    python analysis/explore.py --count CURRENCY_CODE --limit 30
    python analysis/explore.py --sql "select * from {P} limit 5"

`{P}` in --sql expands to the quoted parquet path, so write `from {P}`.
"""
import argparse

from swift.db import P, columns, connect, sql


def show_schema(con):
    print(con.execute(f"describe select * from '{P}'").df().to_string(index=False))


def show_coverage(con):
    row = sql(con, f"""
        select count(*) as rows,
               count(distinct CURRENCY_CODE) as currencies,
               count(distinct ORDERING_BIC8) as banks,
               count(distinct substr(ORDERING_BIC8, 5, 2)) as countries,
               strftime(to_timestamp(min(EPOCH_SECONDS)), '%Y-%m-%d') as first_day,
               strftime(to_timestamp(max(EPOCH_SECONDS)), '%Y-%m-%d') as last_day
        from '{P}'
    """).iloc[0]
    print(f"\n{row.rows:,} rows · {row.currencies} currencies · {row.banks:,} banks · "
          f"{row.countries} countries · {row.first_day} to {row.last_day}")


def show_head(con, n):
    print()
    print(sql(con, f"select * from '{P}' limit {n}").to_string(index=False))


def show_counts(con, column, limit):
    if column not in columns():
        raise SystemExit(f"unknown column {column!r}; try one of: {', '.join(columns())}")
    print(sql(con, f"""
        select {column} as value, count(*) as n,
               round(100.0 * count(*) / sum(count(*)) over (), 2) as pct
        from '{P}' group by 1 order by n desc limit {limit}
    """).to_string(index=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--head", type=int, default=5, help="sample rows to print")
    parser.add_argument("--count", metavar="COLUMN", help="value counts for one column")
    parser.add_argument("--limit", type=int, default=20, help="rows in a value-count table")
    parser.add_argument("--sql", help="run a query; {P} is the parquet path")
    args = parser.parse_args()

    con = connect()
    if args.sql:
        print(sql(con, args.sql.replace("{P}", f"'{P}'")).to_string(index=False))
        return
    if args.count:
        show_counts(con, args.count, args.limit)
        return
    show_schema(con)
    show_coverage(con)
    show_head(con, args.head)


if __name__ == "__main__":
    main()
