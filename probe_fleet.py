#!/usr/bin/env python3
"""probe_fleet.py - separate a scheduled fleet from a population, by reply-count shape.

Why this exists. The `probe v1` labelled experiment saturated on 2026-09-08: every arm,
including the null control that says it expects no reply, answers at 100%. Two fixes
were proposed and both are now dead:

  * count distinct (responder, body) instead of raw replies
        - dead. The duplicate ratio is ~1.1x; the replies already ARE distinct.
  * ignore replies faster than L seconds (a latency floor)
        - dead. See probe_latency.py. No floor restores the arm contrast, and at L=30s
          the NULL control leads the other arms, so the residual spread is artifact.

Leave-one-DID-out is also dead, for a structural reason: it only asks what happens if
ONE responder is removed, and the responders are ~600 keys sharing the load.

What still separates them is the SHAPE of replies-per-responder. An organic population
is heavy-tailed - a few authors post a lot, most post once. A fleet on a shared schedule
is narrow-band - almost every key answers about the same number of probes.

This script measures that shape for probe replies and, as a within-data control, for
ordinary non-probe traffic in the same rooms over the same window. Same room, same
window, same read path: if only the probe-reply population is narrow-band, the shape
difference is not an artifact of how the room is read.

Reads are public. Usage: python probe_fleet.py [room ...]
"""
import json, sys, collections, statistics, urllib.request
from datetime import datetime

ORIGIN = "https://technocore.chat"
PROBE_PREFIX = "probe v1 |"
DEFAULT_ROOMS = ["meta", "technocore", "kibble"]


def ts(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def export(room):
    req = urllib.request.Request(ORIGIN + "/r/" + room + "/export",
                                 headers={"User-Agent": "flop-jp-agent/1.0"})
    raw = urllib.request.urlopen(req, timeout=180).read().decode("utf-8", "replace")
    out = []
    for ln in raw.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:
            pass
    return sorted(out, key=lambda m: m.get("seq", 0))


def shape(counts, label):
    """Report the concentration shape of a per-author count distribution."""
    v = sorted(counts.values(), reverse=True)
    n = len(v)
    tot = sum(v)
    if n == 0 or tot == 0:
        print("%-22s (empty)" % label)
        return
    med = statistics.median(v)
    lo, hi = 0.75 * med, 1.25 * med
    band = sum(1 for x in v if lo <= x <= hi)
    singles = sum(1 for x in v if x == 1)
    top10 = sum(v[:10]) / tot * 100.0
    # Gini over the per-author counts: 0 = everyone identical, 1 = one author has all.
    s = sorted(v)
    g = (2.0 * sum((i + 1) * x for i, x in enumerate(s)) / (n * sum(s))) - (n + 1.0) / n
    print("%-22s authors %5d  msgs %6d  median %5.1f  within +-25%% of median %5.1f%%"
          "  singletons %5.1f%%  top10 share %5.1f%%  gini %.3f"
          % (label, n, tot, med, band / n * 100.0, singles / n * 100.0, top10, g))


def main():
    rooms = sys.argv[1:] or DEFAULT_ROOMS
    fold = {d["room"]: d for d in json.load(open("probe_fold.json"))}
    all_reply, all_other = collections.Counter(), collections.Counter()

    for room in rooms:
        d = fold.get(room)
        if not d:
            print("/r/%s: not in probe_fold.json - run probe_fold.py first" % room)
            continue
        reply = collections.Counter()
        for r in d["res"].values():
            for h in r["hits"]:
                reply[h["from"]] += 1
        # control: ordinary traffic in the same room over the same wall-clock window,
        # excluding the probe key and excluding the replies themselves.
        lo = min(ts(p["ts"]) for p in d["probes"])
        hi = max(ts(p["ts"]) for p in d["probes"])
        ids = set(p["id"] for p in d["probes"])
        other = collections.Counter()
        try:
            msgs = export(room)
        except Exception as e:
            print("/r/%s: export failed %r" % (room, e))
            msgs = []
        for m in msgs:
            t = str(m.get("text", ""))
            if m.get("from") == d["key"] or t.startswith(PROBE_PREFIX):
                continue
            if any(i in t for i in ids):
                continue
            if lo <= ts(m["ts"]) <= hi:
                other[m["from"]] += 1
        print("\n=== /r/%s   %s .. %s ===" % (room, lo, hi))
        shape(reply, "probe replies")
        shape(other, "non-probe control")
        all_reply.update(reply)
        all_other.update(other)

    print("\n=== pooled ===")
    shape(all_reply, "probe replies")
    shape(all_other, "non-probe control")
    v = sorted(all_reply.values(), reverse=True)
    h = collections.Counter(v)
    print("\nreplies-per-responder histogram (probe replies, pooled):")
    for k in sorted(h, reverse=True):
        if h[k] >= 3:
            print("   %5d replies : %4d keys  %s" % (k, h[k], "#" * min(h[k], 60)))
    print("\nreading: a narrow band with a spike at one or two exact counts is a shared")
    print("schedule, not a crowd. Leave-one-DID-out cannot see it, because no single key")
    print("carries the arm; the band as a whole does.")


if __name__ == "__main__":
    main()
