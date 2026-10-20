"""CMF portfolio files: column codes, asset classes and labels.

The CMF publishes every Chilean mutual fund's holdings each month in five files
(form "Cartera de Fondos Mutuos"): NACI domestic investments, EXTR foreign
investments, FUTU forwards, futures and swaps, OPCI options, OPLA options written.
Columns carry the codes of CMF Circular 1333. Market values are in thousands of CLP.
"""

from __future__ import annotations

PORTFOLIOS = {
    "NACI": "Domestic investments",
    "EXTR": "Foreign investments",
    "FUTU": "Forwards, futures and swaps",
    "OPCI": "Options held",
    "OPLA": "Options written",
}

COLUMNS = {
    "NACI": {
        "Run Fondo": "fund_run",
        "Nombre Fondo": "fund_name",
        "FFM_6010100": "ticker",
        "FFM_6010211": "issuer_rut",
        "FFM_6010212": "issuer_dv",
        "FFM_6010300": "issuer_country",
        "FFM_6010400": "instrument_type",
        "FFM_6010500": "maturity_date",
        "FFM_6010600": "instrument_status",
        "FFM_6010700": "rating",
        "FFM_6010800": "issuer_group",
        "FFM_6010900": "nominal",
        "FFM_6011000": "currency",
        "FFM_TIR_6011111": "yield",
        "FFM_6011112": "valuation_code",
        "FFM_6011113": "day_count",
        "FFM_6011114": "rate_type",
        "FFM_6011200": "market_value",
        "FFM_6011300": "settlement_currency",
        "FFM_6011400": "transaction_country",
        "FFM_6011511": "pct_issuer_capital",
        "FFM_6011512": "pct_issuer_assets",
        "FFM_6011513": "pct_fund_assets",
    },
    "EXTR": {
        "Run Fondo": "fund_run",
        "Nombre Fondo": "fund_name",
        "FFM_6020100": "ticker",
        "FFM_6020200": "instrument_name",
        "FFM_6020300": "issuer_country",
        "FFM_6020400": "instrument_type",
        "FFM_6020500": "maturity_date",
        "FFM_6020600": "instrument_status",
        "FFM_6020700": "rating",
        "FFM_6020800": "issuer_group",
        "FFM_6020900": "nominal",
        "FFM_6021000": "currency",
        "FFM_tir_6021111": "yield",
        "FFM_6021200": "market_value",
        "FFM_6021300": "settlement_currency",
        "FFM_6021400": "transaction_country",
        "FFM_6021513": "pct_fund_assets",
    },
    "FUTU": {
        "Run Fondo": "fund_run",
        "Nombre Fondo": "fund_name",
        "FFM_6040111": "underlying",
        "FFM_6040112": "derivative_type",
        "FFM_6040113": "strike_currency",
        "FFM_6040114": "maturity_date",
        "FFM_6040115": "settlement_currency",
        "FFM_6040116": "counterparty_country",
        "FFM_6040200": "position",
        "FFM_6040300": "notional",
        "FFM_6040400": "strike",
        "FFM_6040500": "committed_amount",
        "FFM_6040600": "market_value",
    },
}
NUMERIC = {
    "nominal",
    "yield",
    "market_value",
    "pct_issuer_capital",
    "pct_issuer_assets",
    "pct_fund_assets",
    "notional",
    "strike",
    "committed_amount",
}

# Domestic instrument types grouped into asset classes. Codes not listed fall into "Other".
ASSET_CLASS = {
    **dict.fromkeys(["DPC", "DPL", "DPF", "DPR", "DPSA", "DPFI", "OIIF"], "Bank deposits"),
    **dict.fromkeys(["BB", "BU", "BBNEE", "LH", "BH"], "Bank bonds"),
    **dict.fromkeys(["PDBC", "BCU", "BCP", "PRC", "BCD"], "Central Bank"),
    **dict.fromkeys(["BTU", "BTP", "BTF"], "Treasury"),
    **dict.fromkeys(["BE", "BNEE", "BEC", "BS"], "Corporate bonds"),
    **dict.fromkeys(["PE", "EC"], "Commercial paper"),
    "ACC": "Chilean equities",
    "CFI": "Investment fund units",
    "CFM": "Mutual fund units",  # funds holding other funds: excluded from industry totals
}
FIXED_INCOME = {"Bank deposits", "Bank bonds", "Central Bank", "Treasury", "Corporate bonds", "Commercial paper"}
DOUBLE_COUNTED = {"Mutual fund units"}

# Currency codes. PROM is the US dollar (forwards on PROM strike at ~900 CLP); DOLAR is used
# for the same thing in some FUTU files. CA and CU appear on shares and fund units and are
# read as unit counts (acciones, cuotas), not currencies.
CURRENCY = {"$$": "CLP", "UF": "UF (CPI-linked)", "PROM": "USD", "DOLAR": "USD", "EUR": "EUR"}

# Bank deposit tickers start with FN or F* followed by the bank's code. Names only for codes
# whose meaning is unambiguous; anything else is shown as the code itself.
BANK_CODES = {
    "STD": "Santander",
    "CHI": "Banco de Chile",
    "BCI": "BCI",
    "BNS": "Scotiabank",
    "ITA": "Itaú",
    "BIC": "BICE",
    "SEC": "Security",
    "EST": "BancoEstado",
    "CNO": "Consorcio",
    "INT": "Internacional",
    "BTG": "BTG Pactual",
    "COO": "Coopeuch",
    "FAL": "Banco Falabella",
    "RIP": "Banco Ripley",
}

RATING_BUCKET = {
    "AAA": "AAA",
    "AA": "AA",
    "A": "A",
    "BBB": "BBB",
    "N-1": "N-1 (short term)",
    "N-2": "N-2 and below",
    "N-3": "N-2 and below",
    "N-4": "N-2 and below",
    "N-5": "N-2 and below",
    "BB": "Below BBB",
    "B": "Below BBB",
    "C": "Below BBB",
    "D": "Below BBB",
}
