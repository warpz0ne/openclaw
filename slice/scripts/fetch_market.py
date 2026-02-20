#!/usr/bin/env python3
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

BASE = "https://query1.finance.yahoo.com"

TRACKED_MCAP = ["NVDA", "AAPL", "GOOG", "MSFT", "AMZN", "META", "AVGO", "TSLA", "BRK-B", "WMT"]
CORE = ["^IXIC", "BTC-USD", "ETH-USD", "SOL-USD", "GC=F"]

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "latest.json"
WEB_FILE = ROOT / "web" / "latest.json"


def fetch_json(url: str):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36"
        },
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def quote(symbols):
    q = urllib.parse.urlencode({"symbols": ",".join(symbols)})
    url = f"{BASE}/v7/finance/quote?{q}"
    data = fetch_json(url)
    return data.get("quoteResponse", {}).get("result", [])


def screener(scr_id: str, count: int = 5):
    q = urllib.parse.urlencode({"scrIds": scr_id, "count": count})
    url = f"{BASE}/v1/finance/screener/predefined/saved?{q}"
    data = fetch_json(url)
    quotes = (
        data.get("finance", {})
        .get("result", [{}])[0]
        .get("quotes", [])
    )
    out = []
    for x in quotes[:count]:
        out.append(
            {
                "symbol": x.get("symbol"),
                "name": x.get("shortName") or x.get("longName") or x.get("symbol"),
                "price": x.get("regularMarketPrice"),
                "changePct": x.get("regularMarketChangePercent"),
            }
        )
    return out


def compact_quote_map(quotes):
    out = {}
    for x in quotes:
        s = x.get("symbol")
        if not s:
            continue
        out[s] = {
            "symbol": s,
            "name": x.get("shortName") or x.get("longName") or s,
            "price": x.get("regularMarketPrice"),
            "changePct": x.get("regularMarketChangePercent"),
            "marketCap": x.get("marketCap"),
        }
    return out


def fmt_num(v):
    if v is None:
        return None
    return round(float(v), 2)


def run():
    core = compact_quote_map(quote(CORE))
    mcap_quotes = compact_quote_map(quote(TRACKED_MCAP))

    top_mcap = sorted(
        [mcap_quotes[s] for s in mcap_quotes],
        key=lambda x: x.get("marketCap") or 0,
        reverse=True,
    )[:10]

    # Yahoo screeners can fail occasionally; keep resilient.
    try:
        gainers = screener("day_gainers", 5)
    except Exception:
        gainers = []
    try:
        losers = screener("day_losers", 5)
    except Exception:
        losers = []

    now_utc = datetime.now(timezone.utc)
    now_et = now_utc.astimezone(ZoneInfo("America/New_York"))

    payload = {
        "brand": "Slice",
        "generatedAtUtc": now_utc.isoformat(),
        "generatedAtEt": now_et.isoformat(),
        "generatedAtEtDisplay": now_et.strftime("%Y-%m-%d %I:%M %p ET"),
        "nasdaq": {
            "symbol": "^IXIC",
            "name": core.get("^IXIC", {}).get("name", "NASDAQ Composite"),
            "price": fmt_num(core.get("^IXIC", {}).get("price")),
            "changePct": fmt_num(core.get("^IXIC", {}).get("changePct")),
        },
        "topGainers": [
            {
                "symbol": x.get("symbol"),
                "name": x.get("name"),
                "price": fmt_num(x.get("price")),
                "changePct": fmt_num(x.get("changePct")),
            }
            for x in gainers
        ],
        "topLosers": [
            {
                "symbol": x.get("symbol"),
                "name": x.get("name"),
                "price": fmt_num(x.get("price")),
                "changePct": fmt_num(x.get("changePct")),
            }
            for x in losers
        ],
        "topUsMcapTracked": [
            {
                "symbol": x.get("symbol"),
                "name": x.get("name"),
                "marketCap": x.get("marketCap"),
            }
            for x in top_mcap
        ],
        "assets": {
            "BTC": {
                "price": fmt_num(core.get("BTC-USD", {}).get("price")),
                "changePct": fmt_num(core.get("BTC-USD", {}).get("changePct")),
            },
            "ETH": {
                "price": fmt_num(core.get("ETH-USD", {}).get("price")),
                "changePct": fmt_num(core.get("ETH-USD", {}).get("changePct")),
            },
            "SOL": {
                "price": fmt_num(core.get("SOL-USD", {}).get("price")),
                "changePct": fmt_num(core.get("SOL-USD", {}).get("changePct")),
            },
            "GOLD": {
                "price": fmt_num(core.get("GC=F", {}).get("price")),
                "changePct": fmt_num(core.get("GC=F", {}).get("changePct")),
            },
        },
    }

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    WEB_FILE.parent.mkdir(parents=True, exist_ok=True)

    txt = json.dumps(payload, indent=2)
    DATA_FILE.write_text(txt + "\n", encoding="utf-8")
    WEB_FILE.write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    run()
