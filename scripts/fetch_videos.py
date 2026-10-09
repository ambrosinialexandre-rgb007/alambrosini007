"""Collect the newest videos from each channel's official YouTube feed.

Writes data/videos.json: {"generatedAt": ISO, "topics": {topic: [video, ...]}, "errors": [...]}
Each video: title, url, channel, published (ISO), topic. Only the last 7 days are kept.
"""
import json, datetime as dt, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={}"
MAX_AGE = dt.timedelta(days=7)
PER_CHANNEL = 8

import re
CACHE = ROOT / "data" / "channel_ids.json"

def resolve(ref, cache):
    """Channel references are UC ids, or YouTube addresses such as @handle, c/name, user/name or a custom name."""
    if re.fullmatch(r"UC[\w-]{22}", ref):
        return ref
    if ref in cache:
        return cache[ref]
    req = urllib.request.Request("https://www.youtube.com/" + ref, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en"})
    with urllib.request.urlopen(req, timeout=20) as r:
        html = r.read().decode("utf-8", "ignore")
    m = re.search(r'"externalId":"(UC[\w-]{22})"', html) or re.search(r'<meta itemprop="identifier" content="(UC[\w-]{22})"', html) or re.search(r'"channelId":"(UC[\w-]{22})"', html)
    if not m:
        raise ValueError("could not resolve channel id for " + ref)
    cache[ref] = m.group(1)
    return cache[ref]

def fetch(channel_id):
    req = urllib.request.Request(FEED.format(channel_id), headers={"User-Agent": "Mozilla/5.0 morning-wire"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return ET.fromstring(r.read())

def main():
    channels = json.loads((ROOT / "scripts" / "channels.json").read_text(encoding="utf-8"))
    now = dt.datetime.now(dt.timezone.utc)
    out, errors = {}, []
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    for topic, chans in channels.items():
        vids = []
        for name, cid in chans.items():
            try:
                root = fetch(resolve(cid, cache))
            except Exception as e:  # keep going; one bad feed must not stop the rest
                errors.append(f"{name}: {e}")
                continue
            for entry in root.findall("a:entry", NS)[:PER_CHANNEL]:
                vid = entry.findtext("yt:videoId", default="", namespaces=NS)
                pub = entry.findtext("a:published", default="", namespaces=NS)
                try:
                    when = dt.datetime.fromisoformat(pub.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if not vid or now - when > MAX_AGE:
                    continue
                vids.append({
                    "title": entry.findtext("a:title", default="", namespaces=NS),
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "channel": name,
                    "published": when.isoformat(),
                    "topic": topic,
                })
        vids.sort(key=lambda v: v["published"], reverse=True)
        out[topic] = vids
    data = {"generatedAt": now.isoformat(), "topics": out, "errors": errors}
    (ROOT / "data").mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(cache, indent=1), encoding="utf-8")
    (ROOT / "data" / "videos.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{sum(len(v) for v in out.values())} videos, {len(errors)} feed errors")

if __name__ == "__main__":
    main()
