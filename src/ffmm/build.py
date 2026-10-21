"""Tables in data/processed -> figures, latest.json and the "Latest reading" block of the README."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path

import pandas as pd

from . import store
from .figstyle import charts

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


def outflows(t: dict[str, pd.DataFrame], horizons=(1, 3, 12)) -> pd.DataFrame:
    """Worst observed change in bank funding from funds over 1, 3 and 12 months: a run-off calibration."""
    comp = _wide(t["composition"], "asset_class").reindex(columns=sorted(BANK_CLASSES), fill_value=0.0)
    rows = []
    for name, x in [("Bank deposits", comp["Bank deposits"]), ("Bank deposits and bonds", comp.sum(axis=1))]:
        for k in horizons:
            change = (x / x.shift(k) - 1).dropna()
            if change.empty:  # history shorter than the horizon
                continue
            rows.append(
                {"funding": name, "months": k, "worst_change": round(change.min(), 4), "ending": change.idxmin()}
            )
    return pd.DataFrame(rows)


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


def _x(index) -> list:
    return [pd.Timestamp(str(p)) for p in index]


def _month(p: str) -> str:
    return pd.Period(p, "M").strftime("%b %Y")


def figures(t: dict[str, pd.DataFrame], figs: Path) -> None:
    comp = _wide(t["composition"], "asset_class")
    first, last = comp.index[0], comp.index[-1]
    repo = "github.com/IgnacioMendozaRojas/chile-mutual-funds-analytics"
    source = (
        f"Source: CMF mutual fund portfolio files, {_month(first)} to {_month(last)}; market values, fund-of-fund "
        f"units excluded. {repo}"
    )
    x = _x(comp.index)

    # 1. Hero: concentration of the funding banks get from mutual funds
    banks = _wide(t["banks"], "bank")
    latest = banks.loc[last].sort_values(ascending=False)
    top6 = latest.head(6)
    shown = pd.concat([latest.head(8), pd.Series({"Other banks": latest.iloc[8:].sum()})])
    for c in charts(
        f"Six banks take {top6.sum() / latest.sum():.0%} of the CLP {latest.sum() / 1000:.1f} trillion "
        "mutual funds lend to banks",
        f"Bank deposits and bonds held by Chilean mutual funds, by issuing bank, {_month(last)}, CLP billion",
        source,
        size=(9, 4.6),
    ):
        c.hbars(list(shown.index), list(shown.values), highlight=set(top6.index), sort=False)
        c.fig.subplots_adjust(left=0.19, right=0.92, top=0.8, bottom=0.2)
        c.save(figs, "banks")

    # 2. The 2021-22 shift from banks to the Central Bank
    bank_tn = comp.reindex(columns=["Bank deposits"], fill_value=0).sum(axis=1) / 1000
    cb_tn = comp.reindex(columns=["Central Bank", "Treasury"], fill_value=0).sum(axis=1) / 1000
    # the 2020-22 episode; on a short history (tests) fall back to the whole series
    before, after = bank_tn.loc["2020-01":"2020-12"], bank_tn.loc["2021-01":"2022-12"]
    hi = (before if len(before) else bank_tn).idxmax()
    lo = (after if len(after) else bank_tn).idxmin()
    for c in charts(
        f"Funds cut bank deposits from CLP {bank_tn[hi]:.1f} to {bank_tn[lo]:.1f} trillion in 2020-22",
        "Bank deposits vs Central Bank and Treasury paper held by Chilean mutual funds, CLP trillion",
        source,
    ):
        c.event(pd.Timestamp("2020-07"), "1st pension withdrawal")
        c.event(pd.Timestamp("2021-07"), "1st rate hike", y_frac=0.9)
        c.line(x, bank_tn.values, 0, "Bank deposits")
        c.line(x, cb_tn.values, 1, "Central Bank and Treasury")
        c.note((pd.Timestamp(lo), bank_tn[lo]), f"{bank_tn[lo]:.1f} trillion, {_month(lo)}", (30, -20))
        c.ax.set_ylim(bottom=0)
        c.yaxis("CLP trillion")
        c.legend("lower right")
        c.save(figs, "funding-shift")

    # 3. Composition
    grouped = comp.T.groupby(lambda col: GROUPS.get(col, "Other")).sum().T
    grouped = grouped[[g for g in dict.fromkeys(GROUPS.values()) if g in grouped]] / 1000
    total = grouped.sum(axis=1)
    for c in charts(
        f"Fund holdings grew from CLP {total.iloc[0]:.1f} to {total.iloc[-1]:.1f} trillion, "
        f"{grouped.iloc[-1].iloc[0] / total.iloc[-1]:.0%} of it lent to banks",
        "Holdings of Chilean mutual funds by asset class, market value, CLP trillion",
        source,
    ):
        c.stack(x, {k: grouped[k].values for k in grouped.columns})
        c.yaxis("CLP trillion")  # every band is labelled at its end, so no separate legend box
        c.fig.subplots_adjust(right=0.74)
        c.save(figs, "composition")

    # 4. Maturity: how short the money is
    risk = t["risk"].set_index("period").sort_index()
    short = risk["share_maturing_1y"]
    for c in charts(
        f"{short.iloc[-1]:.0%} of funds' domestic fixed income matures within a year",
        "Share of domestic fixed income (market value) with less than one year to maturity",
        source,
    ):
        c.line(_x(short.index), short.values, 0, "maturing within a year", end_label=False)
        k = short.idxmax()
        c.note((pd.Timestamp(k), short.max()), f"{short.max():.0%}, {_month(k)}", (25, -25))
        c.ax.set_ylim(0, 1)
        c.yaxis(pct=True)
        c.save(figs, "maturity")

    # 5. FX hedging
    fx = t["fx_hedge"].set_index("period").sort_index().dropna(subset=["fx_assets_bn"])
    xf = _x(fx.index)
    assets, sold = fx["fx_assets_bn"] / 1000, fx["usd_sold_forward_bn"] / 1000
    for c in charts(
        f"Only {fx['hedge_ratio'].iloc[-1]:.0%} of CLP {assets.iloc[-1]:.1f} trillion in foreign-currency "
        "assets is hedged",
        "Foreign-currency assets of Chilean mutual funds vs US dollars sold forward (net), CLP trillion",
        source.replace(repo, "Forwards with inconsistent amounts are excluded, so the hedge is a lower bound. " + repo),
    ):
        c.line(xf, assets.values, 0, "Foreign-currency assets")
        c.line(xf, sold.values, 1, "US$ sold forward")
        c.ax.set_ylim(bottom=0)
        c.yaxis("CLP trillion")
        c.legend("upper left")
        c.save(figs, "fx-hedge")

    # 6. Equities
    eq = _wide(t["equities"], "ticker").loc[last].nlargest(10)
    top = list(eq.index[:2])
    for c in charts(
        f"{' and '.join(top)} {'are' if len(top) > 1 else 'is'} the largest Chilean "
        f"{'stocks' if len(top) > 1 else 'stock'} held by mutual funds",
        f"Chilean equities held by mutual funds, ten largest positions, {_month(last)}, CLP billion",
        source,
        size=(9, 4.6),
    ):
        c.hbars(list(eq.index), list(eq.values), highlight=set(top))
        c.fig.subplots_adjust(left=0.16, right=0.92, top=0.8, bottom=0.2)
        c.save(figs, "equities")


def build(out: Path = Path("data/processed"), figs: Path = Path("docs/figures"), readme: Path | None = None) -> dict:
    t = store.read_all(out)
    s = series(t)
    s.round(4).to_csv(Path(out) / "headline_series.csv")
    outflows(t).to_csv(Path(out) / "outflows.csv", index=False)
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
