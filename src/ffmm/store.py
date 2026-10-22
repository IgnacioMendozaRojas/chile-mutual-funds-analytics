"""The published tables in data/processed: read, replace a month, write."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .monthly import TABLES


def path(out: Path, name: str) -> Path:
    return Path(out) / f"{name}.csv"


def read(out: Path, name: str) -> pd.DataFrame:
    p = path(out, name)
    if not p.exists():
        return pd.DataFrame(columns=TABLES[name])
    return pd.read_csv(p, dtype={"period": str, "fund_run": str, "bank": str, "ticker": str, "issuer_rut": str})


def read_all(out: Path) -> dict[str, pd.DataFrame]:
    return {name: read(out, name) for name in TABLES}


def months_done(out: Path) -> set[str]:
    return set(read(out, "funds")["period"].astype(str))


def replace_month(out: Path, rows: dict[str, pd.DataFrame], keep_by_fund: int = 1) -> None:
    """Swap in one month's rows in every table (idempotent: re-running a month replaces it).

    The by-fund FX table is kept for the latest `keep_by_fund` months only; the
    industry series has the full history.
    """
    Path(out).mkdir(parents=True, exist_ok=True)
    period = rows["funds"]["period"].iloc[0]
    for name, keys in TABLES.items():
        old = read(out, name)
        new = pd.concat([old[old["period"] != period], rows[name]], ignore_index=True)
        if name == "fx_hedge_by_fund":
            new = new[new["period"].isin(sorted(new["period"].unique())[-keep_by_fund:])]
        new = new.sort_values(keys, kind="stable")
        decimals = 0 if name == "funds" else 4
        new.to_csv(path(out, name), index=False, float_format=f"%.{decimals}f" if decimals else "%.0f")
