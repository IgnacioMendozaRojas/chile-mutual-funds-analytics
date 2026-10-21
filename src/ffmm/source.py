"""One month of holdings from the CMF, through cmf-ffmm-etl, ready for analysis.

cmf-ffmm-etl downloads each file, runs its quality checks and returns typed columns.
This module adds what the analysis needs on top: amounts in CLP billion, remaining
maturity, asset class, and normalised codes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
from cmf_etl import read_period

from .schema import ASSET_CLASS

CODES = ("NACI", "EXTR", "FUTU")


@dataclass
class Month:
    period: pd.Period
    tables: dict[str, pd.DataFrame]
    rows: dict[str, int] = field(default_factory=dict)
    warnings: dict[str, list[str]] = field(default_factory=dict)

    def __getitem__(self, code: str) -> pd.DataFrame:
        return self.tables[code]


def enrich(df: pd.DataFrame, code: str, period: pd.Period) -> pd.DataFrame:
    """Analysis columns on top of the typed table returned by cmf-ffmm-etl."""
    df = df.copy()
    df["period"] = period
    df["fund_run"] = pd.to_numeric(df["fund_run"], errors="coerce").astype("Int64").astype(str)
    df["market_value_bn"] = df["market_value"] / 1e6  # thousands of CLP -> CLP billion
    if "maturity_date" in df:
        mat = pd.to_datetime(df["maturity_date"], errors="coerce")
        years = (mat - period.to_timestamp(how="end")).dt.days / 365.25
        df["years_to_maturity"] = years.where((years > -1) & (years < 100))
    for col in ("instrument_type", "currency", "ticker", "issuer_rut"):
        if col in df:
            df[col] = df[col].astype("string").str.strip()
    if code == "NACI":
        df["asset_class"] = df["instrument_type"].map(ASSET_CLASS).fillna("Other")
        df["risk_rating"] = df["risk_rating"].astype("string").str.strip().str.rstrip("+-")
    if code == "FUTU":
        for col in ("underlying_currency", "derivative_type", "position", "strike_currency"):
            df[col] = df[col].astype("string").str.strip().str.upper()
    return df


def load_month(year: int, month: int, client=None, codes: tuple[str, ...] = CODES) -> Month:
    """Read the month's portfolios. Raises cmf_etl.NoDataError if it is not published yet
    and cmf_etl.BlockedError if a file fails a blocking quality check."""
    period = pd.Period(f"{year}-{month:02d}", "M")
    out = Month(period, {})
    for code in codes:
        read = read_period(code, year, month, client=client)
        out.tables[code] = enrich(read.data, code, period)
        out.rows[code] = len(read.data)
        out.warnings[code] = read.warnings
    return out
