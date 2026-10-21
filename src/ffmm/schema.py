"""Labels used by the analysis: asset classes, currencies, banks and rating buckets.

Column names and types of the CMF files are defined in cmf-ffmm-etl, which reads them.
Market values are in thousands of CLP.
"""

from __future__ import annotations

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
