"""Aggregate one month of holdings into the rows of each published table.

Every table in data/processed is built month by month, so a monthly update only
needs that month's files. Tables are long (one row per period and category); the
choice of what to show, such as the top banks, is made when figures are drawn.
"""

from __future__ import annotations

import pandas as pd

from . import analysis as an
from .source import Month

# Tables in data/processed, with the columns that identify a row.
TABLES = {
    "composition": ["period", "asset_class"],
    "banks": ["period", "bank"],
    "risk": ["period"],
    "fx_hedge": ["period"],
    "fx_hedge_by_fund": ["period", "fund_run"],
    "equities": ["period", "ticker"],
    "funds": ["period"],
    "bank_funding_by_type": ["period", "issuer_rut", "asset_class"],
}


def _long(wide: pd.DataFrame, name: str) -> pd.DataFrame:
    out = wide.rename_axis(columns=name).stack().rename("clp_bn").reset_index()
    out["period"] = out["period"].astype(str)
    return out[out["clp_bn"] != 0]


def bank_funding_by_type(naci: pd.DataFrame, period: str) -> pd.DataFrame:
    """Deposits and bonds held by funds, by issuing bank (RUT and label), for linking to bank balance sheets."""
    b = naci[naci["asset_class"].isin({"Bank deposits", "Bank bonds"})]
    labels = an.bank_labels(naci)
    out = b.groupby(["issuer_rut", "asset_class"], as_index=False)["market_value_bn"].sum()
    out.insert(0, "period", period)
    out["bank"] = out["issuer_rut"].map(labels).fillna("")
    return out.rename(columns={"market_value_bn": "clp_bn"})[["period", "issuer_rut", "bank", "asset_class", "clp_bn"]]


def aggregate(month: Month) -> dict[str, pd.DataFrame]:
    naci, extr, futu = month["NACI"], month["EXTR"], month["FUTU"]
    p = str(month.period)

    comp = an.composition(naci, extr).drop(columns="Total")
    banks, hhi = an.bank_funding(naci, top=10_000)  # every bank; the figure picks the top ones
    risk = an.risk_profile(naci)
    risk["issuer_hhi"] = hhi
    risk.index = risk.index.astype(str)

    fwd = an.clean_usd_forwards(futu, keep_dropped=True)
    status = fwd["status"].value_counts()
    industry, by_fund = an.fx_hedge(naci, extr, futu)
    if industry.empty:  # no USD forwards this month
        industry = pd.DataFrame([{"fx_assets_bn": float("nan")}], index=pd.Index([month.period], name="period"))
    industry = industry.assign(
        forwards_used=int(status.get("ok", 0) + status.get("rescaled from CLP units", 0)),
        forwards_rescaled=int(status.get("rescaled from CLP units", 0)),
        forwards_dropped=int(status.get("dropped: inconsistent", 0)),
    )
    industry.index = industry.index.astype(str)
    by_fund = by_fund.reset_index()
    by_fund["period"] = by_fund["period"].astype(str)

    funds = pd.DataFrame(
        {
            "period": [p],
            "funds": [an.fund_count(naci, extr).iloc[0]],
            **{f"rows_{c.lower()}": [n] for c, n in month.rows.items()},
            "quality_warnings": [sum(len(w) for w in month.warnings.values())],
        }
    )
    return {
        "composition": _long(comp, "asset_class"),
        "banks": _long(banks, "bank"),
        "bank_funding_by_type": bank_funding_by_type(naci, p),
        "risk": risk.rename_axis("period").reset_index(),
        "fx_hedge": industry.rename_axis("period").reset_index(),
        "fx_hedge_by_fund": by_fund,
        "equities": _long(an.equities(naci, top=10_000).drop(columns="Other stocks"), "ticker"),
        "funds": funds,
    }
