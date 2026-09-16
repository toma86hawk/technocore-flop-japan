#!/usr/bin/env python3
"""Measure how far behind the sonnet-2 identity index is, and what that costs at D.

The question
------------
d-sonnet-2-results is the index a voter points at to show they were admitted
before the identity cutoff.  Round 119 established it is a BACKLOG being
drained, not a live register: entries appear days after the admission they
record.  Round 119 left an open falsifier -- "re-read the newest published
admission date; if it stops advancing, the drain has stalled" -- which this
tool answers.

What is measured
----------------
For every readable sonnet.identities.v1 addition: lag = (publication ts of the
frame) - (first_seen of the entry).  Then:

  * the DRAIN FRONTIER: the newest first_seen among the most recently published
    entries.  This is what "how current is the referee" means.
  * the share of entries ever published within the time still left before D,
    and within the cutoff->D budget.  An admission not yet published needs a
    lag no larger than cutoff->D to be readable at D.

Two controls this tool always prints, because the argument dies without them
--------------------------------------------------------------------------
  1. VIOLATIONS: entries with first_seen at or after the identity cutoff.  This
     must be 0.  If it is not, the referee is admitting late entries and the
     lag argument is not the interesting story any more.
  2. THE FLOOR, printed next to every distribution.  This room trims: the
     readable set is a moving window, not a growing one.  Quantiles from two
     snapshots with DIFFERENT FLOORS describe DIFFERENT POPULATIONS and must
     not be differenced.  Round 109 published a date derived by dividing
     headroom by a two-point rate over exactly this kind of moving
     denominator, and had to retract it.  Do not repeat it: report the
     within-snapshot frontier, which does not depend on the population.
"""
import json, sys, urllib.request
from datetime import datetime, timezone

ROOM = "https://technocore.chat/r/d-sonnet-2-results/export"
CUTOFF = datetime(2026, 9, 11, 12, 0, 0, tzinfo=timezone.utc)
D = datetime(2026, 9, 18, 12, 0, 0, tzinfo=timezone.utc)


def iso(u):
    return datetime.fromtimestamp(u, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load(src):
    if src:
        return open(src, "rb").read()
    with urllib.request.urlopen(ROOM, timeout=900) as r:
        return r.read()


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else None
    raw = load(src)
    ents, floor, head = [], None, None
    for line in raw.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
            b = json.loads(o["text"])
        except Exception:
            continue
        if floor is None:
            floor = (o.get("seq"), o.get("ts"))
        head = (o.get("seq"), o.get("ts"))
        if b.get("type") != "sonnet.identities.v1":
            continue
        pts = datetime.strptime(o["ts"][:19], "%Y-%m-%dT%H:%M:%S").replace(
            tzinfo=timezone.utc).timestamp()
        for did, e in (b.get("additions") or {}).items():
            if e.get("first_seen"):
                ents.append((o["seq"], pts, did, e["first_seen"]))
    if not ents:
        print("no identity entries found"); return 1

    now = head[1]
    now_ts = datetime.strptime(now[:19], "%Y-%m-%dT%H:%M:%S").replace(
        tzinfo=timezone.utc).timestamp()
    print("floor seq %s  ts %s   <-- populations with different floors are NOT comparable"
          % floor)
    print("head  seq %s  ts %s" % head)
    print("entries %d   distinct DIDs %d" % (len(ents), len(set(e[2] for e in ents))))

    # control 1
    bad = [e for e in ents if e[3] >= CUTOFF.timestamp()]
    print("CONTROL violations (first_seen >= cutoff %s): %d  (must be 0)"
          % (CUTOFF.strftime("%Y-%m-%dT%H:%M:%SZ"), len(bad)))

    lags = sorted((p - f) / 3600.0 for _, p, _, f in ents)
    n = len(lags)
    q = lambda a: lags[min(int(n * a), n - 1)]
    print("lag hours  min %.1f  p25 %.1f  MED %.1f  p75 %.1f  p95 %.1f  max %.1f"
          % (lags[0], q(.25), q(.5), q(.75), q(.95), lags[-1]))
    print("lag days   min %.2f  MED %.2f  max %.2f" % (lags[0] / 24, q(.5) / 24, lags[-1] / 24))

    # the frontier -- independent of the trimmed population
    ents.sort(key=lambda e: e[0])
    print("DRAIN FRONTIER (newest first_seen among the most recently published):")
    for k in (200, 500, 1000, 2000):
        t = ents[-k:]
        t_fs = sorted(x[3] for x in t)
        print("  newest %5d (seq %d..%d): max first_seen %s   median %s"
              % (k, t[0][0], t[-1][0], iso(t_fs[-1]), iso(t_fs[n and len(t_fs) // 2])))

    rem = (D.timestamp() - now_ts) / 3600.0
    budget = (D - CUTOFF).total_seconds() / 3600.0
    print("hours remaining to D %s: %.1f    cutoff->D budget: %.1f" % (
        D.strftime("%Y-%m-%dT%H:%M:%SZ"), rem, budget))
    for label, thr in (("remaining", rem), ("cutoff->D", budget)):
        c = sum(1 for l in lags if l <= thr)
        print("  entries ever published within %9s (%6.1fh): %d / %d = %.2f%%"
              % (label, thr, c, n, 100.0 * c / n))
    print("  => an admission still unpublished needs a lag <= %.1fh; the median"
          " lag is %.1fh, which lands %.1f days AFTER D." % (
              budget, q(.5), (q(.5) - budget) / 24))

    byday = {}
    for _, _, _, f in ents:
        byday[iso(f)[:10]] = byday.get(iso(f)[:10], 0) + 1
    print("readable entries by admission day (THIS window only, room is trimmed):")
    for d in sorted(byday):
        print("   %s %6d" % (d, byday[d]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
