"""Alpha chainId → 各数据源的链标识。新增链只改这里。"""

CHAINS = {
    "56":     dict(slug="bsc",      dex="bsc",      cg="binance-smart-chain", explorer="https://bscscan.com/token/{a}"),
    "1":      dict(slug="ethereum", dex="ethereum", cg="ethereum",            explorer="https://etherscan.io/token/{a}"),
    "CT_501": dict(slug="solana",   dex="solana",   cg="solana",              explorer="https://solscan.io/token/{a}"),
    "8453":   dict(slug="base",     dex="base",     cg="base",                explorer="https://basescan.org/token/{a}"),
    "42161":  dict(slug="arbitrum", dex="arbitrum", cg="arbitrum-one",        explorer="https://arbiscan.io/token/{a}"),
    "146":    dict(slug="sonic",    dex="sonic",    cg="sonic",               explorer="https://sonicscan.org/token/{a}"),
    "CT_195": dict(slug="tron",     dex="tron",     cg="tron",                explorer="https://tronscan.org/#/token20/{a}"),
    "59144":  dict(slug="linea",    dex="linea",    cg="linea",               explorer="https://lineascan.build/token/{a}"),
    "CT_784": dict(slug="sui",      dex="sui",      cg="sui",                 explorer="https://suivision.xyz/coin/{a}"),
    "4663":   dict(slug="robinhood", dex=None,      cg=None,                  explorer=None),
}


def chain_info(chain_id):
    return CHAINS.get(str(chain_id), dict(slug=str(chain_id), dex=None, cg=None, explorer=None))
