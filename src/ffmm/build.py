"""Raw CMF files -> aggregated tables in data/processed and figures in docs/figures."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import analysis as an
from . import figures as fg
from .read import read_portfolio

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


def _save(df: pd.DataFrame | pd.Series, path: Path, digits: int = 3) -> None:
    out = df.copy()
    out.index = out.index.astype(str)
    out.round(digits).to_csv(path)


def build(raw_dir: str | Path, processed: str | Path = "data/processed", figs: str | Path = "docs/figures") -> dict:
    processed, figs = Path(processed), Path(figs)
    processed.mkdir(parents=True, exist_ok=True)
    naci = read_portfolio(raw_dir, "NACI")
    extr = read_portfolio(raw_dir, "EXTR")
    futu = read_portfolio(raw_dir, "FUTU")
    results = {}

    comp = an.composition(naci, extr)
    _save(comp, processed / "composition_clp_bn.csv", 1)
    grouped = comp.drop(columns="Total").T.groupby(lambda c: GROUPS.get(c, "Other")).sum().T
    grouped = grouped[[g for g in dict.fromkeys(GROUPS.values()) if g in grouped]] / 1000
    fg.stacked(
        grouped,
        figs,
        "composition",
        "Where Chilean mutual funds invest",
        "Holdings at market value, CLP trillion; fund-of-fund units excluded",
        "CLP trillion",
    )
    results["composition"] = comp

    banks, hhi = an.bank_funding(naci)
    _save(banks, processed / "bank_funding_clp_bn.csv", 1)
    _save(hhi, processed / "issuer_hhi.csv", 0)
    last = banks.index[-1]
    fg.bars(
        banks.loc[last].drop("Other banks"),
        figs,
        "banks",
        "Bank deposits and bonds held by mutual funds",
        f"By issuing bank, {last}, CLP billion",
        "CLP billion",
    )
    results["banks"], results["hhi"] = banks, hhi

    risk = an.risk_profile(naci)
    _save(risk, processed / "risk_profile.csv")
    fg.lines(
        risk[["avg_years_to_maturity"]],
        figs,
        "maturity",
        "Average remaining maturity of domestic fixed income",
        "Market-value weighted, years",
        "years",
    )
    results["risk"] = risk

    if not futu.empty:
        industry, by_fund = an.fx_hedge(naci, extr, futu)
        _save(industry, processed / "fx_hedge_industry.csv")
        latest = by_fund.loc[industry.index[-1]]
        _save(
            latest.sort_values("fx_assets_bn", ascending=False),
            processed / f"fx_hedge_by_fund_{industry.index[-1]}.csv",
        )
        fg.lines(
            industry[["fx_assets_bn", "usd_sold_forward_bn"]].rename(
                columns={"fx_assets_bn": "Foreign-currency assets", "usd_sold_forward_bn": "US$ sold forward (net)"}
            )
            / 1000,
            figs,
            "fx-hedge",
            "Foreign-currency assets vs US$ sold forward",
            f"All funds, CLP trillion, {industry.index[0]} to {industry.index[-1]}",
            "CLP trillion",
        )
        results["fx"] = industry

    eq = an.equities(naci)
    _save(eq, processed / "equities_clp_bn.csv", 1)
    fg.bars(
        eq.iloc[-1].drop("Other stocks"),
        figs,
        "equities",
        "Largest Chilean stocks held by mutual funds",
        f"{eq.index[-1]}, CLP billion",
        "CLP billion",
    )
    results["equities"] = eq

    funds = an.fund_count(naci, extr)
    _save(funds, processed / "fund_count.csv", 0)
    results["funds"] = funds
    return results
