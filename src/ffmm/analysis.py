"""Industry-level questions answered from the monthly holdings.

All amounts in CLP billion (miles de millones) at market value. Holdings of other
mutual funds' units ("Mutual fund units") are left out of industry totals, since
the underlying assets are already counted in the fund that issued the units.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .schema import BANK_CODES, DOUBLE_COUNTED, FIXED_INCOME, RATING_BUCKET

USD_CODES = {"PROM", "DOLAR", "USD", "DO", "US$"}


def _pivot(df: pd.DataFrame, col: str) -> pd.DataFrame:
    return df.pivot_table(index="period", columns=col, values="market_value_bn", aggfunc="sum", fill_value=0.0)


def composition(naci: pd.DataFrame, extr: pd.DataFrame) -> pd.DataFrame:
    """Holdings by asset class, plus foreign investments, per month."""
    dom = _pivot(naci[~naci["asset_class"].isin(DOUBLE_COUNTED)], "asset_class")
    dom["Foreign investments"] = extr.groupby("period")["market_value_bn"].sum()
    dom = dom.fillna(0.0)
    order = dom.iloc[-1].sort_values(ascending=False).index
    out = dom[order]
    out["Total"] = out.sum(axis=1)
    return out


def bank_labels(naci: pd.DataFrame) -> pd.Series:
    """Issuer RUT -> bank name, read from the code inside its deposit tickers (FNSTD-..., F*CHI...)."""
    dep = naci[naci["ticker"].str.match(r"^F[N*][A-Z]{3}", na=False)]
    codes = dep["ticker"].str.slice(2, 5)
    code = codes.groupby(dep["issuer_rut"]).agg(lambda s: s.value_counts().index[0])
    return code.map(lambda c: BANK_CODES.get(c, c))


def bank_funding(naci: pd.DataFrame, top: int = 8) -> tuple[pd.DataFrame, pd.Series]:
    """Deposits and bank bonds held by funds, by bank; and the issuer HHI of fixed income."""
    banks = naci[naci["asset_class"].isin({"Bank deposits", "Bank bonds"})].copy()
    labels = bank_labels(naci)
    banks["bank"] = banks["issuer_rut"].map(labels).fillna("RUT " + banks["issuer_rut"].astype(str))
    table = _pivot(banks, "bank")
    keep = table.iloc[-1].sort_values(ascending=False).index[:top]
    table = pd.concat([table[keep], table.drop(columns=keep).sum(axis=1).rename("Other banks")], axis=1)

    fi = naci[naci["asset_class"].isin(FIXED_INCOME)]
    shares = fi.groupby(["period", "issuer_rut"])["market_value_bn"].sum()
    shares = shares / shares.groupby(level=0).transform("sum")
    hhi = (shares**2).groupby(level=0).sum() * 10_000
    return table, hhi.rename("issuer_hhi")


def risk_profile(naci: pd.DataFrame) -> pd.DataFrame:
    """Currency, rating and maturity profile of domestic fixed income, per month."""
    fi = naci[naci["asset_class"].isin(FIXED_INCOME)].copy()
    fi["ccy"] = fi["currency"].map({"$$": "CLP", "UF": "UF", "PROM": "USD", "EUR": "EUR"}).fillna("Other")
    ccy = _pivot(fi, "ccy")
    ccy = ccy.div(ccy.sum(axis=1), axis=0).add_prefix("currency_")
    fi["rating_bucket"] = fi["rating"].map(RATING_BUCKET).fillna("Not rated / other")
    fi.loc[fi["asset_class"].isin({"Central Bank", "Treasury"}), "rating_bucket"] = "Sovereign"
    rat = _pivot(fi, "rating_bucket")
    rat = rat.div(rat.sum(axis=1), axis=0).add_prefix("rating_")
    ok = fi.dropna(subset=["years_to_maturity"])
    w = ok["market_value_bn"]
    wam = (ok["years_to_maturity"] * w).groupby(ok["period"]).sum() / w.groupby(ok["period"]).sum()
    short = (w * (ok["years_to_maturity"] <= 1)).groupby(ok["period"]).sum() / w.groupby(ok["period"]).sum()
    return pd.concat([wam.rename("avg_years_to_maturity"), short.rename("share_maturing_1y"), ccy, rat], axis=1)


def clean_usd_forwards(futu: pd.DataFrame) -> pd.DataFrame:
    """USD forwards with the committed amount checked against notional x strike.

    The committed amount should equal notional (US$) x strike (CLP per US$), in
    thousands of CLP. Some filers report it in CLP units (1,000x too large); those
    rows are rescaled. Rows whose implied rate is nowhere near the strike (for example
    a notional reported in pesos) cannot be repaired and are dropped. The `status`
    column records which case each row fell into.
    """
    fwd = futu[futu["underlying"].isin(USD_CODES) & futu["derivative_type"].str.contains("FORWARD", na=False)].copy()
    implied = fwd["committed_amount"] * 1000 / fwd["notional"]
    ratio = implied / fwd["strike"]
    ok = ratio.between(0.8, 1.25)
    units = (ratio / 1000).between(0.8, 1.25)
    fwd["status"] = np.select([ok, units], ["ok", "rescaled from CLP units"], "dropped: inconsistent")
    fwd["committed_clp_th"] = np.where(ok, fwd["committed_amount"], fwd["committed_amount"] / 1000)
    return fwd[fwd["status"] != "dropped: inconsistent"]


def fx_hedge(naci: pd.DataFrame, extr: pd.DataFrame, futu: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Foreign-currency assets vs net USD sold forward, industry and by fund.

    Assets: all foreign investments plus domestic holdings in foreign currency.
    Hedge: forwards on the US dollar, sells (V) minus buys (C), at committed amount
    (notional x strike, in CLP). Interest-rate and UF swaps are excluded.
    """
    # domestic holdings denominated in a foreign currency (CA and CU denote share and unit counts, not currencies)
    fx_dom = naci[naci["currency"].isin(["PROM", "EUR"])]
    assets = pd.concat(
        [extr[["period", "fund_run", "market_value_bn"]], fx_dom[["period", "fund_run", "market_value_bn"]]]
    )
    fwd = clean_usd_forwards(futu)
    fwd["net_sold_bn"] = np.where(fwd["position"] == "V", 1, -1) * fwd["committed_clp_th"] / 1e6
    periods = sorted(set(fwd["period"]))

    a = assets[assets["period"].isin(periods)].groupby(["period", "fund_run"])["market_value_bn"].sum()
    h = fwd.groupby(["period", "fund_run"])["net_sold_bn"].sum()
    by_fund = pd.concat([a.rename("fx_assets_bn"), h.rename("usd_sold_forward_bn")], axis=1).fillna(0.0)
    by_fund["hedge_ratio"] = by_fund["usd_sold_forward_bn"] / by_fund["fx_assets_bn"].where(by_fund["fx_assets_bn"] > 0)

    industry = by_fund.groupby(level=0)[["fx_assets_bn", "usd_sold_forward_bn"]].sum()
    industry["hedge_ratio"] = industry["usd_sold_forward_bn"] / industry["fx_assets_bn"]
    material = by_fund[by_fund["fx_assets_bn"] >= 1.0]  # funds with at least CLP 1bn abroad
    industry["funds_with_fx_assets"] = material.groupby(level=0).size()
    industry["share_of_those_hedging_half_or_more"] = (material["hedge_ratio"] >= 0.5).groupby(level=0).mean()
    return industry, by_fund


def equities(naci: pd.DataFrame, top: int = 10) -> pd.DataFrame:
    acc = naci[naci["asset_class"] == "Chilean equities"]
    table = _pivot(acc, "ticker")
    keep = table.iloc[-1].sort_values(ascending=False).index[:top]
    out = pd.concat([table[keep], table.drop(columns=keep).sum(axis=1).rename("Other stocks")], axis=1)
    return out


def fund_count(naci: pd.DataFrame, extr: pd.DataFrame) -> pd.Series:
    return (
        pd.concat([naci[["period", "fund_run"]], extr[["period", "fund_run"]]]).groupby("period")["fund_run"].nunique()
    )
