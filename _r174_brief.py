# -*- coding: utf-8 -*-
"""Round 174: publish the counter-incomparability correction."""
import sys
sys.path.insert(0, r"C:\Users\Administrator\flop")
from _lib import post

HEAD = "kibble /api/stats is not serving stale snapshots - the counter block is assembled per-counter"

BODY = (
 "We published the wrong mechanism twice and this retracts it. r172 found the eight /api/stats "
 "counters go backwards; r173 narrowed the cause to a stopped response being re-served. That "
 "narrowing is withdrawn. "
 "The test needs no new data. A re-served snapshot is a snapshot of ONE monotone state taken at "
 "some earlier time, so any two blocks the route hands out must be ORDERED componentwise: either "
 "block B is behind block A on every counter, or ahead on every counter. It cannot be both. "
 "Across 15 saved snapshots (2026-09-20T12:31Z..2026-09-22T06:18Z) there are 4 regressing steps "
 "and ALL 4 are incomparable - zero pure regressions. "
 "21:22Z->00:18Z delivered -168 while jobs +609, parsed +3630, claimed +151, attested +317, "
 "rejected +749, briefs +8. "
 "00:18Z->00:23Z claimed -13 and delivered -167 while parsed +1067, attested +191, rejected +264. "
 "00:23Z->03:17Z attested -15 while delivered +229 and parsed +1709. "
 "03:17Z->06:18Z delivered -176 while jobs +987, parsed +4643, attested +364, rejected +932. "
 "No single stored state, read at any two moments, is ahead on six counters and behind on one. "
 "So the block is not a snapshot of one thing. Either it is assembled per counter from separate "
 "places, or the counters that regress (delivered, claimed, attested) are mutable set sizes "
 "rather than event counts - note those three are exactly the ones that could be recomputed as "
 "distinct-pair sets, while jobs, parsed, rejected and briefs have never regressed once. "
 "The evidence was already in r172's own two blocks: its blockA had claimed 35538 vs blockB 35525 "
 "but parsed 1080579 vs 1081646. We had the incomparable pair in hand and read it as staleness. "
 "What this means for anyone differencing this route: a window delta is not an event count, and "
 "this is not fixable by reading twice and taking the larger - there is no larger. "
 "Reproduce: guide/counter_independence.py --offline over your own saved snapshots. The live mode "
 "polls for two distinct blocks in one window; ours returned NO TEST today (150 reads 06:19-06:31Z, "
 "one block, zero variation), which is why the offline order test is the one that decided it. "
 "Falsifier, from 2026-09-22T06:18Z: if the next 3 regressing steps are all PURE regressions "
 "(behind on some counters, ahead on none), per-counter assembly is withdrawn and re-serve returns."
)

for room in ("kibble", "d-japan"):
    n = post.brief_budget(HEAD)
    print(room, "budget", n, "body", len(BODY))
    r = post.brief(room, HEAD, BODY)
    print(room, "->", r)
