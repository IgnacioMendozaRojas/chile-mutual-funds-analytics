"""One-off: what would the hedge ratio have been if forwards filed 1,000x too large were not rescaled?"""

import numpy as np

from ffmm import analysis as an
from ffmm.source import load_month

for y, m in [(2020, 11), (2022, 1)]:
    mo = load_month(y, m)
    naci, extr, futu = mo["NACI"], mo["EXTR"], mo["FUTU"]
    industry, _ = an.fx_hedge(naci, extr, futu)
    fwd = an.clean_usd_forwards(futu)
    bad = fwd[fwd["status"] == "rescaled from CLP units"]
    sign = np.where(bad["position"] == "V", 1, -1)
    extra_bn = float((sign * (bad["committed_amount"] - bad["committed_clp_th"])).sum() / 1e6)
    row = industry.iloc[0]
    raw_ratio = (row["usd_sold_forward_bn"] + extra_bn) / row["fx_assets_bn"]
    print(
        f"::notice title=Forward units {y}-{m:02d}::rows rescaled {len(bad)}; "
        f"hedged {row['usd_sold_forward_bn']:.1f} bn of {row['fx_assets_bn']:.1f} bn = {row['hedge_ratio']:.1%}; "
        f"unrescaled it would be {row['usd_sold_forward_bn'] + extra_bn:.1f} bn = {raw_ratio:.1%}; "
        f"largest row {bad['committed_amount'].abs().max() / 1e6:.1f} bn as filed"
    )
