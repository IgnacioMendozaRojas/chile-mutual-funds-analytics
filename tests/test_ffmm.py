"""Tests on a few real rows from the CMF files (fixtures/*_202208.txt.gz).

The FUTU fixture takes rows from the January 2022 file, including one with the
committed amount reported in CLP units instead of thousands, and is filed under
August 2022 so that it lines up with the other fixtures.
"""

import gzip
import json
from pathlib import Path

import pandas as pd
import pytest
from cmf_etl import NoDataError
from cmf_etl.extract import parse_portfolio_file

from ffmm import analysis as an
from ffmm import build, store
from ffmm.monthly import aggregate
from ffmm.source import load_month
from ffmm.update import gaps, months, update

FIX = Path(__file__).parent / "fixtures"


class FakeClient:
    """Serves the fixture files for any month up to `last`; later months are not published."""

    def __init__(self, last=(2022, 9)):
        self.last, self.calls = last, []

    def download(self, portfolio, year, month):
        self.calls.append((portfolio, year, month))
        if (year, month) > self.last:
            raise NoDataError("not published")
        return parse_portfolio_file(gzip.decompress((FIX / f"{portfolio}_202208.txt.gz").read_bytes()))


@pytest.fixture(scope="module")
def month():
    return load_month(2022, 8, client=FakeClient())


def test_read_types_and_units(month):
    n = month["NACI"]
    assert set(n["period"].astype(str)) == {"2022-08"}
    dep = n[n["instrument_type"] == "DPC"].iloc[0]
    assert dep["market_value_bn"] == pytest.approx(0.992088)  # 992,088 thousand CLP
    assert dep["asset_class"] == "Bank deposits"
    assert dep["years_to_maturity"] == pytest.approx(30 / 365.25, abs=0.01)
    assert n.loc[n["instrument_type"] == "ACC", "years_to_maturity"].isna().all()
    assert month.rows == {"NACI": 7, "EXTR": 3, "FUTU": 4}


def test_composition_excludes_fund_of_fund_units(month):
    comp = an.composition(month["NACI"], month["EXTR"])
    assert "Mutual fund units" not in comp.columns
    naci = month["NACI"]
    expected = (
        naci.loc[naci["instrument_type"] != "CFM", "market_value_bn"].sum() + month["EXTR"]["market_value_bn"].sum()
    )
    assert comp["Total"].iloc[0] == pytest.approx(expected)


def test_bank_labels_from_deposit_tickers(month):
    assert an.bank_labels(month["NACI"])["97006000"] == "BCI"


def test_risk_profile_sovereign_bucket(month):
    r = an.risk_profile(month["NACI"]).iloc[0]
    assert r["rating_Sovereign"] > 0  # Central Bank and Treasury paper is not rated
    assert r.filter(like="currency_").sum() == pytest.approx(1.0)


def test_usd_forwards_are_cleaned_and_rates_excluded(month):
    fwd = an.clean_usd_forwards(month["FUTU"])
    assert len(fwd) == 3  # the UF swap is not an FX hedge
    rescaled = fwd[fwd["status"] == "rescaled from CLP units"]
    assert len(rescaled) == 1
    assert rescaled["committed_clp_th"].iloc[0] == pytest.approx(1_515_068.247)


def test_fx_hedge_ratio(month):
    _, by_fund = an.fx_hedge(month["NACI"], month["EXTR"], month["FUTU"])
    bice = by_fund.loc[(pd.Period("2022-08", "M"), "8032")]
    assets = month["EXTR"]["market_value_bn"].sum()
    assert bice["fx_assets_bn"] == pytest.approx(assets)
    assert bice["usd_sold_forward_bn"] == pytest.approx((1_631_800 + 815_900) / 1e6)
    assert bice["hedge_ratio"] == pytest.approx(bice["usd_sold_forward_bn"] / assets)


def test_month_aggregates_and_replace_is_idempotent(month, tmp_path):
    rows = aggregate(month)
    assert rows["fx_hedge"]["forwards_rescaled"].iloc[0] == 1
    store.replace_month(tmp_path, rows)
    store.replace_month(tmp_path, rows)  # same month again: replaced, not duplicated
    t = store.read_all(tmp_path)
    assert len(t["funds"]) == 1
    total = t["composition"]["clp_bn"].sum()
    assert total == pytest.approx(an.composition(month["NACI"], month["EXTR"])["Total"].iloc[0], rel=1e-4)


def test_update_adds_only_new_months_and_stops_at_unpublished(tmp_path):
    client = FakeClient(last=(2022, 9))
    r = update(tmp_path, start=(2022, 8), end=(2022, 10), client=client)
    assert r["added"] == ["2022-08", "2022-09"] and r["not_published"] == ["2022-10"]
    client.calls.clear()
    r = update(tmp_path, start=(2022, 8), end=(2022, 9), client=client)
    assert r["added"] == [] and client.calls == []  # nothing downloaded twice
    assert gaps(tmp_path, start=(2022, 8)) == []
    assert list(months((2025, 11), (2026, 2))) == [(2025, 11), (2025, 12), (2026, 1), (2026, 2)]


def test_build_writes_latest_json_and_readme_block(tmp_path):
    update(tmp_path, start=(2022, 8), end=(2022, 9), client=FakeClient())
    readme = tmp_path / "README.md"
    readme.write_text("intro\n<!-- latest:start -->\nold\n<!-- latest:end -->\nrest\n")
    data = build.build(tmp_path, tmp_path / "figs", readme)
    saved = json.loads((tmp_path / "latest.json").read_text())
    assert saved["as_of"] == "2022-09" and saved["schema"] == 1
    ids = {m["id"] for m in saved["metrics"]}
    assert {"bank_funding_tn", "top6_bank_share", "fx_hedge_ratio"} <= ids
    funding = next(m for m in data["metrics"] if m["id"] == "bank_funding_tn")
    assert funding["change"] == pytest.approx(0.0)  # same fixture both months
    text = readme.read_text()
    assert "Latest reading: September 2022" in text and "\nold\n" not in text and text.endswith("rest\n")
    assert (tmp_path / "figs" / "banks-light.png").exists()
    readme.write_text("<!-- latest:start -->\n<!-- latest:end -->\n")  # empty block, as in a fresh README
    build.build(tmp_path, tmp_path / "figs", readme)
    assert "Latest reading" in readme.read_text()
