#!/usr/bin/env python3
"""
counter_independence.py  (round 174)

WHAT THIS DECIDES
-----------------
r173 narrowed the /api/stats counter regressions to "a stopped response being
re-served rather than a rollback".  That mechanism makes a hard prediction:

    every block the route hands out is a SNAPSHOT of one monotone state,
    taken at some time t.  Two such snapshots, whatever their ages, must be
    COMPARABLE: for blocks A and B, either A <= B on every counter, or
    B <= A on every counter.  A set of snapshots of a monotone process is a
    CHAIN under the componentwise order.

So the falsifier of "whole-block re-serve" is an INCOMPARABLE PAIR:
two blocks A, B and two counters i, j with A[i] > B[i] and A[j] < B[j].
No single monotone state, sampled at any two times, can produce that.
An incomparable pair means the block is ASSEMBLED PER-COUNTER (different
counters answered from different places), or some counter is not an event
count at all.

WINDOW.  Registered start: the poll's own first read.  This is a
within-window test only - it says nothing about counters across rounds.

NO-TEST CASE.  If the poll sees only one distinct block, the instrument did
not deploy: report NO TEST, not "no effect".  (r173's rule.)
"""
import json, sys, time, urllib.request, hashlib
from datetime import datetime, timezone

URL = "https://flop-kibble.onrender.com/api/stats"
KEYS = ["jobs", "parsed", "claimed", "attested", "rejected", "delivered", "briefs"]
CURSOR = ["stats_engine_seq", "engine_seq", "head", "tape_head"]


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def pick(d, names):
    for n in names:
        if isinstance(d.get(n), int):
            return n, d[n]
    return None, None


def read():
    req = urllib.request.Request(URL, headers={"User-Agent": "flop-japan-counter-independence/1"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode())


def flatten(d):
    out = {}
    for k in KEYS:
        v = d.get(k)
        if isinstance(v, int):
            out[k] = v
    # counters sometimes live one level down
    for sub in ("counters", "stats", "totals"):
        s = d.get(sub)
        if isinstance(s, dict):
            for k in KEYS:
                if k not in out and isinstance(s.get(k), int):
                    out[k] = s[k]
    return out


def compare(a, b, keys):
    """return 'le', 'ge', 'eq', or the (i,j) witness of incomparability"""
    lt = [k for k in keys if a[k] < b[k]]
    gt = [k for k in keys if a[k] > b[k]]
    if lt and gt:
        return ("incomparable", gt[0], lt[0])
    if lt:
        return ("le", None, None)
    if gt:
        return ("ge", None, None)
    return ("eq", None, None)


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 140
    gap = float(sys.argv[2]) if len(sys.argv) > 2 else 4.5
    out = sys.argv[3] if len(sys.argv) > 3 else "guide/_r174_independence.json"

    started = now()
    blocks = {}          # digest -> {"counters":..., "cursor":..., "n":, "first":, "last":}
    order = []
    errors = 0
    cursor_key = None

    for i in range(n):
        try:
            d = read()
        except Exception:
            errors += 1
            time.sleep(gap)
            continue
        c = flatten(d)
        if not c:
            errors += 1
            time.sleep(gap)
            continue
        ck, cv = pick(d, CURSOR)
        if ck and not cursor_key:
            cursor_key = ck
        dig = hashlib.sha256(json.dumps(c, sort_keys=True).encode()).hexdigest()[:10]
        if dig not in blocks:
            blocks[dig] = {"counters": c, "cursors": [cv], "n": 1, "first": now(), "last": now()}
            order.append(dig)
        else:
            b = blocks[dig]
            b["n"] += 1
            b["last"] = now()
            if cv is not None and cv not in b["cursors"]:
                b["cursors"].append(cv)
        time.sleep(gap)

    ended = now()
    keys = sorted(set.intersection(*[set(b["counters"]) for b in blocks.values()])) if blocks else []

    result = {
        "tool": "guide/counter_independence.py",
        "window": [started, ended],
        "reads": n,
        "errors": errors,
        "cursor_key": cursor_key,
        "distinct_blocks": len(blocks),
        "counters_compared": keys,
        "blocks": [
            {"digest": d, "seen": blocks[d]["n"], "first": blocks[d]["first"],
             "last": blocks[d]["last"], "cursors": blocks[d]["cursors"],
             "counters": blocks[d]["counters"]}
            for d in order
        ],
    }

    if len(blocks) < 2:
        result["verdict"] = "NO TEST - the route handed out a single block for the whole window. The instrument did not deploy; this is not evidence either way."
        result["incomparable_pairs"] = []
    else:
        pairs = []
        ds = list(order)
        for a in range(len(ds)):
            for b in range(a + 1, len(ds)):
                kind, up, down = compare(blocks[ds[a]]["counters"], blocks[ds[b]]["counters"], keys)
                if kind == "incomparable":
                    A, B = blocks[ds[a]]["counters"], blocks[ds[b]]["counters"]
                    pairs.append({
                        "a": ds[a], "b": ds[b],
                        "a_higher_on": {up: [A[up], B[up]]},
                        "b_higher_on": {down: [A[down], B[down]]},
                        "a_first": blocks[ds[a]]["first"], "b_first": blocks[ds[b]]["first"],
                    })
        result["incomparable_pairs"] = pairs
        if pairs:
            result["verdict"] = (
                "WHOLE-BLOCK RE-SERVE IS REFUTED AS A COMPLETE EXPLANATION. %d of the %d "
                "distinct blocks form at least one incomparable pair: one block is ahead on "
                "one counter and behind on another. No snapshot of a single monotone state, "
                "taken at any two times, can do that. The block is assembled per-counter."
                % (len(set([p['a'] for p in pairs] + [p['b'] for p in pairs])), len(blocks))
            )
        else:
            result["verdict"] = (
                "CHAIN. All %d distinct blocks are totally ordered componentwise - exactly what "
                "re-serving stopped snapshots of one monotone state predicts. r173's mechanism "
                "survives this window." % len(blocks)
            )

    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    print(json.dumps({k: v for k, v in result.items() if k != "blocks"}, indent=1))
    print("blocks:")
    for b in result["blocks"]:
        print(" ", b["digest"], "x%-4d" % b["seen"], b["first"], "cursors", b["cursors"][:3],
              {k: b["counters"].get(k) for k in keys})
    print("->", out)


if __name__ == "__main__" and "--offline" not in sys.argv:
    main()


# ---------------------------------------------------------------------------
# OFFLINE MODE  (added in round 174, after the live poll returned NO TEST)
#
# The live poll needs the route to hand out two different blocks inside one
# window, and on 2026-09-22T06:19-06:31Z it handed out exactly one across 150
# reads.  But the same test does not need a live poll: the saved
# api_stats_*.json series is already a set of blocks the route handed out, and
# the componentwise order argument applies to any two of them.
#
#   run:  python guide/counter_independence.py --offline
# ---------------------------------------------------------------------------
import glob as _glob, re as _re

OFF_KEYS = ["jobs", "parsed", "claimed", "attested", "rejected", "delivered", "briefs"]
# `open` is excluded: it is a gauge, jobs legitimately leave the open pool.
# `agents` is excluded: it is a set size, not a cumulative count.


def offline(pattern="api_stats_*.json", out="guide/_r174_independence_offline.json"):
    rows = []
    skipped = []
    for f in sorted(_glob.glob(pattern)):
        m = _re.search(r"(\d{8}T\d{6}Z)", f)
        if not m:
            skipped.append(f)
            continue
        s = json.load(open(f, encoding="utf-8")).get("stats", {})
        if all(k in s for k in OFF_KEYS):
            rows.append((m.group(1), {k: s[k] for k in OFF_KEYS}, f))
    rows.sort()

    steps = []
    for i in range(len(rows) - 1):
        a, A, fa = rows[i]
        b, B, fb = rows[i + 1]
        up = [k for k in OFF_KEYS if B[k] > A[k]]
        dn = [k for k in OFF_KEYS if B[k] < A[k]]
        if not dn:
            continue
        steps.append({
            "from": a, "to": b,
            "down": {k: [A[k], B[k]] for k in dn},
            "up": {k: B[k] - A[k] for k in up},
            "kind": "INCOMPARABLE" if up else "pure regression",
        })

    inc = [s for s in steps if s["kind"] == "INCOMPARABLE"]
    pure = [s for s in steps if s["kind"] == "pure regression"]

    res = {
        "tool": "guide/counter_independence.py --offline",
        "snapshots": len(rows),
        "span": [rows[0][0], rows[-1][0]] if rows else None,
        "skipped_unparsable_filenames": skipped,
        "counters": OFF_KEYS,
        "regressing_steps": len(steps),
        "incomparable": len(inc),
        "pure_regressions": len(pure),
        "steps": steps,
    }

    if not steps:
        res["verdict"] = "NO TEST - no regressing step in the saved series, so there is nothing to order."
    elif pure and not inc:
        res["verdict"] = (
            "CHAIN. Every regressing step is a pure regression: the later block is behind on "
            "some counters and ahead on none. That is exactly what re-serving a stopped "
            "snapshot of one monotone state looks like. r173's mechanism survives."
        )
    else:
        res["verdict"] = (
            "WHOLE-BLOCK RE-SERVE IS REFUTED AS THE MECHANISM OF THE REGRESSIONS. %d of %d "
            "regressing steps are INCOMPARABLE - the later block is ahead on some counters and "
            "behind on others in the same step. A snapshot of one monotone state, taken at any "
            "two times, is ordered: it cannot be ahead on six counters and behind on one. So "
            "the block is not a snapshot; it is assembled per-counter, or the counters that go "
            "backwards are not event counts. r173 narrowed the mechanism to 'a stopped response "
            "being re-served' and that narrowing is WITHDRAWN."
            % (len(inc), len(steps))
        )

    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "steps"}, indent=1))
    for s in res["steps"]:
        print("\n%s -> %s   [%s]" % (s["from"], s["to"], s["kind"]))
        print("   DOWN:", {k: "%d->%d (%+d)" % (v[0], v[1], v[1] - v[0]) for k, v in s["down"].items()})
        print("   UP  :", {k: "+%d" % v for k, v in s["up"].items()})
    print("\n->", out)
    return res


if __name__ == "__main__" and "--offline" in sys.argv:
    offline()
