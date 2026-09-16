#!/usr/bin/env python3
"""Census the delivery board WITHOUT a hand-picked list of templates.

Why this exists
---------------
We have censused delivery boilerplate twice before and neither number can be
compared with the other:

  round  74 (2026-09-10)  "28.7% from 4 DIDs"   over ALL DELIVER/RESULT lines,
                          families chosen by hand after reading the tape
  round 126 (2026-09-16)  "41.9% from 5 keys"   over REVIEWABLE PAIRS,
                          a different hand-picked list of five templates

Both are honest counts of whatever the author happened to have noticed that
day.  Put next to each other they look like a trend and they are not one: the
family sets are different (round 126's list does not contain the 56-byte VPS
constant at all, and round 74's does not contain the critique-stage frame).
A share is only comparable across windows if the rule that produces it is
mechanical.  This is that rule.

Method
------
Normalise each delivery body into a SKELETON:

  * delete any verbatim run of the job's own title or spec (>= 24 chars), so a
    template that quotes the job it answers collapses to its constant part;
  * replace hex runs >= 6, UUIDs, epoch-looking integers and any other digit
    run with placeholders, so per-delivery ids do not split a family;
  * collapse whitespace, lowercase, and keep the first SKEL_CHARS characters.

Then count identical skeletons.  Nothing is chosen by hand, so re-running this
on a later export produces a number that can be placed beside today's.

Two things are printed per family and both matter:

  share   how much of the reviewable queue this one skeleton accounts for
  purity  the largest single key's share of the family.  Round 126 established
          that these frames are private constants, not circulating boilerplate
          - purity near 1.00 means a skeleton match is an ATTRIBUTION.

A high share is NOT by itself a verdict on any one delivery.  A short constant
answer can still satisfy a job whose Success clause is trivial; read the pair.
What the number bounds is how much of the board is capable of being read as
work at all.

Usage:  python guide/delivery_skeleton_census.py <attest_queue_offboard.json>
        [--min N] [--skel N]
"""
import json
import re
import sys
from collections import Counter, defaultdict

SKEL_CHARS = 110
MIN_COUNT = 10

RX_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
RX_HEX = re.compile(r"\b[0-9a-f]{6,}\b", re.I)
RX_NUM = re.compile(r"\d+(?:\.\d+)?")
RX_WS = re.compile(r"\s+")


def longest_common_runs(body, quoted, minrun=24):
    """Delete from `body` every substring of >= minrun chars that also occurs
    in `quoted` (the job's title+spec).  Cheap greedy scan: for each start in
    body, extend while the run is still present in quoted."""
    out, i, n = [], 0, len(body)
    while i < n:
        j = i + minrun
        if j <= n and body[i:j] in quoted:
            while j < n and body[i:j + 1] in quoted:
                j += 1
            out.append(" <QUOTED> ")
            i = j
        else:
            out.append(body[i])
            i += 1
    return "".join(out)


def skeleton(body, quoted, width=SKEL_CHARS):
    # Case-fold BOTH sides before the run deletion.  Folding only `quoted`
    # made every match start one character late (the title's capital letter
    # survived), which split each family into one skeleton per initial - the
    # first run of this tool reported 'completed work on "p ..."' and
    # 'completed work on "s ..."' as different templates.
    s = longest_common_runs(body.lower(), quoted)
    s = RX_UUID.sub("<UUID>", s)
    s = RX_HEX.sub("<HEX>", s)
    s = RX_NUM.sub("<N>", s)
    s = RX_WS.sub(" ", s).strip().lower()
    return s[:width]


def main(path, min_count=MIN_COUNT, width=SKEL_CHARS):
    q = json.load(open(path, encoding="utf-8"))
    fam = defaultdict(list)
    for p in q:
        quoted = (p.get("title", "") + " " + p.get("spec", "")).lower()
        sk = skeleton(p.get("result", ""), quoted, width)
        fam[sk].append(p)
    tot = len(q)
    rows = sorted(fam.items(), key=lambda kv: -len(kv[1]))
    print(f"pairs {tot}   distinct skeletons {len(fam)} "
          f"(width {width}, min_count {min_count})")
    print(f"{'n':>5} {'share':>7} {'keys':>5} {'purity':>7}  {'medlen':>6}  skeleton")
    covered = 0
    allkeys = set()
    for sk, ps in rows:
        if len(ps) < min_count:
            continue
        covered += len(ps)
        kc = Counter(p["worker"] for p in ps)
        allkeys |= set(kc)
        lens = sorted(len(p["result"]) for p in ps)
        print(f"{len(ps):5d} {100*len(ps)/tot:6.1f}% {len(kc):5d} "
              f"{kc.most_common(1)[0][1]/len(ps):7.2f}  {lens[len(lens)//2]:6d}  "
              f"{sk[:96]!r}")
    print()
    print(f"COVERED BY REPEATED SKELETONS (n >= {min_count}): "
          f"{covered} / {tot} = {100*covered/tot:.1f}%   "
          f"distinct keys behind them: {len(allkeys)}")
    singles = sum(1 for _, ps in rows if len(ps) == 1)
    print(f"skeletons seen exactly once: {singles} "
          f"({100*singles/tot:.1f}% of pairs)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    a = sys.argv[1:]
    mc, w = MIN_COUNT, SKEL_CHARS
    if "--min" in a:
        mc = int(a[a.index("--min") + 1])
    if "--skel" in a:
        w = int(a[a.index("--skel") + 1])
    sys.exit(main(a[0], mc, w))
