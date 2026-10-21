"""Tables in data/processed -> figures, latest.json and the "Latest reading" block of the README."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path

import pandas as pd

from . import figures as fg
from . import store

GROUPS = {
    "Bank deposits": "Banks (deposits and bonds)",
    "Bank bonds": "Banks (deposits and bonds)",
    "Central Bank": "Central Bank and Treasury",
    "Treasury": "Central Bank and Treasury",
    "Corporate bonds": "Corporate bonds and paper",
    "Commercial paper": "Corporate bonds and paper",
    "Chilean equities": "Chilean equities and funds",
    "Investment fund units": "Chilean equities and funds",
    "Foreign investments": "Foreign investments",
}
BANK_CLASSES = {"Bank deposits", "Bank bonds"}
REPO = "chile-mutual-funds-analytics"


def _wide(df: pd.DataFrame, col: str) -> pd.DataFrame:
    return df.pivot_table(index="period", columns=col, values="clp_bn", aggfunc="sum", fill_value=0.0).sort_index()


def series(t: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Headline monthly series, one row per month."""
    comp = _wide(t["composition"], "asset_class")
    banks = _wide(t["banks"], "bank")
    risk = t["risk"].set_index("period").sort_index()
    top6 = banks.apply(lambda r: r.nlargest(6).sum(), axis=1)
    out = pd.DataFrame(
        {
            "holdings_tn": comp.sum(axis=1) / 1000,
            "bank_funding_tn": banks.sum(axis=1) / 1000,
            "central_bank_treasury_tn": comp.reindex(columns=["Central Bank", "Treasury"], fill_value=0).sum(axis=1)
            / 1000,
            "top6_bank_share": top6 / banks.sum(axis=1),
            "share_maturing_1y": risk["share_maturing_1y"],
            "avg_years_to_maturity": risk["avg_years_to_maturity"],
            "issuer_hhi": risk["issuer_hhi"],
        }
    )
    out["bank_share_of_holdings"] = out["bank_funding_tn"] / out["holdings_tn"]
    fx = t["fx_hedge"].set_index("period").sort_index()
    out["fx_hedge_ratio"] = fx["hedge_ratio"]
    return out


METRICS = [
    # id, label, unit, kind of change
    ("bank_funding_tn", "Bank deposits and bonds held by funds", "CLP tn", "pct"),
    ("bank_share_of_holdings", "Share of fund holdings lent to banks", "share", "pp"),
    ("top6_bank_share", "Share taken by the six largest banks", "share", "pp"),
    ("share_maturing_1y", "Domestic fixed income maturing within a year", "share", "pp"),
    ("avg_years_to_maturity", "Average remaining maturity, domestic fixed income", "years", "abs"),
    ("holdings_tn", "Total holdings (fund-of-fund units excluded)", "CLP tn", "pct"),
    ("fx_hedge_ratio", "Foreign-currency assets hedged with US$ forwards", "share", "pp"),
]


def latest(s: pd.DataFrame, updated: dt.date | None = None) -> dict:
    metrics = []
    for mid, label, unit, kind in METRICS:
        col = s[mid].dropna()
        if col.empty:
            continue
        value, period = float(col.iloc[-1]), col.index[-1]
        prev = float(col.iloc[-2]) if len(col) > 1 else None
        change = None
        if prev is not None:
            change = value / prev - 1 if kind == "pct" else value - prev
        metrics.append(
            {
                "id": mid,
                "label": label,
                "value": round(value, 4),
                "unit": unit,
                "period": period,
                "previous": None if prev is None else round(prev, 4),
                "change": None if change is None else round(change, 4),
                "change_type": {"pct": "relative", "pp": "points", "abs": "absolute"}[kind],
            }
        )
    m = {x["id"]: x for x in metrics}
    as_of = s.index[-1]
    return {
        "schema": 1,
        "id": "mutual-funds-bank-funding",
        "repo": REPO,
        "title": "Mutual funds as a source of bank funding",
        "question": "How much short-term funding do Chilean banks get from mutual funds, and how concentrated is it?",
        "as_of": as_of,
        "frequency": "monthly",
        "updated": str(updated or dt.date.today()),
        "source": "CMF mutual fund portfolio files (NACI, EXTR, FUTU)",
        "headline": (
            f"Mutual funds held CLP {m['bank_funding_tn']['value']:.1f} trillion of bank deposits and bonds in "
            f"{_month_name(as_of)}, {m['bank_share_of_holdings']['value']:.0%} of everything they own; "
            f"the six largest banks take {m['top6_bank_share']['value']:.0%}."
        ),
        "metrics": metrics,
        "figure": "docs/figures/banks-light.png",
    }


def _month_name(period: str) -> str:
    return pd.Period(period, "M").strftime("%B %Y")


def _fmt(value: float | None, unit: str) -> str:
    if value is None:
        return "–"
    if unit == "share":
        return f"{value:.1%}"
    if unit == "years":
        return f"{value:.2f} years"
    return f"CLP {value:,.1f} tn"


def _fmt_change(x: dict) -> str:
    c = x["change"]
    if c is None:
        return "–"
    if x["change_type"] == "relative":
        return f"{c:+.1%}"
    if x["change_type"] == "points":
        return f"{c * 100:+.1f} pp"
    return f"{c:+.2f}"


def readme_block(data: dict) -> str:
    rows = []
    for x in data["metrics"]:
        note = f"latest is {_month_name(x['period'])}" if x["period"] != data["as_of"] else ""
        cells = [x["label"], _fmt(x["value"], x["unit"]), _fmt(x["previous"], x["unit"]), _fmt_change(x), note]
        rows.append("| " + " | ".join(cells) + " |")
    units = "CLP tn = CLP trillion (10^12)."
    return "\n".join(
        [
            f"**Latest reading: {_month_name(data['as_of'])}.** {data['headline']}",
            "",
            "| Indicator | Latest | Month before | Change | Note |",
            "|---|---:|---:|---:|---|",
            *rows,
            "",
            f"*Updated automatically on {data['updated']} from the CMF files. {units} "
            "A note gives the month when an indicator lags the others.*",
        ]
    )


def write_readme(readme: Path, block: str) -> None:
    text = readme.read_text(encoding="utf-8")
    new = re.sub(
        r"(<!-- latest:start -->\n)(?:.*?\n)?(<!-- latest:end -->)",
        lambda m: m.group(1) + block + "\n" + m.group(2),
        text,
        flags=re.S,
    )
    readme.write_text(new, encoding="utf-8")


def figures(t: dict[str, pd.DataFrame], figs: Path) -> None:
    comp = _wide(t["composition"], "asset_class")
    grouped = comp.T.groupby(lambda c: GROUPS.get(c, "Other")).sum().T
    grouped = grouped[[g for g in dict.fromkeys(GROUPS.values()) if g in grouped]] / 1000
    first, last = comp.index[0], comp.index[-1]
    fg.stacked(
        grouped,
        figs,
        "composition",
        "Where Chilean mutual funds invest",
        f"Holdings at market value, CLP trillion, {first} to {last}; fund-of-fund units excluded",
        "CLP trillion",
    )
    banks = _wide(t["banks"], "bank")
    fg.bars(
        banks.loc[last].nlargest(8),
        figs,
        "banks",
        "Bank deposits and bonds held by mutual funds",
        f"By issuing bank, {last}, CLP billion",
        "CLP billion",
    )
    risk = t["risk"].set_index("period").sort_index()
    fg.lines(
        risk[["avg_years_to_maturity"]],
        figs,
        "maturity",
        "Average remaining maturity of domestic fixed income",
        "Market-value weighted, years",
        "years",
    )
    fx = t["fx_hedge"].set_index("period").sort_index().dropna(subset=["fx_assets_bn"])
    fg.lines(
        fx[["fx_assets_bn", "usd_sold_forward_bn"]].rename(
            columns={"fx_assets_bn": "Foreign-currency assets", "usd_sold_forward_bn": "US$ sold forward (net)"}
        )
        / 1000,
        figs,
        "fx-hedge",
        "Foreign-currency assets vs US$ sold forward",
        f"All funds, CLP trillion, {fx.index[0]} to {fx.index[-1]}",
        "CLP trillion",
    )
    eq = _wide(t["equities"], "ticker")
    fg.bars(
        eq.loc[last].nlargest(10),
        figs,
        "equities",
        "Largest Chilean stocks held by mutual funds",
        f"{last}, CLP billion",
        "CLP billion",
    )


def build(out: Path = Path("data/processed"), figs: Path = Path("docs/figures"), readme: Path | None = None) -> dict:
    t = store.read_all(out)
    s = series(t)
    s.round(4).to_csv(Path(out) / "headline_series.csv")
    data = latest(s)
    (Path(out) / "latest.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    figures(t, figs)
    if readme is not None and readme.exists():
        write_readme(readme, readme_block(data))
    return data


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ffmm build")
    p.add_argument("--out", default="data/processed", type=Path)
    p.add_argument("--figs", default="docs/figures", type=Path)
    p.add_argument("--readme", default="README.md", type=Path)
    a = p.parse_args(argv)
    data = build(a.out, a.figs, a.readme)
    print(f"built: latest {data['as_of']}")
    return 0
