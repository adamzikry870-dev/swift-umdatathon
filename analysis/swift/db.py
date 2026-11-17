"""Shared plumbing for the analysis scripts: paths, a DuckDB connection, small helpers.

Every other module imports from here, so there is exactly one definition of the
dataset path, the row count and the country-from-BIC rule.
"""
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "analysis" / "payments.parquet"
RAW_CSV = ROOT / "swift_umdac_datathon_2026_fictitious_payment_data.csv"
PANEL_DATA = ROOT / "dashboard" / "data"

N_ROWS = 10_000_000
P = DATA.as_posix()          # quoted inside SQL as '{P}'


def connect(memory: str = "12GB", threads: int = 8) -> duckdb.DuckDBPyConnection:
    """A DuckDB connection tuned for the 10M-row parquet."""
    con = duckdb.connect()
    con.execute(f"SET threads={threads}")
    con.execute(f"SET memory_limit='{memory}'")
    return con


def sql(con, query: str) -> pd.DataFrame:
    """Run a query and return a DataFrame."""
    return con.execute(query).df()


def country(bic_col: str) -> str:
    """SQL expression for the ISO country of a BIC8: characters 5-6."""
    return f"substr({bic_col}, 5, 2)"


def columns() -> list[str]:
    """The parquet's column names, in file order."""
    con = connect()
    return list(con.execute(f"describe select * from '{P}'").df().column_name)


def panel_path(name: str, out: Path | str = ".") -> Path:
    """Resolve a file under `dashboard/data`; `out` is a subfolder used by dry runs."""
    folder = Path(out)
    if not folder.is_absolute():
        folder = PANEL_DATA / folder
    folder.mkdir(parents=True, exist_ok=True)
    return folder / name


def save(df: pd.DataFrame, name: str, out: Path | str = ".") -> pd.DataFrame:
    """Write a panel CSV (no index) and return it, so calls can be chained."""
    df.to_csv(panel_path(name, out), index=False)
    return df


def load(name: str, out: Path | str = ".") -> pd.DataFrame:
    """Read a panel CSV by name."""
    return pd.read_csv(panel_path(name, out))
