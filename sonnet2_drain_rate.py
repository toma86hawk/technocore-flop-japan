#!/usr/bin/env python3
"""How fast is the sonnet-2 identity index actually draining?

Rounds 119-126 measured the backlog with SNAPSHOTS: publication lag quantiles,
and a "drain frontier" taken as the newest first_seen among the last N
published entries.  Two weaknesses in that:

  * the trailing-N frontier is a MAX, so one out-of-order entry moves it and it
    says nothing about the bulk;
  * a snapshot cannot answer the question that actually decides eligibility at
    D, which is a RATE: is the drain catching up, holding, or falling behind?

Because the room's floor has been pinned at seq 7411 since 2026-09-16T00:21Z,
two exports taken hours apart share a floor, so the entries present in the
later one and absent from the earlier are EXACTLY what the drain emitted in
between.  That increment - not a trailing window - is the thing to measure.

For each increment this prints the admission-time (first_seen) distribution of
what was emitted, and the advance of that distribution per wall-clock hour.

  advance rate < 1.0  ->  the index is falling further behind real time
  advance rate > 1.0  ->  it is catching up, and the catch-up date is printable

Usage:  python guide/sonnet2_drain_rate.py <older export> [more] <newest export>
        (order does not matter; they are sorted by head seq)
"""
import json
import sys
from datetime import datetime, timezone

CUTOFF = datetime(2026, 9, 11, 12, 0, 0, tzinfo=timezone.utc)
D = datetime(2026, 9, 18, 12, 0, 0, tzinfo=timezone.utc)
LATE = datetime(2026, 9, 10, 0, 0, 0, tzinfo=timezone.utc)
NEAR = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)


def ts(s):
    return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def iso(u):
    """first_seen is epoch seconds (float) in every frame measured - never a string."""
    return datetime.fromtimestamp(u, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z"


def dt(u):
    return datetime.fromtimestamp(u, timezone.utc)


def load(path):
    """-> (floor_seq, head_seq, head_ts, {seq: [first_seen, ...]})"""
    floor = head = head_ts = None
    per = {}
    for line in open(path, "rb"):
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
            b = json.loads(o["text"])
        except Exception:
            continue
        if floor is None:
            floor = o.get("seq")
        head, head_ts = o.get("seq"), o.get("ts")
        if b.get("type") != "sonnet.identities.v1":
            continue
        fs = [e["first_seen"] for e in (b.get("additions") or {}).values()
              if e.get("first_seen")]
        if fs:
            per[o["seq"]] = fs
    return floor, head, head_ts, per


def quant(vals, p):
    return vals[min(len(vals) - 1, int(p * len(vals)))]


def main(paths):
    snaps = []
    for p in paths:
        floor, head, head_ts, per = load(p)
        snaps.append((head, head_ts, floor, per, p))
    snaps.sort(key=lambda s: s[0])

    floors = set(s[2] for s in snaps)
    print("floors seen: %s" % sorted(floors))
    if len(floors) > 1:
        print("  !! floors DIFFER - the room trimmed between these exports, so the")
        print("     increment below is contaminated by the trim.  Report, do not hide.")
    print()

    prev = None
    rates = []
    for head, head_ts, floor, per, path in snaps:
        if prev is None:
            print("base   head seq %-7s ts %s   frames %d" % (head, head_ts, len(per)))
            prev = (head, head_ts, per)
            continue
        phead, phead_ts, pper = prev
        new = {s: v for s, v in per.items() if s > phead}
        fs = sorted(x for v in new.values() for x in v)
        wall = (ts(head_ts) - ts(phead_ts)).total_seconds() / 3600.0
        print()
        print("increment seq %s..%s   published %s -> %s   (%.2f wall hours)"
              % (phead + 1, head, phead_ts[:19], head_ts[:19], wall))
        print("  frames %d   entries emitted %d   (%.0f entries/hour)"
              % (len(new), len(fs), len(fs) / wall if wall else 0))
        if not fs:
            prev = (head, head_ts, per)
            continue
        print("  admission time of what was emitted:")
        print("     min %s   p25 %s" % (iso(fs[0]), iso(quant(fs, .25))))
        print("     MED %s   p75 %s" % (iso(quant(fs, .50)), iso(quant(fs, .75))))
        print("     p95 %s   max %s" % (iso(quant(fs, .95)), iso(fs[-1])))
        # The bulk median is not the whole story: the drain is NOT strictly
        # ordered, so a near-cutoff admission can surface inside an increment
        # whose median is two weeks older.  Count them explicitly.
        late = [x for x in fs if dt(x) >= LATE]
        near = [x for x in fs if dt(x) >= NEAR]
        print("  emitted with first_seen >= %s: %d (%.3f%%)"
              % (LATE.strftime("%Y-%m-%d"), len(late), 100.0 * len(late) / len(fs)))
        print("  emitted with first_seen >= %s (last 24h before cutoff): %d (%.3f%%)"
              % (NEAR.strftime("%Y-%m-%d"), len(near), 100.0 * len(near) / len(fs)))
        prev_med = getattr(main, "_prev_med", None)
        med = dt(quant(fs, .50))
        mx = dt(fs[-1])
        prev_max = getattr(main, "_prev_max", None)
        if prev_med is not None and wall:
            dm = (med - prev_med).total_seconds() / 3600.0
            dx = (mx - prev_max).total_seconds() / 3600.0
            print("  ADVANCE vs previous increment: median %+.2f h, max %+.2f h"
                  % (dm, dx))
            print("  advance rate: median %.3fx real time, max %.3fx"
                  % (dm / wall, dx / wall))
            rates.append((dm / wall, dx / wall, med, mx, ts(head_ts)))
        main._prev_med, main._prev_max = med, mx
        prev = (head, head_ts, per)

    print()
    if not rates:
        print("need at least three exports to state a rate (two increments).")
        return 0
    dm, dx, med, mx, at = rates[-1]
    left = (D - at).total_seconds() / 3600.0
    print("LATEST RATE -> what it implies at D %s (%.1f h away)"
          % (D.strftime("%Y-%m-%dT%H:%M:%SZ"), left))
    for label, rate, now in (("median", dm, med), ("max", dx, mx)):
        gap = (CUTOFF - now).total_seconds() / 3600.0
        print("  %s emission is %.1f h (%.2f d) short of the identity cutoff"
              % (label, gap, gap / 24))
        if rate <= 1.0:
            print("     advancing at %.3fx real time: the gap is NOT closing" % rate)
        if rate > 0:
            need = gap / rate
            print("     at this rate it reaches the cutoff in %.0f h (%.1f d), %s D"
                  % (need, need / 24, "BEFORE" if need < left else "AFTER"))
        else:
            print("     rate is <= 0: it is moving backwards or not at all")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1:]))
