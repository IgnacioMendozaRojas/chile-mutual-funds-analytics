"""Read raw CMF files into typed tables."""

from __future__ import annotations

import gzip
import io
import re
from pathlib import Path

import pandas as pd

from .schema import ASSET_CLASS, COLUMNS, NUMERIC

ENCODING = "latin-1"


def _number(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.str.strip().str.replace(",", ".", regex=False), errors="coerce")


def read_file(path: str | Path, code: str | None = None) -> pd.DataFrame:
    path = Path(path)
    m = re.search(r"([A-Z]{4})_(\d{4})(\d{2})", path.name)
    if not m:
        raise ValueError(f"unexpected file name {path.name}; expected CODE_YYYYMM.txt.gz")
    code = code or m.group(1)
    raw = path.read_bytes()
    text = (gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw).decode(ENCODING)
    first = text.split("\n", 1)[0]
    sep = next((s for s in ("|", ";", "\t") if s in first), ",")
    df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str, on_bad_lines="skip")
    df = df.rename(columns=COLUMNS[code])
    df = df[[c for c in COLUMNS[code].values() if c in df.columns]].copy()
    for col in NUMERIC & set(df.columns):
        df[col] = _number(df[col])
    df["period"] = pd.Period(f"{m.group(2)}-{m.group(3)}", "M")
    return enrich(df, code)


def enrich(df: pd.DataFrame, code: str) -> pd.DataFrame:
    df["market_value_bn"] = df["market_value"] / 1e6  # thousands of CLP -> CLP billion
    if "maturity_date" in df:
        mat = pd.to_datetime(df["maturity_date"].str.slice(0, 10), format="%d/%m/%Y", errors="coerce")
        end = df["period"].dt.to_timestamp(how="end")
        df["years_to_maturity"] = ((mat - end).dt.days / 365.25).where(lambda x: (x > -1) & (x < 100))
    if code == "NACI":
        df["asset_class"] = df["instrument_type"].map(ASSET_CLASS).fillna("Other")
        df["rating"] = df["rating"].str.strip().str.rstrip("+-")
    if code == "FUTU":
        for col in ("underlying", "derivative_type", "position", "strike_currency"):
            df[col] = df[col].str.strip().str.upper()
    return df


def read_portfolio(raw_dir: str | Path, code: str) -> pd.DataFrame:
    files = sorted(Path(raw_dir).glob(f"{code}_*.txt.gz"))
    if not files:
        return pd.DataFrame()
    return pd.concat([read_file(p, code) for p in files], ignore_index=True)
