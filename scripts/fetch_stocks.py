"""Collect prices, performance and chart history for the watchlist.

Writes, under data/stocks/:
  summary.json          one document: every ticker's price, day change and performance
  docs/<id>.json        one document per ticker with chart series (1D, 5D, 1M, 6M, 1Y, 5Y)
Source: Yahoo Finance via the yfinance package (unofficial; a failed ticker is reported, not fatal).
"""
import json, math, datetime as dt
from pathlib import Path
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "stocks"
DOCS = OUT / "docs"

RANGES = {  # range: (period, interval)
    "1D": ("1d", "5m"),
    "5D": ("5d", "30m"),
    "1M": ("1mo", "1d"),
    "6M": ("6mo", "1d"),
    "1Y": ("1y", "1d"),
    "5Y": ("5y", "1wk"),
}

def doc_id(sym):
    return "".join(ch if ch.isalnum() else "_" for ch in sym)

def rnd(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    a = abs(v)
    return round(v, 2 if a >= 100 else 3 if a >= 1 else 5)

def series(t, period, interval):
    h = t.history(period=period, interval=interval, auto_adjust=False)
    if h is None or h.empty:
        return None
    h = h.dropna(subset=["Close"])
    return {"t": [int(ts.timestamp()) for ts in h.index], "c": [rnd(float(x)) for x in h["Close"]]}

def pct(now, then):
    return None if not then else round((now / then - 1) * 100, 2)

def perf_from_daily(t_list, c_list, price):
    """Performance vs the close at or before a given date."""
    if not t_list:
        return {}
    pts = list(zip(t_list, c_list))
    last = dt.datetime.fromtimestamp(pts[-1][0], dt.timezone.utc)
    def close_on_or_before(day):
        cand = [c for ts, c in pts if dt.datetime.fromtimestamp(ts, dt.timezone.utc) <= day]
        return cand[-1] if cand else None
    year_start = dt.datetime(last.year, 1, 1, tzinfo=dt.timezone.utc) - dt.timedelta(seconds=1)
    return {
        "1W": pct(price, close_on_or_before(last - dt.timedelta(days=7))),
        "1M": pct(price, close_on_or_before(last - dt.timedelta(days=30))),
        "YTD": pct(price, close_on_or_before(year_start)),
        "1Y": pct(price, pts[0][1] if len(pts) > 200 else None),
    }

def main():
    groups = json.loads((ROOT / "scripts" / "stocks.json").read_text(encoding="utf-8"))
    DOCS.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc)
    seen, rows, errors = {}, [], []
    for topic, items in groups.items():
        for name, sym in items:
            row = {"topic": topic, "name": name, "symbol": sym}
            if not sym:
                row["status"] = "not listed"
                rows.append(row)
                continue
            if sym in seen:  # same ticker in two topics: reuse
                rows.append({**seen[sym], "topic": topic, "name": name})
                continue
            try:
                t = yf.Ticker(sym)
                ser = {k: series(t, p, i) for k, (p, i) in RANGES.items()}
                daily = ser.get("1Y") or ser.get("6M") or ser.get("1M")
                if not daily:
                    raise ValueError("no price history")
                intraday = ser.get("1D")
                price = (intraday or daily)["c"][-1]
                prev = None
                try:
                    prev = float(t.fast_info.get("previous_close") or t.fast_info.get("regular_market_previous_close"))
                except Exception:
                    pass
                if not prev and len(daily["c"]) > 1:
                    prev = daily["c"][-2]
                try:
                    currency = t.fast_info.get("currency")
                except Exception:
                    currency = None
                as_of = (intraday or daily)["t"][-1]
                row.update({
                    "status": "ok", "id": doc_id(sym), "currency": currency, "price": rnd(price),
                    "change": rnd(price - prev) if prev else None, "changePct": pct(price, prev),
                    "perf": perf_from_daily(daily["t"], daily["c"], price),
                    "asOf": dt.datetime.fromtimestamp(as_of, dt.timezone.utc).isoformat(),
                    "spark": daily["c"][-22:],
                })
                hist = {"symbol": sym, "name": name, "currency": currency, "updatedAt": now.isoformat(),
                        "series": {k: v for k, v in ser.items() if v}}
                (DOCS / f"{doc_id(sym)}.json").write_text(json.dumps(hist, separators=(",", ":")), encoding="utf-8")
                seen[sym] = row
            except Exception as e:
                row["status"] = "error"
                errors.append(f"{sym}: {e}")
            rows.append(row)
    summary = {"updatedAt": now.isoformat(), "source": "Yahoo Finance (via yfinance)", "rows": rows, "errors": errors}
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    ok = sum(1 for r in rows if r.get("status") == "ok")
    print(f"{ok} prices, {len(errors)} errors")
    for e in errors:
        print("  ", e)

if __name__ == "__main__":
    main()
