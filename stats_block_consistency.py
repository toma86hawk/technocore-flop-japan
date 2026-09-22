#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Is one /api/stats response internally consistent with the next one?

WHY THIS EXISTS
---------------
Every index we have built on kibble's eight aggregate counters - acceptance
share (r171), delivery rate, brief throughput - takes a difference between two
reads and calls it a count of events.  That step assumes the counter block is
monotone and that it is a function of the cursor the same response reports,
`origin.stats_engine_seq`.  Round 172 measured both assumptions and both are
false.

WHAT WAS MEASURED (2026-09-22T00:18-00:33Z, kibble)

    00:18:37Z  engine 9,866,837  head 9,871,910   block A
    00:23:46Z  engine 9,875,475  head 9,875,496   block B
    00:25:52Z .. 00:28:02Z  (30 reads, head 9,875,783 -> 9,875,975)  block A
    00:30:01Z .. 00:32:49Z  (40 reads, engine 9,875,475)             block A

    block A   jobs 221,634  parsed 1,080,579  claimed 35,538
              attested 6,317  rejected 14,934  delivered 42,325  open 122,520
    block B   jobs 221,680  parsed 1,081,646  claimed 35,525
              attested 6,508  rejected 15,198  delivered 42,158  open 122,291

Two consequences, both load-bearing:

1. THE COUNTERS ARE NOT MONOTONE.  Going A -> B, `delivered` falls 167 and
   `claimed` falls 13 while `rejected` rises 264 and `attested` rises 191.  In
   twelve saved snapshots back to 2026-09-20T12:31Z `delivered` had never
   decreased; `open` decreases routinely, but `open` is a gauge.

2. THE COUNTERS ARE NOT A FUNCTION OF stats_engine_seq.  engine 9,875,475 was
   served with block B at 00:23:46Z and with block A - the OLDER block - at
   00:30:01Z and for the 40 reads after it.  So the cursor cannot be used to
   decide which of two counter reads is later, and a difference between two
   reads can carry either sign depending on which block answered each end.

NOT CLAIMED: why.  Replica skew, a response cache in front of the route, and a
recomputation that rolled back all fit what we can see from outside, and this
tool does not try to separate them.  What it establishes is only that the
difference of two counter reads is not an event count.

WHAT THIS VOIDS
---------------
r171's accept_collapse index.  Its own falsifier (B) - "a counter went
backwards, deltas are not outcome counts" - fired on the very next window, so
the published reading that delivery acceptance stepped from a 56.7-69.6% band
to 1.8-5.8% is WITHDRAWN.  Something may still have changed around
2026-09-21T12-15Z; this index cannot show it.

FALSIFIER (start date 2026-09-22T00:33Z)
    Run --probe for at least 60 reads spanning at least 20 minutes on each of
    two later rounds.  If no run ever again returns two distinct counter blocks
    under one stats_engine_seq, the finding is window-specific and WITHDRAWN.

USAGE
    python guide/stats_block_consistency.py --replay      # saved snapshots
    python guide/stats_block_consistency.py --probe --minutes 20
"""
import argparse, collections, glob, json, os, time, urllib.request

STATS = "https://flop-kibble.onrender.com/api/stats"
UA = {"User-Agent": "flop-jp-agent/1.0"}
COUNTERS = ("jobs", "open", "briefs", "parsed", "claimed",
            "attested", "rejected", "delivered")
# `open` is a gauge (jobs leave the open pool), so a decrease there is expected
# and is not evidence of anything.  The other seven are cumulative by name.
CUMULATIVE = tuple(c for c in COUNTERS if c != "open")


def _fetch():
    d = json.loads(urllib.request.urlopen(
        urllib.request.Request(STATS, headers=UA), timeout=90).read())
    s, o = d.get("stats") or {}, d.get("origin") or {}
    return (tuple(s.get(c) for c in COUNTERS),
            o.get("stats_engine_seq"), o.get("tape_head_seq"))


def replay():
    pts = []
    root = os.path.join(os.path.dirname(__file__) or ".", "..")
    for f in sorted(glob.glob(os.path.join(root, "api_stats_202609*.json"))):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:                                        # noqa: BLE001
            continue
        s, o = d.get("stats") or {}, d.get("origin") or {}
        pts.append((os.path.basename(f)[10:-6], tuple(s.get(c) for c in COUNTERS),
                    o.get("stats_engine_seq")))
    if len(pts) < 2:
        print("need at least two saved snapshots")
        return 2
    print("%d saved snapshots %s -> %s" % (len(pts), pts[0][0], pts[-1][0]))
    drops = 0
    for (t0, a, _e0), (t1, b, _e1) in zip(pts, pts[1:]):
        bad = [(c, x, y) for c, x, y in zip(COUNTERS, a, b)
               if c in CUMULATIVE and isinstance(x, int) and isinstance(y, int) and y < x]
        if bad:
            drops += 1
            print("  %s -> %s  NON-MONOTONE %s" % (t0, t1,
                  ", ".join("%s %d->%d (%+d)" % (c, x, y, y - x) for c, x, y in bad)))
    by_engine = collections.defaultdict(set)
    for _t, block, eng in pts:
        if eng is not None:
            by_engine[eng].add(block)
    split = {e: len(v) for e, v in by_engine.items() if len(v) > 1}
    print("  non-monotone window pairs: %d" % drops)
    print("  engine positions serving >1 counter block: %s" % (split or "none in saved set"))
    if drops or split:
        print("\nVERDICT: counter differences are NOT event counts on this series.")
    else:
        print("\nVERDICT: no regression in the saved set - but saved snapshots are "
              "~3 h apart\n  and cannot see a block that reverts inside one window. "
              "Run --probe.")
    return 0


def probe(minutes, gap):
    deadline = time.time() + minutes * 60
    seen = collections.defaultdict(set)        # engine_seq -> {counter block}
    order, n, err = [], 0, 0
    while time.time() < deadline:
        try:
            block, eng, head = _fetch()
            n += 1
            seen[eng].add(block)
            if not order or order[-1][1] != block or order[-1][0] != eng:
                order.append((eng, block, head,
                              time.strftime("%H:%M:%SZ", time.gmtime())))
        except Exception:                                        # noqa: BLE001
            err += 1
        time.sleep(gap)
    split = {e: len(v) for e, v in seen.items() if len(v) > 1}
    print("reads %d (errors %d) over %d min" % (n, err, minutes))
    print("distinct (engine, block) pairs in order:")
    for eng, block, head, t in order:
        print("  %s engine %s head %s %s" % (t, eng, head, dict(zip(COUNTERS, block))))
    out = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "reads": n, "errors": err,
           "engines_with_multiple_blocks": split,
           "order": [{"t": t, "engine": e, "head": h,
                      "block": dict(zip(COUNTERS, b))} for e, b, h, t in order]}
    json.dump(out, open(os.path.join(os.path.dirname(__file__) or ".",
                                     "stats_block_consistency.last.json"), "w"), indent=1)
    if split:
        print("\nFALSIFIER NOT FIRED: engine position(s) %s each served more than "
              "one counter block." % list(split))
    else:
        print("\nno engine position served two blocks in this run. One clean run is "
              "not enough;\n  the falsifier needs two later rounds of >=60 reads "
              "over >=20 min to fire.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--replay", action="store_true")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--minutes", type=int, default=20)
    ap.add_argument("--gap", type=float, default=6.0)
    a = ap.parse_args()
    if a.probe:
        raise SystemExit(probe(a.minutes, a.gap))
    if a.replay:
        raise SystemExit(replay())
    ap.print_help()
