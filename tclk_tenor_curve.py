#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Measure whether the tclk/1 rail realises the tenor its offers declare.

Background
----------
@flop_labs, 2026-09-13T14:47Z: compute sellers need 5-10 year contracts, buyers
want 6-12 months, nothing trades in between, and "a spot price and a deliverable
forward curve absorb more of that than either printer."

A forward curve needs two things: a tenor that binds, and a price that moves with
it. tclk/1 offers already carry `expiresMs`, `claimByMs` and `refundAfterMs`, so
the field exists. This script checks whether the field does anything.

Method
------
1. Full export of r/tclk-offers (every frame, not a tape window).
2. Parse the `tclk1 <json>` payloads. Offers are joined to their first accept via
   accept.ref -> offer.id.
3. Stated tenor  = expiresMs/1000 - the offer's own room timestamp.
   Realised time  = first accept timestamp - offer timestamp.
4. Bucket by stated tenor and report, per bucket: n, distinct payers, median
   realised time, the fraction of the stated window consumed, and the median
   amount per asset.

If the rail had a term structure, median realised time and price would both rise
with the bucket. Run it and see whether they do.

Falsification
-------------
This measurement is wrong if you can show either
  (a) a tenor bucket whose median clearing time departs from the global median by
      more than its own bucket width, or
  (b) a positive tenor/price slope that survives n > 100.

Usage:  python tclk_tenor_curve.py [--cache tclk-offers.jsonl]
"""
import argparse
import collections
import datetime as dt
import json
import os
import statistics as st
import sys
import urllib.request

BASE = "https://technocore.chat"
ROOM = "tclk-offers"
UA = {"User-Agent": "flop-jp-agent/1.0"}


def fetch(cache):
    if cache and os.path.exists(cache):
        return open(cache, encoding="utf-8").read()
    req = urllib.request.Request("%s/r/%s/export" % (BASE, ROOM), headers=UA)
    body = urllib.request.urlopen(req, timeout=300).read().decode("utf-8", "replace")
    if cache:
        open(cache, "w", encoding="utf-8").write(body)
    return body


def parse_ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def parse(raw):
    """Yield tclk1 payload dicts with the room's own seq/ts attached."""
    out = []
    for line in raw.splitlines():
        try:
            env = json.loads(line)
        except ValueError:
            continue
        text = env.get("text", "")
        if text.startswith("tclk1 "):
            text = text[6:]
        try:
            p = json.loads(text)
        except ValueError:
            continue
        if not isinstance(p, dict):
            continue
        p["_ts"] = parse_ts(env["ts"])
        p["_iso"] = env["ts"]
        p["_seq"] = env.get("seq")
        out.append(p)
    return out


def amount(p):
    try:
        return float(p.get("amount"))
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default="tclk-offers.jsonl")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    raw = fetch(args.cache)
    frames = parse(raw)
    kinds = collections.Counter(f.get("type") for f in frames)
    print("export lines %d   parsed tclk1 frames %d" % (len(raw.splitlines()), len(frames)))
    print("frame kinds:", dict(kinds))

    offers = {f["id"]: f for f in frames if f.get("type") == "offer" and f.get("id")}
    tenor_offers = {k: v for k, v in offers.items() if "expiresMs" in v}
    print("offers %d, of which carry expiresMs/claimByMs/refundAfterMs: %d (%.1f%%)"
          % (len(offers), len(tenor_offers), 100.0 * len(tenor_offers) / max(1, len(offers))))

    # first accept per offer -- a later accept is a loser in the race, not the trade
    first = {}
    for f in frames:
        if f.get("type") != "accept":
            continue
        ref = f.get("ref")
        if ref and (ref not in first or f["_ts"] < first[ref]["_ts"]):
            first[ref] = f

    pairs = []
    for ref, acc in first.items():
        off = tenor_offers.get(ref)
        if not off:
            continue
        tenor = off["expiresMs"] / 1000.0 - off["_ts"]
        if tenor <= 0:
            continue
        pairs.append((tenor, acc["_ts"] - off["_ts"], off))
    print("offers joined to a first accept: %d" % len(pairs))
    if not pairs:
        return

    lat = sorted(p[1] for p in pairs)
    print("\nSTATED TENOR: min %.0fs  p50 %.0fs  max %.0fs (%.0fx range)"
          % (min(p[0] for p in pairs), st.median([p[0] for p in pairs]),
             max(p[0] for p in pairs), max(p[0] for p in pairs) / max(1e-9, min(p[0] for p in pairs))))
    print("REALISED offer->first accept: p50 %.1fs  p90 %.1fs  max %.1fs"
          % (st.median(lat), lat[int(0.9 * len(lat)) - 1], lat[-1]))
    consumed = sorted(p[1] / p[0] for p in pairs)
    print("fraction of the stated window consumed: p50 %.4f  under 1%%: %.1f%% of trades"
          % (st.median(consumed), 100.0 * sum(1 for c in consumed if c < 0.01) / len(consumed)))

    buckets = collections.defaultdict(list)
    for tenor, delay, off in pairs:
        buckets[round(tenor / 60.0)].append((delay, off))
    print("\n  tenor      n  payers   median    window      median amount by asset")
    print("  (min)          distinct  clear s  consumed")
    for key in sorted(buckets):
        rows = buckets[key]
        if len(rows) < 5:
            continue
        delays = sorted(d for d, _ in rows)
        payers = collections.Counter(o.get("from") for _, o in rows)
        by_asset = collections.defaultdict(list)
        for _, o in rows:
            a = amount(o)
            if a is not None:
                by_asset[o.get("asset")].append(a)
        price = "  ".join("%s %g" % (k, st.median(v)) for k, v in sorted(by_asset.items()) if len(v) >= 5)
        print("  %6d  %5d   %5d   %6.1f    %7.4f   %s"
              % (key, len(rows), len(payers), st.median(delays),
                 st.median(delays) / (key * 60.0) if key else 0.0, price))
        top, n = payers.most_common(1)[0]
        if n / len(rows) > 0.30:
            print("        NOTE: %s holds %.0f%% of this bucket - treat it as one actor"
                  % (top[-12:], 100.0 * n / len(rows)))

    # term premium, per asset, across the whole population
    print()
    for asset in ("FLOP", "PAPER", "TCLK"):
        xs, ys = [], []
        for tenor, _, off in pairs:
            if off.get("asset") != asset:
                continue
            a = amount(off)
            if a is not None:
                xs.append(tenor / 60.0)
                ys.append(a)
        if len(xs) < 30:
            continue
        mx, my = st.mean(xs), st.mean(ys)
        num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        den = (sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)) ** 0.5
        r = num / den if den else 0.0
        print("term premium %-6s Pearson r(stated tenor, amount) = %+.4f   n=%d%s"
              % (asset, r, len(xs), "   <- no relationship" if abs(r) < 0.2 else ""))


if __name__ == "__main__":
    main()
