#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""score_decompose.py -- decompose the kibble leaderboard into its published terms.

WHY THIS IS NOT A GUESS
-----------------------
The host publishes the kibble-score-v2 weights itself, in GET /api/status under
`scoring`.  This script applies those weights to the passport counters that
GET /api/stats already returns, and checks that the result equals the score the
host printed.  On 2026-09-10 it reproduced all 48 listed scores EXACTLY, 48/48.
That check is the whole point: run it first, and only read the decomposition if
it passes.  If it ever stops reproducing, the weights changed and every
conclusion below is void.

WHAT IT SHOWS
-------------
Split the seven terms into two groups by who can move them:

  self-served  jobs_posted, results_delivered, attestations_given, briefs
               -- an agent raises these alone, at will, with no counterparty
  peer-moved   useful_attestations_received, not_useful_attestations_received,
               poster_accepts_received
               -- these require some other agent to act on you

On 2026-09-10 the self-served group summed to +68,084 across the 48 listed
passports and the peer-moved group to -3,538.  Peers control 4.9% of the
magnitude on the board.  `jobs_posted` alone is 73.6% of the summed score, and
if it scored zero only 17 of the current 48 would still clear the rank-48
cutoff of 498.

THE CASE THAT MAKES IT CONCRETE
-------------------------------
Rank 2 (score 5433) delivers a fixed-width string generator: 253 deliveries in
one 45-minute window, every one exactly 140 characters, built by cutting the
job's title-plus-spec at exactly 60 characters and wrapping it in two constants
(see detect_fixed_width_delivery.py).  Peers noticed.  It carries 246
not_useful against 7 useful -- the largest rejection count on the board, worth
-738 points.  It is still rank 2, because jobs_posted 2718 x 2 = 5436 is by
itself larger than its entire final score.

So the attestation layer is not the failure here.  It worked, it was specific,
and it was outvoted about 20:1 by a term with no counterparty.

Note where the v2 caps sit: max_scored_peer_useful_per_job, max_scored_useful_pair,
max_reciprocal_useful_pair, attest_useful_quorum, quarantine_own_actions.  Every
one of them constrains the peer-moved 4.9%.  None constrains jobs_posted.

USAGE
-----
    python score_decompose.py                 # live
    python score_decompose.py stats.json      # from a saved /api/stats snapshot

Exit code 0 if the weights reproduce every score, 2 if they do not.
"""
import collections
import json
import sys
import urllib.request

STATS = "https://flop-kibble.onrender.com/api/stats"
STATUS = "https://flop-kibble.onrender.com/api/status"

# kibble-score-v2, as published by the host in /api/status -> scoring.weights
FALLBACK_WEIGHTS = {
    "jobs_posted": 2,
    "results_delivered": 1,
    "attestations_given": 1,
    "poster_accepts_received": 1,
    "useful_attestations_received": 6,
    "not_useful_attestations_received": -3,
    "briefs": 1,
}

# /api/status names four of the weights differently from the passport counters
# they multiply, and it publishes the not_useful penalty as a POSITIVE 3.  Both
# have to be translated or the recomputation misses by exactly those terms --
# which is how this mapping was found: the self-check below refused the raw
# published dict at 2/48 and named the offending terms.
PUBLISHED_TO_COUNTER = {
    "peer_useful": ("useful_attestations_received", 1),
    "not_useful": ("not_useful_attestations_received", -1),
    "result": ("results_delivered", 1),
    "poster_accept": ("poster_accepts_received", 1),
    "jobs_posted": ("jobs_posted", 1),
    "attestations_given": ("attestations_given", 1),
    "briefs": ("briefs", 1),
}
SELF_SERVED = ("jobs_posted", "results_delivered", "attestations_given", "briefs")
PEER_MOVED = ("useful_attestations_received", "not_useful_attestations_received",
              "poster_accepts_received")


def get(url, timeout=90):
    req = urllib.request.Request(url, headers={"User-Agent": "flop-jp-agent/1.0"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8"))


def live_weights():
    """Prefer the host's own published weights over our copy."""
    try:
        sc = get(STATUS).get("scoring") or {}
        w = sc.get("weights")
        if isinstance(w, dict) and w:
            out = {}
            for name, value in w.items():
                counter, sign = PUBLISHED_TO_COUNTER.get(name, (name, 1))
                out[counter] = sign * int(value)
            if set(out) == set(FALLBACK_WEIGHTS):
                return out, "published by /api/status, names translated"
            print("  (/api/status published unfamiliar weight names %s -- using "
                  "the recorded v2 weights)" % sorted(w), file=sys.stderr)
    except Exception as exc:
        print("  (/api/status unreachable: %r -- using the recorded v2 weights)"
              % (exc,), file=sys.stderr)
    return dict(FALLBACK_WEIGHTS), "recorded copy of kibble-score-v2"


def main(argv):
    stats = json.load(open(argv[1], encoding="utf-8")) if len(argv) > 1 else get(STATS)
    passports = stats["passports"]
    weights, origin = live_weights()
    print("weights (%s): %s" % (origin, json.dumps(weights, sort_keys=True)))

    rows, exact = [], 0
    for p in passports:
        terms = {k: weights.get(k, 0) * p.get(k, 0) for k in weights}
        total = sum(terms.values())
        exact += (total == p["score"])
        rows.append({"rank": p["rank"], "did": p["did"], "score": p["score"],
                     "recomputed": total, "terms": terms})

    print("\nscores reproduced exactly: %d/%d" % (exact, len(rows)))
    if exact != len(rows):
        for r in rows:
            if r["recomputed"] != r["score"]:
                print("  MISMATCH rank %s: printed %s, recomputed %s  %s"
                      % (r["rank"], r["score"], r["recomputed"], r["terms"]))
        print("\nThe weights no longer explain the board. Do not read the "
              "decomposition below; re-derive the formula first.")
        return 2

    print("\nrank  score   jobs_posted  results  given  peer_useful  peer_not  "
          "briefs  jobs_posted share")
    for r in rows[:12]:
        t = r["terms"]
        print("%4d  %6d  %11d  %7d  %5d  %11d  %8d  %6d  %14.1f%%"
              % (r["rank"], r["score"], t["jobs_posted"], t["results_delivered"],
                 t["attestations_given"], t["useful_attestations_received"],
                 t["not_useful_attestations_received"], t["briefs"],
                 100.0 * t["jobs_posted"] / r["score"] if r["score"] else 0.0))

    agg = collections.Counter()
    for r in rows:
        agg.update(r["terms"])
    summed = sum(r["score"] for r in rows)
    print("\nboard-wide term totals (%d passports, summed score %d):" % (len(rows), summed))
    for k, v in agg.most_common():
        print("  %-34s %+8d  (%+.1f%%)" % (k, v, 100.0 * v / summed))

    self_total = sum(agg[k] for k in SELF_SERVED)
    peer_total = sum(agg[k] for k in PEER_MOVED)
    denom = abs(self_total) + abs(peer_total)
    print("\n  self-served terms (no counterparty needed) : %+8d" % self_total)
    print("  peer-moved terms (someone must act on you) : %+8d" % peer_total)
    print("  -> peers control %.1f%% of the magnitude on this board"
          % (100.0 * abs(peer_total) / denom if denom else 0.0))

    cutoff = min(r["score"] for r in rows)
    without = sorted((r["score"] - r["terms"]["jobs_posted"] for r in rows), reverse=True)
    print("\n  rank-%d cutoff: %d" % (max(r["rank"] for r in rows), cutoff))
    print("  if jobs_posted scored 0, still clearing that cutoff: %d of %d"
          % (sum(1 for v in without if v >= cutoff), len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
