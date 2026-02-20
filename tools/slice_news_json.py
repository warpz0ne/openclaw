#!/usr/bin/env python3
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

UA = {"User-Agent": "Mozilla/5.0 (Slice news updater)"}
ROOT = Path("/home/manu/.openclaw/workspace/slice")
OUT = ROOT / "web" / "news.json"

CATEGORIES = [
    {
        "key": "ndtv",
        "title": "NDTV",
        "feeds": ["https://feeds.feedburner.com/ndtvnews-top-stories"],
    },
    {
        "key": "indiatoday",
        "title": "India Today",
        "feeds": ["https://www.indiatoday.in/rss/home"],
    },
    {
        "key": "ai_news",
        "title": "AI News",
        "feeds": ["https://techcrunch.com/category/artificial-intelligence/feed/"],
    },
    {
        "key": "geekwire",
        "title": "GeekWire",
        "feeds": ["https://www.geekwire.com/feed/"],
    },
    {
        "key": "techmeme",
        "title": "Techmeme",
        "feeds": ["https://www.techmeme.com/feed.xml"],
    },
    {
        "key": "wired_ai",
        "title": "Wired AI",
        "feeds": ["https://www.wired.com/feed/tag/ai/latest/rss"],
    },
    {
        "key": "wired_trending",
        "title": "Wired Trending",
        "feeds": ["https://www.wired.com/feed/rss"],
    },
    {
        "key": "axios",
        "title": "Axios",
        "feeds": ["https://www.axios.com/feeds/feed.rss"],
    },
    {
        "key": "bbc",
        "title": "BBC News",
        "feeds": ["https://www.bbc.com/news/rss.xml"],
    },
    {
        "key": "espn_cricinfo",
        "title": "ESPNcricinfo",
        "feeds": ["https://www.espncricinfo.com/rss/content/story/feeds/0.xml"],
    },
    {
        "key": "espn_f1",
        "title": "ESPN F1",
        "feeds": ["https://www.espn.com/espn/rss/f1/news"],
    },
    {
        "key": "toms_hardware",
        "title": "Tom's Hardware",
        "feeds": ["https://www.tomshardware.com/feeds/all"],
    },
]


def text(x):
    return (x or "").strip()


def parse_feed(url: str):
    items = []
    try:
        r = requests.get(url, headers=UA, timeout=20)
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception:
        return items

    channel_title = text(root.findtext("./channel/title"))

    # RSS
    for it in root.findall("./channel/item"):
        title = text(it.findtext("title"))
        link = text(it.findtext("link"))
        pub = text(it.findtext("pubDate"))
        src_tag = it.find("source")
        source = text(src_tag.text if src_tag is not None else "") or channel_title
        desc = text(it.findtext("description"))

        img = None
        enc = it.find("enclosure")
        if enc is not None and str(enc.attrib.get("type", "")).startswith("image"):
            img = enc.attrib.get("url")
        if not img:
            mt = it.find("{http://search.yahoo.com/mrss/}thumbnail")
            if mt is not None:
                img = mt.attrib.get("url")
        if not img:
            m = re.search(r'<img[^>]+src=["\']([^"\']+)', desc or "", re.I)
            if m:
                img = m.group(1)

        if title and link:
            items.append({"title": title, "url": link, "source": source, "published": pub, "image": img})

    # Atom
    atom_entries = root.findall("{http://www.w3.org/2005/Atom}entry")
    atom_title = text(root.findtext("{http://www.w3.org/2005/Atom}title"))
    for e in atom_entries:
        title = text(e.findtext("{http://www.w3.org/2005/Atom}title"))
        link = ""
        link_el = e.find("{http://www.w3.org/2005/Atom}link")
        if link_el is not None:
            link = text(link_el.attrib.get("href"))
        pub = text(e.findtext("{http://www.w3.org/2005/Atom}updated")) or text(e.findtext("{http://www.w3.org/2005/Atom}published"))
        source = atom_title
        if title and link:
            items.append({"title": title, "url": link, "source": source, "published": pub, "image": None})

    return items


def curate_category(cat):
    seen = set()
    out = []
    for feed in cat["feeds"]:
        for it in parse_feed(feed):
            key = (it.get("url") or "").strip()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(it)
            if len(out) >= 15:
                break
        if len(out) >= 15:
            break
    return out[:5]


def main():
    now_utc = datetime.now(timezone.utc)
    now_et = now_utc.astimezone(ZoneInfo("America/New_York"))

    categories = [{"key": cat["key"], "title": cat["title"], "items": curate_category(cat)} for cat in CATEGORIES]

    payload = {
        "generatedAtUtc": now_utc.isoformat().replace("+00:00", "Z"),
        "generatedAtEtDisplay": now_et.strftime("%Y-%m-%d %I:%M %p ET"),
        "categories": categories,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
