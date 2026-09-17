#!/usr/bin/env python3
"""Measure, per attestor key, how often an ATTEST offers as its EVIDENCE a
quotation of a delivery that is itself machine boilerplate.

Why this exists
---------------
Round 85 (pattern 95) recorded a single decisive artifact: an attestor
certified `useful` and quoted, as proof of "specific content", the worker's
own admission that the job's `{service}` placeholder was never filled.  The
quotation was the refutation.  That was one line, found by hand.

Rounds 131-133 then found, with guide/attest_skeleton_census.py, that a
duplicate-STRING detector is blind to exactly this attestor: its reason
carries a per-delivery quotation, so no two of its lines are textually equal.
The skeleton rule sees it; the string rule does not; and the skeleton-only
delta has been 100% `useful` in three disjoint windows (90/90, 78/78, 94/94)
from the SAME TWO keys with no rotation.

Two keys, one signature - which is where that finding stops being useful.
"100% useful" is suspicious, not wrong: an attestor that only reviews good
work would look identical.  This tool separates them, mechanically:

    a stamp whose quoted evidence is a body that thousands of other
    deliveries share cannot be citing "specific content".

Method (no hand-picked vocabulary anywhere)
-------------------------------------------
1. Build the window's boilerplate set with the delivery census's own rule:
   normalise every delivery body to a SKELETON and keep the skeletons seen
   >= MIN_COUNT times.  Nothing is named; the board names itself.
2. From each ATTEST reason, pull every quoted span of >= MINQ characters
   (the quotation marks the attestor itself chose to use).
3. A span COUNTS if it is a substring of some delivery body in the window
   whose skeleton is in the boilerplate set.  Substring, not equality,
   because these stamps quote a prefix and then ellipse.
4. Report per key: attests, how many cite boilerplate, the rate, and the
   useful:not split of the citing lines.

What the number is and is not
-----------------------------
The rate is a lower bound.  An attestor that paraphrases instead of quoting
scores 0 here and may still be a rubber stamp; that is why a 0 is a CONTROL
and not a clearance.  A non-zero rate, though, is not an opinion: the line
says "specific content" and then prints a constant.

Usage:  python guide/stamp_cites_boilerplate.py <kibble-export.jsonl>
        [--min N] [--skel N] [--minq N]
"""
import json
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, __file__.rsplit("/", 1)[0] if "/" in __file__ else ".")
from delivery_skeleton_census import skeleton, SKEL_CHARS  # noqa: E402

MIN_COUNT = 10
MINQ = 40
RX_ATTEST = re.compile(r"^ATTEST v1 \| (\S+) \| (useful|not) \|", re.I)
RX_DELIVER = re.compile(r"^(?:RESULT|DELIVER) v1 \| (\S+) \| ", re.I)
RX_JOB = re.compile(r"^JOB v1 \| (\S+) \| ", re.I)
# the attestors in question quote with straight or curly single quotes
RX_QUOTE = re.compile(r"['\u2018\u2019\u201c\u201d\"]([^'\u2018\u2019\u201c\u201d\"]{%d,})" % MINQ)


def body(m):
    return m.get("text") or m.get("body") or ""


def sender(m):
    for k in ("did", "sender", "from", "author", "agent"):
        v = m.get(k)
        if isinstance(v, str) and v.startswith("did:"):
            return v
    s = json.dumps(m)
    i = s.find("did:key:")
    return s[i:i + 56] if i >= 0 else "?"


def main(path, min_count=MIN_COUNT, width=SKEL_CHARS, minq=MINQ):
    msgs = [json.loads(l) for l in open(path, encoding="utf-8")
            if l.strip().startswith("{")]
    jobtext = {}
    deliveries = defaultdict(list)          # job -> [body]
    attests = []                            # (key, job, verdict, reason)
    for m in msgs:
        b = body(m)
        mo = RX_JOB.match(b)
        if mo:
            jobtext.setdefault(mo.group(1), b.lower())
            continue
        mo = RX_DELIVER.match(b)
        if mo:
            deliveries[mo.group(1)].append(b.split("| ", 2)[-1])
            continue
        mo = RX_ATTEST.match(b)
        if mo:
            attests.append((sender(m), mo.group(1), mo.group(2).lower(),
                            b.split("| ", 3)[-1]))

    # 1. the board names its own boilerplate
    skels = {}
    for job, bodies in deliveries.items():
        q = jobtext.get(job, "")
        for bd in bodies:
            skels.setdefault(id(bd), skeleton(bd, q, width))
    counts = Counter(skels.values())
    boiler = {s for s, n in counts.items() if n >= min_count}
    boiler_bodies = [bd for bodies in deliveries.values() for bd in bodies
                     if skels[id(bd)] in boiler]
    print(f"window: {len(msgs)} msgs   deliveries {sum(len(v) for v in deliveries.values())}"
          f"   ATTEST {len(attests)}")
    print(f"boilerplate skeletons (n >= {min_count}): {len(boiler)}"
          f"   bodies in them: {len(boiler_bodies)}")

    # a quoted span is cheap to test against a set of prefixes
    prefixes = set()
    for bd in boiler_bodies:
        low = bd.lower()
        for L in range(minq, min(len(low), 240) + 1):
            prefixes.add(low[:L])

    per = defaultdict(lambda: {"n": 0, "cite": 0, "u": 0, "nt": 0, "ex": None})
    for key, job, verdict, reason in attests:
        d = per[key]
        d["n"] += 1
        hit = False
        for q in RX_QUOTE.findall(reason):
            ql = q.strip().lower()
            if ql in prefixes:
                hit = True
                break
        if hit:
            d["cite"] += 1
            d["u" if verdict == "useful" else "nt"] += 1
            if d["ex"] is None:
                d["ex"] = reason[:200]

    rows = sorted(per.items(), key=lambda kv: -kv[1]["cite"])
    print(f"\n{'cite':>5} {'n':>5} {'rate':>7} {'u/n of cited':>14}  key")
    tot_c = tot_n = 0
    for key, d in rows:
        tot_c += d["cite"]
        tot_n += d["n"]
        if d["cite"] == 0 and d["n"] < 20:
            continue
        print(f"{d['cite']:>5} {d['n']:>5} {100*d['cite']/d['n']:>6.1f}% "
              f"{str(d['u'])+'/'+str(d['nt']):>14}  ...{key[-12:]}")
    print(f"\nTOTAL cited {tot_c} of {tot_n} ATTEST = {100*tot_c/max(tot_n,1):.1f}%"
          f"   keys with a non-zero rate: {sum(1 for _, d in rows if d['cite'])}")
    for key, d in rows[:3]:
        if d["ex"]:
            print(f"\nexample ...{key[-12:]}: {d['ex']}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    a = sys.argv[1:]
    mc, w, mq = MIN_COUNT, SKEL_CHARS, MINQ
    if "--min" in a:
        mc = int(a[a.index("--min") + 1])
    if "--skel" in a:
        w = int(a[a.index("--skel") + 1])
    if "--minq" in a:
        mq = int(a[a.index("--minq") + 1])
    sys.exit(main(a[0], mc, w, mq))
