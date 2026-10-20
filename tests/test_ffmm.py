"""Tests on a few real rows from the CMF files (fixtures/*_202208.txt.gz).

The FUTU fixture takes rows from the January 2022 file, including one with the
committed amount reported in CLP units instead of thousands, and is filed under
August 2022 so that it lines up with the other fixtures.
"""

from pathlib import Path

import pandas as pd
import pytest

from ffmm import analysis as an
from ffmm.download import Downloader, form_portfolios, is_data, months
from ffmm.read import read_file, read_portfolio

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def data():
    return {c: read_portfolio(FIX, c) for c in ("NACI", "EXTR", "FUTU")}


def test_read_types_and_units(data):
    n = data["NACI"]
    assert set(n["period"].astype(str)) == {"2022-08"}
    dep = n[n["instrument_type"] == "DPC"].iloc[0]
    assert dep["market_value_bn"] == pytest.approx(0.992088)  # 992,088 thousand CLP
    assert dep["asset_class"] == "Bank deposits"
    assert dep["years_to_maturity"] == pytest.approx(30 / 365.25, abs=0.01)
    assert n.loc[n["instrument_type"] == "ACC", "years_to_maturity"].isna().all()


def test_composition_excludes_fund_of_fund_units(data):
    comp = an.composition(data["NACI"], data["EXTR"])
    assert "Mutual fund units" not in comp.columns
    naci = data["NACI"]
    expected = (
        naci.loc[naci["instrument_type"] != "CFM", "market_value_bn"].sum() + data["EXTR"]["market_value_bn"].sum()
    )
    assert comp["Total"].iloc[0] == pytest.approx(expected)


def test_bank_labels_from_deposit_tickers(data):
    labels = an.bank_labels(data["NACI"])
    assert labels["97006000"] == "BCI"


def test_risk_profile_sovereign_bucket(data):
    r = an.risk_profile(data["NACI"]).iloc[0]
    assert r["rating_Sovereign"] > 0  # Central Bank and Treasury paper is not rated
    assert r.filter(like="currency_").sum() == pytest.approx(1.0)


def test_usd_forwards_are_cleaned_and_rates_excluded(data):
    fwd = an.clean_usd_forwards(data["FUTU"])
    assert len(fwd) == 3  # the UF swap is not an FX hedge
    rescaled = fwd[fwd["status"] == "rescaled from CLP units"]
    assert len(rescaled) == 1
    assert rescaled["committed_clp_th"].iloc[0] == pytest.approx(1_515_068.247)


def test_fx_hedge_ratio(data):
    industry, by_fund = an.fx_hedge(data["NACI"], data["EXTR"], data["FUTU"])
    bice = by_fund.loc[(pd.Period("2022-08", "M"), "8032")]
    assets = data["EXTR"]["market_value_bn"].sum()
    assert bice["fx_assets_bn"] == pytest.approx(assets)
    assert bice["usd_sold_forward_bn"] == pytest.approx((1_631_800 + 815_900) / 1e6)
    assert bice["hedge_ratio"] == pytest.approx(bice["usd_sold_forward_bn"] / assets)


def test_months_and_form_parsing():
    assert list(months((2025, 11), (2026, 2))) == [(2025, 11), (2025, 12), (2026, 1), (2026, 2)]
    html = (
        '<select name="cartera"><option value="###">Seleccione Cartera</option>'
        '<option value="NACI">Cartera de Inversiones Nacionales</option>'
        '<option value="EXTR">Extranjeras</option></select>'
    )
    assert form_portfolios(html) == {"NACI": "Cartera de Inversiones Nacionales", "EXTR": "Extranjeras"}
    assert not is_data(b"<html><body>No hay datos</body></html>" * 3)


class FakeSession:
    def __init__(self, payload):
        self.payload, self.posts = payload, []

    def get(self, url, timeout=None):
        return None

    def post(self, url, data=None, timeout=None):
        self.posts.append(data)

        class R:
            content = self.payload

            def raise_for_status(self):
                pass

        return R()


def test_downloader_saves_and_resumes(tmp_path):
    payload = (FIX / "EXTR_202208.txt.gz").read_bytes()
    import gzip

    session = FakeSession(gzip.decompress(payload))
    d = Downloader(tmp_path, pause=0, session=session)
    assert d.run(["EXTR"], (2022, 8), (2022, 9)) == {"downloaded": 2, "skipped": 0, "empty": 0}
    assert d.run(["EXTR"], (2022, 8), (2022, 9))["skipped"] == 2  # second run touches nothing
    assert len(read_file(tmp_path / "EXTR_202209.txt.gz")) == 3
    assert session.posts[0] == {"mm": "08", "aa": "2022", "cartera": "EXTR"}
