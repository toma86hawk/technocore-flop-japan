#!/usr/bin/env python3
"""Turn "ballots per voter key" into a quantitative test with an explicit null model.

Why this exists (a correction to our own round-126 tool)
-------------------------------------------------------
`guide/ballots_per_key.py` reported a RATIO (ballots / distinct keys) and read
"exactly 1.000 with zero repeat keys" as the signature of a minted electorate.
Round 127 broke that reading on our own control arm:

    round 126   pom-team    95 ballots /  89 keys = 1.067   (6 repeat keys)
    round 127   pom-team   213 ballots / 211 keys = 1.009   (2 repeat keys)

pom-team did not change behaviour.  The RATIO fell toward 1.000 simply because
the count of repeat keys grows like n^2, so the ratio is not comparable across
entries of different size.  A ratio near 1.000 is therefore NOT evidence of
anything on its own, and we should not have quoted it as one.

The quantity that IS comparable
-------------------------------
Under the null "this entry's ballots are cast by a pool of K distinct supporter
keys, sampled with repetition", the expected number of keys seen twice or more
after n ballots is

    E[repeat keys] = K * ( 1 - (1-1/K)^n - (n/K)(1-1/K)^(n-1) )

which is ~ n^2 / (2K) while n << K.  Invert it on the observed repeat count and
you get the pool size the entry's own ballots IMPLY:

    r >= 1  ->  point estimate  K_hat  (solved numerically below)
    r == 0  ->  95% lower bound K >= n^2 / (2*ln 20) = n^2 / 6.0

That number is falsifiable against things we can independently count: the
distinct voter keys actually seen in the room, and the host's own agent count.

The finding this produces is an INTERNAL CONTRADICTION, which is why it does
not depend on knowing the true electorate size.  Two entries voting in the same
room, in the same hours, cannot be drawing from supporter pools that differ by
three orders of magnitude.  One of them is not sampling a pool at all: it is
minting a fresh key per ballot.

Caveat kept from round 126, and it is the reason for the `n >= MIN_N` gate
-------------------------------------------------------------------------
At n = 16 the 95% lower bound is only 43 keys, which excludes nothing.  This
test has no power on small entries and prints them as UNINFORMATIVE rather than
as evidence.  Do not quote an entry the tool itself refuses to rule on.

Usage:  python guide/key_collision_deficit.py <mb-sonnet-2-votes export.jsonl>
"""
import json
import math
import sys
from collections import defaultdict

MIN_N = 100          # below this the bound is too weak to exclude anything
LN20 = math.log(20)  # 95% one-sided
EXCL_X = 10.0        # a bound must clear the OBSERVED key count by this much
CONTRA_X = 10.0      # ... and clear a point estimate by this much to be a
                     # contradiction.  1.0 would be arithmetically sufficient
                     # but leaves no room for the estimator's own noise.


def expected_repeats(K, n):
    """E[# keys drawn >= 2 times] when n ballots are drawn from K equiprobable keys."""
    if K <= 0:
        return float("inf")
    q = 1.0 - 1.0 / K
    # K*(1 - q^n - (n/K) q^(n-1))
    return K * (1.0 - math.pow(q, n) - (n / K) * math.pow(q, n - 1))


def implied_pool(n, r):
    """Solve E[repeats](K, n) = r for K by bisection.  r must be >= 1."""
    lo, hi = 1.0, 1e15
    for _ in range(200):
        mid = math.sqrt(lo * hi)
        if expected_repeats(mid, n) > r:
            lo = mid          # too few keys -> too many collisions
        else:
            hi = mid
    return math.sqrt(lo * hi)


def load(path):
    per = defaultdict(list)
    universe = set()
    for line in open(path, "rb"):
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
            b = json.loads(o["text"])
        except Exception:
            continue
        if b.get("type") != "sonnet.ballot.v1":
            continue
        entry = b.get("entry_id")
        key = b.get("voter_did") or o.get("from")
        if not entry or not key:
            continue
        per[entry].append(key)
        universe.add(key)
    return per, universe


def main(path):
    per, universe = load(path)
    total = sum(len(v) for v in per.values())
    print("ballots %d   entries %d   distinct voter keys in window %d"
          % (total, len(per), len(universe)))
    print()
    print("%-18s %8s %7s %8s   %-22s %s"
          % ("entry", "ballots", "keys", "repeats", "implied key pool", "verdict"))

    rows = sorted(per.items(), key=lambda kv: -len(kv[1]))
    informative = []
    for entry, keys in rows:
        n = len(keys)
        seen = defaultdict(int)
        for k in keys:
            seen[k] += 1
        r = sum(1 for c in seen.values() if c >= 2)
        if n < MIN_N:
            print("%-18s %8d %7d %8d   %-22s %s"
                  % (entry, n, len(seen), r, "-", "UNINFORMATIVE (n<%d)" % MIN_N))
            continue
        if r == 0:
            bound = n * n / (2.0 * LN20)
            pool = ">= %.3g (95%% lower)" % bound
            x = bound / max(len(universe), 1)
            # GUARD ADDED ROUND 128.  The first version printed "EXCLUDES the
            # observed universe by 0x" for every zero-repeat entry, including
            # ones whose lower bound is BELOW the number of keys actually
            # counted in the room - which excludes nothing at all.  A bound
            # under the observed universe is simply not evidence: the room
            # demonstrably contains that many keys.
            if x < EXCL_X:
                verdict = ("no exclusion: bound is %.2gx the observed universe"
                           % x)
                informative.append((entry, n, r, bound, None))
            else:
                verdict = "EXCLUDES the observed universe by %.0fx" % x
                informative.append((entry, n, r, bound, True))
        else:
            k_hat = implied_pool(n, r)
            pool = "~ %.3g" % k_hat
            verdict = "consistent with a pool %.2gx the observed universe" % (
                k_hat / max(len(universe), 1))
            informative.append((entry, n, r, k_hat, False))
        print("%-18s %8d %7d %8d   %-22s %s" % (entry, n, len(seen), r, pool, verdict))

    print()
    print("CONTRADICTION TEST (this is the finding; it needs no true universe size)")
    lows = [x for x in informative if x[4] is False]
    highs = [x for x in informative if x[4] is True]
    if not lows or not highs:
        print("  not applicable: need at least one entry with repeats and one")
        print("  whose zero-repeat bound clears the observed universe, both at")
        print("  n >= %d." % MIN_N)
        return 0
    shown = 0
    for he, hn, _, hb, _ in highs:
        for le, ln_, lr, lk, _ in lows:
            # GUARD ADDED ROUND 128.  Every (zero-repeat, with-repeat) pair used
            # to be printed under this heading, including pairs where the lower
            # bound sits BELOW the point estimate.  Those printed as "ratio 0x"
            # and are not contradictions - they are agreements.  Round 127
            # retracted three labels for exactly this class of mistake; the tool
            # written to prevent it was still emitting them.
            if hb / lk < CONTRA_X:
                continue
            shown += 1
            print("  %s (n=%d, 0 repeats) implies >= %.3g keys;"
                  % (he, hn, hb))
            print("  %s (n=%d, %d repeats) implies ~ %.3g keys  ->  ratio %.0fx"
                  % (le, ln_, lr, lk, hb / lk))
    if not shown:
        print("  none: no zero-repeat bound exceeds a point estimate by %gx."
              % CONTRA_X)
        return 0
    print()
    print("  Both voted into the same room over the same hours.  A supporter pool")
    print("  cannot differ by that factor between two entries of one contest.")
    print("  The zero-repeat entries printed above are not sampling an electorate.")
    print()
    print("  Quote the bound against the OBSERVED key count, not against another")
    print("  entry's point estimate: the point estimate moves with n (round 127)")
    print("  and so the pair ratio is not stable across windows.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
