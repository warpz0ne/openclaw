#!/usr/bin/env python3
import json
import re
from datetime import datetime, timezone, date

import requests

UA = {"User-Agent": "Mozilla/5.0 (OpenClaw market report)"}


def ny_date_today():
    # Avoid dependencies: approximate NY by fixed offset rules is messy.
    # Instead, use UTC and let the holiday source include observed dates; this is sufficient
    # because our cron schedule is already America/New_York.
    return datetime.now(timezone.utc).date()


def get_nasdaq_trader_closed_dates(year: int):
    """Scrape NasdaqTrader Trading Calendar and return a set of date objects when US markets are CLOSED."""
    url = "https://www.nasdaqtrader.com/Trader.aspx?id=Calendar"
    html = requests.get(url, headers=UA, timeout=25).text
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, flags=re.S | re.I)
    closed = set()
    for row in rows:
        if "closed" not in row.lower():
            continue
        txt = re.sub(r"<[^<]+?>", " ", row)
        txt = " ".join(txt.split())
        # Example: "January 1, 2026 New Years Day (Observed) Closed"
        m = re.match(r"([A-Za-z]+\s+\d{1,2},\s+\d{4})\s+.*\sClosed\b", txt)
        if not m:
            continue
        ds = m.group(1)
        try:
            d = datetime.strptime(ds, "%B %d, %Y").date()
        except Exception:
            continue
        if d.year == year:
            closed.add(d)
    return closed


def is_market_closed_today():
    today = ny_date_today()
    try:
        closed = get_nasdaq_trader_closed_dates(today.year)
        return today in closed
    except Exception:
        # If the calendar scrape fails, don't block reports.
        return False


def get_json(url, timeout=20):
    r = requests.get(url, headers=UA, timeout=timeout)
    r.raise_for_status()
    return r.json()


def pct_fmt(v):
    if v is None:
        return "n/a"
    try:
        v = float(v)
        return f"{v:+.2f}%"
    except Exception:
        return "n/a"


def num_fmt(v):
    if v is None:
        return "n/a"
    try:
        v = float(v)
        if abs(v) >= 1_000_000_000_000:
            return f"{v/1_000_000_000_000:.2f}T"
        if abs(v) >= 1_000_000_000:
            return f"{v/1_000_000_000:.2f}B"
        if abs(v) >= 1_000_000:
            return f"{v/1_000_000:.2f}M"
        return f"{v:,.2f}"
    except Exception:
        return str(v)


def get_stooq_symbol(symbol):
    url = f"https://stooq.com/q/l/?s={symbol}&f=sd2t2ohlcv&h&e=json"
    # Stooq sometimes returns invalid JSON (e.g., volume:}) — sanitize lightly.
    txt = requests.get(url, headers=UA, timeout=20).text
    txt = re.sub(r'"volume":\s*}', '"volume":null}', txt)
    data = json.loads(txt)
    arr = data.get("symbols", [])
    if not arr:
        return None
    item = arr[0]
    o = item.get("open")
    c = item.get("close")
    chg_pct = None
    try:
        if o and c:
            chg_pct = ((float(c) - float(o)) / float(o)) * 100
    except Exception:
        pass
    return {
        "symbol": item.get("symbol", symbol),
        "open": o,
        "close": c,
        "change_pct": chg_pct,
        "date": item.get("date"),
        "time": item.get("time"),
    }


def get_yahoo_screener(scr_id, count):
    url = f"https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?count={count}&scrIds={scr_id}"
    data = get_json(url)
    result = (((data or {}).get("finance") or {}).get("result") or [])
    if not result:
        return []
    quotes = result[0].get("quotes", [])
    out = []
    for q in quotes:
        out.append(
            {
                "symbol": q.get("symbol"),
                "name": q.get("shortName") or q.get("longName") or "",
                "price": q.get("regularMarketPrice"),
                "change_pct": q.get("regularMarketChangePercent"),
                "market_cap": q.get("marketCap"),
            }
        )
    return out


def get_top10_marketcap_from_companiesmarketcap():
    url = "https://companiesmarketcap.com/usa/largest-companies-in-the-usa-by-market-cap/"
    html = requests.get(url, headers=UA, timeout=25).text

    # Parse each row quickly with regex (site is fairly stable)
    rows = re.findall(r"<tr>(.*?)</tr>", html, flags=re.S)
    out = []
    for row in rows:
        # skip header rows
        if "rank-td" not in row or "company-name" not in row:
            continue

        rank_m = re.search(r'class="rank-td[^"\']*"[^>]*data-sort="(\d+)"', row)
        if not rank_m:
            continue
        rank = int(rank_m.group(1))
        if rank > 10:
            continue

        name_m = re.search(r'class="company-name">\s*([^<]+)\s*</div>', row)
        cap_m = re.search(r'th-mcap|Market Cap', row)
        # Market cap cell: <td class="td-right" data-sort="4450..."> $4.450 T
        cap_cell_m = re.search(r'<td class="td-right" data-sort="\d+"[^>]*>\s*(?:<span[^>]*>\$</span>)?\s*([^<]+)\s*</td>', row)

        name = name_m.group(1).strip() if name_m else "Unknown"
        market_cap = cap_cell_m.group(1).strip() if cap_cell_m else "n/a"

        out.append({"rank": rank, "name": name, "market_cap": market_cap})

    out.sort(key=lambda x: x["rank"])
    return out[:10]


def get_crypto_prices():
    url = (
        "https://api.coingecko.com/api/v3/simple/price"
        "?ids=bitcoin,ethereum,solana&vs_currencies=usd&include_24hr_change=true"
    )
    data = get_json(url)
    def pick(k):
        d = data.get(k, {})
        return d.get("usd"), d.get("usd_24h_change")

    btc_p, btc_c = pick("bitcoin")
    eth_p, eth_c = pick("ethereum")
    sol_p, sol_c = pick("solana")

    return {
        "BTC": {"price": btc_p, "change_pct": btc_c},
        "ETH": {"price": eth_p, "change_pct": eth_c},
        "SOL": {"price": sol_p, "change_pct": sol_c},
    }


def line_stock(i, s):
    return (
        f"{i}. {s.get('symbol','?')} — {s.get('name','')[:40]} | "
        f"${num_fmt(s.get('price'))} | {pct_fmt(s.get('change_pct'))}"
    )


def main():
    if is_market_closed_today():
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        print(f"📈 Market Check — {now}\n\nUS markets are closed today (holiday). Skipping hourly report.")
        return

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    ndq = get_stooq_symbol("^ndq")
    gold = get_stooq_symbol("xauusd")

    gainers = get_yahoo_screener("day_gainers", 5)
    losers = get_yahoo_screener("day_losers", 5)
    top_mcap = get_top10_marketcap_from_companiesmarketcap()
    crypto = get_crypto_prices()

    lines = []
    lines.append(f"📈 Hourly Market Check — {now}")
    lines.append("")

    lines.append("NASDAQ")
    if ndq:
        lines.append(
            f"- NASDAQ (NDQ): {num_fmt(ndq.get('close'))} ({pct_fmt(ndq.get('change_pct'))})"
        )
    else:
        lines.append("- NASDAQ: n/a")

    lines.append("")
    lines.append("Top 5 Up (by % change)")
    for i, s in enumerate(gainers[:5], 1):
        lines.append(f"- {line_stock(i, s)}")

    lines.append("")
    lines.append("Top 5 Down (by % change)")
    for i, s in enumerate(losers[:5], 1):
        lines.append(f"- {line_stock(i, s)}")

    lines.append("")
    lines.append("Top 10 US Stocks by Market Cap")
    for s in top_mcap:
        lines.append(f"- #{s['rank']} {s['name']} — ${s['market_cap']}")

    lines.append("")
    lines.append("Crypto + Gold")
    for sym in ["BTC", "ETH", "SOL"]:
        d = crypto.get(sym, {})
        lines.append(f"- {sym}: ${num_fmt(d.get('price'))} ({pct_fmt(d.get('change_pct'))})")

    if gold:
        lines.append(f"- Gold (XAUUSD): ${num_fmt(gold.get('close'))} ({pct_fmt(gold.get('change_pct'))})")
    else:
        lines.append("- Gold: n/a")

    print("\n".join(lines))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Hourly market checker failed: {e}")
