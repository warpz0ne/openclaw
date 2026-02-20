#!/usr/bin/env python3
import csv
import io
import json
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

UA = {"User-Agent": "Mozilla/5.0 (Slice market updater)"}
OUT = "/home/manu/.openclaw/workspace/slice/web/latest.json"

TOP = [
    ("NVDA", "NVIDIA", "nvda.us"),
    ("AAPL", "Apple", "aapl.us"),
    ("GOOGL", "Alphabet", "googl.us"),
    ("MSFT", "Microsoft", "msft.us"),
    ("AMZN", "Amazon", "amzn.us"),
    ("META", "Meta Platforms", "meta.us"),
    ("AVGO", "Broadcom", "avgo.us"),
    ("TSLA", "Tesla", "tsla.us"),
    ("BRK-B", "Berkshire Hathaway", "brk-b.us"),
    ("WMT", "Walmart", "wmt.us"),
]

# (label, stooq_symbol, yahoo_symbol, region)
INDEX_SPECS = [
    ("NASDAQ", "^ndq", "^IXIC", "US"),
    ("S&P 500", "^spx", "^GSPC", "US"),
    ("FTSE 100", "^ukx", "^FTSE", "INTL"),
    ("DAX", "^dax", "^GDAXI", "INTL"),
    ("Nikkei 225", "^nkx", "^N225", "INTL"),
    ("Hang Seng", "^hsi", "^HSI", "INTL"),
    ("CAC 40", "^cac", "^FCHI", "INTL"),
    ("Nifty 50", "^nif", "^NSEI", "INTL"),
    ("BSE Sensex", "^snx", "^BSESN", "INTL"),
]

# (symbol, name, theme, stooq_symbol)
ETF_SPECS = [
    ("VGT", "Vanguard Information Technology ETF", "US Tech", "vgt.us"),
    ("VOO", "Vanguard S&P 500 ETF", "US Broad", "voo.us"),
    ("VTI", "Vanguard Total Stock Market ETF", "US Broad", "vti.us"),
    ("VGK", "Vanguard FTSE Europe ETF", "Europe (FTSE 100 / DAX / CAC)", "vgk.us"),
    ("VPL", "Vanguard FTSE Pacific ETF", "Pacific (Nikkei / Hang Seng)", "vpl.us"),
    ("VWO", "Vanguard FTSE Emerging Markets ETF", "India (Nifty / Sensex)", "vwo.us"),
]

STABLE_SYMBOLS = {"USDT", "USDC", "DAI", "TUSD", "FDUSD", "USDE", "USDP", "PYUSD"}


def get_text(url, timeout=10):
    return requests.get(url, headers=UA, timeout=timeout).text


def pct_from_base(cur, base):
    if cur is None or base in (None, 0):
        return None
    return ((cur - base) / base) * 100


def closest_on_or_before(rows, target_date):
    pick = None
    for r in rows:
        if r["date"] <= target_date:
            pick = r
        else:
            break
    return pick


def perf_metrics(rows, current_price):
    if not rows:
        return {
            "todayPct": None,
            "currentClose": None,
            "ytdPct": None,
            "oneYearPct": None,
            "threeYearPct": None,
            "fiveYearPct": None,
            "week52Low": None,
            "week52High": None,
            "week52PosPct": None,
        }

    rows = sorted(rows, key=lambda x: x["date"])
    if current_price is None:
        current_price = rows[-1].get("close")

    now_et = datetime.now(ZoneInfo("America/New_York")).date()
    y_start = datetime(now_et.year, 1, 1).date()
    d1 = datetime(now_et.year - 1, now_et.month, now_et.day).date()
    d3 = datetime(now_et.year - 3, now_et.month, now_et.day).date()
    d5 = datetime(now_et.year - 5, now_et.month, now_et.day).date()

    y_base = closest_on_or_before(rows, y_start)
    p1 = closest_on_or_before(rows, d1)
    p3 = closest_on_or_before(rows, d3)
    p5 = closest_on_or_before(rows, d5)

    w52 = [r for r in rows if r["date"] >= d1]
    w52_low = min((r["low"] for r in w52), default=None)
    w52_high = max((r["high"] for r in w52), default=None)
    w52_pos = None
    if current_price is not None and w52_low is not None and w52_high is not None and w52_high > w52_low:
        w52_pos = ((current_price - w52_low) / (w52_high - w52_low)) * 100

    prev_close = rows[-2]["close"] if len(rows) >= 2 else None
    today_pct = pct_from_base(current_price, prev_close)

    return {
        "todayPct": today_pct,
        "currentClose": current_price,
        "ytdPct": pct_from_base(current_price, y_base["close"] if y_base else None),
        "oneYearPct": pct_from_base(current_price, p1["close"] if p1 else None),
        "threeYearPct": pct_from_base(current_price, p3["close"] if p3 else None),
        "fiveYearPct": pct_from_base(current_price, p5["close"] if p5 else None),
        "week52Low": w52_low,
        "week52High": w52_high,
        "week52PosPct": w52_pos,
    }


def yahoo_chart_metrics(symbol):
    try:
        r = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
            params={"interval": "1d", "range": "10y", "events": "history"},
            headers=UA,
            timeout=8,
        )
        d = r.json()
        res = (d.get("chart", {}).get("result") or [None])[0]
        if not res:
            return {}
        ts = res.get("timestamp") or []
        q = res.get("indicators", {}).get("quote", [{}])[0]
        closes = q.get("close") or []
        highs = q.get("high") or []
        lows = q.get("low") or []
        rows = []
        for i, t in enumerate(ts):
            try:
                c, h, l = closes[i], highs[i], lows[i]
                if c is None or h is None or l is None:
                    continue
                rows.append({
                    "date": datetime.fromtimestamp(t, tz=ZoneInfo("America/New_York")).date(),
                    "close": float(c),
                    "high": float(h),
                    "low": float(l),
                })
            except Exception:
                continue
        if not rows:
            return {}
        rows.sort(key=lambda x: x["date"])
        return perf_metrics(rows, rows[-1]["close"])
    except Exception:
        return {}


def normalized_row(name, symbol, current_price, perf, extra=None):
    extra = extra or {}
    return {
        "name": name,
        "symbol": symbol,
        "currentPrice": current_price,
        "changePctToday": perf.get("todayPct"),
        "ytdPct": perf.get("ytdPct"),
        "oneYearPct": perf.get("oneYearPct"),
        "threeYearPct": perf.get("threeYearPct"),
        "fiveYearPct": perf.get("fiveYearPct"),
        "week52Low": perf.get("week52Low"),
        "week52High": perf.get("week52High"),
        "week52PosPct": perf.get("week52PosPct"),
        **extra,
    }


def crypto_top10():
    preferred = ["BTC", "ETH", "SOL", "XRP", "BNB", "ADA", "DOGE", "TRX", "DOT", "LINK", "AVAX", "TON", "LTC"]
    try:
        data = requests.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": 100,
                "page": 1,
                "sparkline": "false",
                "price_change_percentage": "24h",
            },
            headers=UA,
            timeout=8,
        ).json()
        if not isinstance(data, list):
            data = []
    except Exception:
        data = []

    cleaned = []
    for x in data:
        if not isinstance(x, dict):
            continue
        sym = (x.get("symbol") or "").upper()
        if not re.match(r"^[A-Z]{2,6}$", sym):
            continue
        if sym in STABLE_SYMBOLS:
            continue
        cleaned.append(
            {
                "id": x.get("id"),
                "symbol": sym,
                "name": x.get("name"),
                "price": x.get("current_price"),
                "changePct": x.get("price_change_percentage_24h"),
                "marketCap": x.get("market_cap"),
            }
        )

    by_sym = {x["symbol"]: x for x in cleaned}
    out = []
    used = set()
    for sym in preferred:
        if sym in by_sym and sym not in used:
            out.append(by_sym[sym])
            used.add(sym)
        if len(out) >= 10:
            break
    if len(out) < 10:
        for x in cleaned:
            if x["symbol"] in used:
                continue
            out.append(x)
            used.add(x["symbol"])
            if len(out) >= 10:
                break

    # Fallback when CoinGecko is unavailable: build from Yahoo symbols.
    if not out:
        out = [{"symbol": s, "name": s, "price": None, "changePct": None, "marketCap": None} for s in preferred[:10]]

    rows = []
    for i, x in enumerate(out, start=1):
        perf = yahoo_chart_metrics(f"{x.get('symbol')}-USD")
        if not perf:
            perf = {
                "todayPct": x.get("changePct"),
                "ytdPct": None,
                "oneYearPct": None,
                "threeYearPct": None,
                "fiveYearPct": None,
                "week52Low": None,
                "week52High": None,
                "week52PosPct": None,
            }

        current_price = x.get("price") if x.get("price") is not None else perf.get("currentClose")
        today_pct = perf.get("todayPct") if perf.get("todayPct") is not None else x.get("changePct")
        rows.append(
            {
                "name": x.get("name"),
                "symbol": x.get("symbol"),
                "currentPrice": current_price,
                "changePctToday": today_pct,
                "ytdPct": perf.get("ytdPct"),
                "oneYearPct": perf.get("oneYearPct"),
                "threeYearPct": perf.get("threeYearPct"),
                "fiveYearPct": perf.get("fiveYearPct"),
                "week52Low": perf.get("week52Low"),
                "week52High": perf.get("week52High"),
                "week52PosPct": perf.get("week52PosPct"),
                "rank": i,
                "marketCap": x.get("marketCap"),
            }
        )
    return rows


def main():
    now_utc = datetime.now(timezone.utc)
    now_et = now_utc.astimezone(ZoneInfo("America/New_York"))

    prev = {}
    try:
        with open(OUT, "r", encoding="utf-8") as f:
            prev = json.load(f)
    except Exception:
        prev = {}

    indexes = []
    for label, _stooq_sym, yahoo_sym, region in INDEX_SPECS:
        perf = yahoo_chart_metrics(yahoo_sym)
        indexes.append(normalized_row(label, yahoo_sym, perf.get("currentClose"), perf, {"region": region}))

    etfs = []
    for symbol, name, theme, _stooq_sym in ETF_SPECS:
        perf = yahoo_chart_metrics(symbol)
        etfs.append(normalized_row(name, symbol, perf.get("currentClose"), perf, {"theme": theme}))

    companies = []
    for symbol, name, _stq in TOP:
        perf = yahoo_chart_metrics(symbol)
        companies.append(normalized_row(name, symbol, perf.get("currentClose"), perf, {"marketCap": None}))

    crypto = crypto_top10()
    if not crypto:
        crypto = prev.get("cryptoTop10", [])

    payload = {
        "brand": "Slice",
        "generatedAtUtc": now_utc.isoformat().replace("+00:00", "Z"),
        "generatedAtEt": now_et.isoformat(),
        "generatedAtEtDisplay": now_et.strftime("%Y-%m-%d %I:%M %p ET"),
        "indexes": indexes,
        "cryptoTop10": crypto,
        "etfs": etfs,
        "topUsMcapTracked": companies[:10],
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"))


if __name__ == "__main__":
    main()
