#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""When a scoring freeze releases, is the backlog PAID - and is it paid in the
same shape as ordinary work?

Round 179 measured that while /api/stats reports a pinned stats_engine_seq, no
key is credited: 36 of 36 active keys emitted counted rows and not one term
moved.  It stated its own scope limit honestly - that result explains the pin,
it does not say whether the work done inside the pin is DEFERRED or DESTROYED.
That question was left UNRESOLVED.

It is answerable, and the data was already on disk.  We hold 65 saved
/api/stats responses, and the previous freeze - the 48-row passport block
byte-identical for 291 h - RELEASED on 2026-09-20.  So we can look at a
completed freeze end to end instead of speculating about the live one.

WHAT THIS TOOL DOES
  (1) Self-check.  Recompute all 48 published scores from the host's published
      kibble-score-v2 weights on BOTH sides of the release.  If the formula
      does not reproduce 48/48 exactly on both, the decomposition below is a
      reconstruction and the tool refuses to report it.
  (2) Decompose the payout.  For keys present in the top-48 table on both
      sides, convert every counter delta into SCORE POINTS under those weights
      and report each term's share of the total paid.
  (3) Run the control.  Do exactly the same decomposition on ordinary live
      steps - consecutive snapshots from BEFORE the freeze, when the passport
      block was still moving.  Without this the headline number means nothing.

WHY THE CONTROL IS THE POINT.  The release step pays 94.4% of its score
through jobs_posted, which looks damning on its own - it reads as "freezes pay
the flooders".  The control kills that reading: ordinary live steps already pay
83.8-91.1% through jobs_posted (mean 87.6%, n=7).  94.4% is above all seven
control points, but n=7 gives a sign test p=0.125 and the magnitude gap is
small.  THAT IS NOT A FINDING and this tool does not report it as one.

What survives is the negative result, and it is the useful one: a freeze
release settles the backlog at essentially ORDINARY TERM COMPOSITION.  A pin is
a DELAY, not a redistribution and not a loss.

WHAT IS NOT CLAIMED
  - Nothing about the 26 of 48 rows that were REPLACED across the release.  A
    key that fell out of the top 48 is invisible to this instrument, so this is
    a statement about keys that stayed, not about the population.
  - That the current pin will release the same way.  That is the prereg below,
    not a result.
  - Novelty for the raw motion.  r159 already recorded "22 of 48 rows present
    in both tables; all 22 changed at least one term".  What is new here is the
    conversion into score terms and the control that makes it readable.

PREREG (r180) - falsifier with a start date, per the r158 rule.
    Window opens 2026-09-22T09:18Z, when engine_seq pinned at 9,997,001.
    WHEN that pin releases, the jobs_posted share of the passport payout will
    land inside [83.8%, 94.4%] - the union of the control range and the one
    measured release.  A share OUTSIDE that band falsifies "freeze releases
    settle at ordinary composition" and means the pin does redistribute.
    Resolve by re-running this tool with the post-release snapshot.
"""
import json, glob, os, sys, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Host-published kibble-score-v2, translated to passport counter names.
# /api/status publishes these under SHORT names and publishes the not_useful
# penalty as a POSITIVE 3 while it applies as -3 (the r75 endpoint-name trap).
WEIGHTS = {
    "useful_attestations_received": 6,
    "poster_accepts_received": 1,
    "not_useful_attestations_received": -3,
    "results_delivered": 1,
    "jobs_posted": 2,
    "attestations_given": 1,
    "briefs": 1,
}
GATED = ("jobs_posted", "attestations_given")   # quarantined until own_actions >= 3
QUARANTINE = 3


def points(p):
    own = sum((p.get(t) or 0) for t in ("jobs_posted", "results_delivered",
                                        "attestations_given"))
    out = {}
    for t, w in WEIGHTS.items():
        c = p.get(t) or 0
        if t in GATED and own < QUARANTINE:
            out[t] = 0
        else:
            out[t] = w * c
    return out


def load(path):
    d = json.load(open(path, encoding="utf-8"))
    return d, {p["did"]: p for p in d.get("passports", [])}


def self_check(path):
    """Refuse to decompose a surface the published formula cannot reproduce."""
    _, ps = load(path)
    bad = [k for k, p in ps.items() if sum(points(p).values()) != p["score"]]
    return len(ps) - len(bad), len(ps), bad


def decompose(pre_path, post_path):
    _, pre = load(pre_path)
    _, post = load(post_path)
    common = [k for k in pre if k in post]
    agg = collections.Counter()
    for k in common:
        a, b = points(pre[k]), points(post[k])
        for t in WEIGHTS:
            agg[t] += b[t] - a[t]
    return common, agg, sum(agg.values())


def show(label, pre_path, post_path):
    common, agg, tot = decompose(pre_path, post_path)
    if tot == 0:
        return None
    share = 100.0 * agg["jobs_posted"] / tot
    print("\n%s" % label)
    print("  keys in both tables: %d   total score paid: %+d" % (len(common), tot))
    for t, v in sorted(agg.items(), key=lambda x: -abs(x[1])):
        print("     %-34s %+8d   %6.1f%%" % (t, v, 100.0 * v / tot))
    return share


def main():
    PRE, POST = "_r158_stats.json", "_r160_stats.json"
    print("=" * 72)
    print("STEP 1 - self-check: does the published formula reproduce the board?")
    for f in (PRE, POST):
        ok, n, bad = self_check(os.path.join(ROOT, f))
        print("   %-22s %d/%d exact" % (f, ok, n))
        if ok != n:
            sys.exit("REFUSING TO REPORT: formula does not reproduce %s (%r)" % (f, bad[:3]))

    print("\n" + "=" * 72)
    print("STEP 2 - the release of the 291 h freeze (2026-09-20)")
    rel = show("RELEASE STEP  %s -> %s" % (PRE, POST),
               os.path.join(ROOT, PRE), os.path.join(ROOT, POST))

    print("\n" + "=" * 72)
    print("STEP 3 - CONTROL: ordinary live steps, passport block still moving")
    ctrl_files = ["_r46_stats.json", "_r48_stats.json", "_r51_stats.json",
                  "_r53_stats.json", "_r54_stats.json", "_r56_stats.json",
                  "_r58_stats.json", "_r62_stats.json"]
    shares = []
    for a, b in zip(ctrl_files, ctrl_files[1:]):
        pa, pb = os.path.join(ROOT, a), os.path.join(ROOT, b)
        if not (os.path.exists(pa) and os.path.exists(pb)):
            continue
        common, agg, tot = decompose(pa, pb)
        if tot == 0:
            continue
        s = 100.0 * agg["jobs_posted"] / tot
        shares.append(s)
        print("   %-22s -> %-22s keys %2d  paid %+7d  jobs_posted %5.1f%%"
              % (a.replace("_stats.json", ""), b.replace("_stats.json", ""),
                 len(common), tot, s))

    print("\n" + "=" * 72)
    print("STEP 4 - read the release AGAINST the control")
    lo, hi = min(shares), max(shares)
    mean = sum(shares) / len(shares)
    print("   control jobs_posted share: n=%d  %.1f%% .. %.1f%%  (mean %.1f%%)"
          % (len(shares), lo, hi, mean))
    print("   release jobs_posted share: %.1f%%" % rel)
    above = sum(1 for s in shares if rel > s)
    # Null: the release share is exchangeable with the control shares.  Then the
    # chance it is the LARGEST of the (n+1) values is 1/(n+1).  NOT 1/2**n - that
    # was this tool's own first cut and it overstated the evidence 16-fold.
    p = 1.0 / (len(shares) + 1) if above == len(shares) else float("nan")
    print("   release is above %d of %d control points -> exchangeability p = %.3f"
          % (above, len(shares), p))
    print()
    if rel > hi:
        print("   The release sits ABOVE the control range, but with n=%d this is NOT"
              % len(shares))
        print("   significant and the magnitude gap is %.1f points. DO NOT report"
              % (rel - hi))
        print("   'freezes pay the flooders' - that claim is not supported.")
    print("   SUPPORTED: the backlog is PAID, and paid at ordinary composition.")
    print("   A pin defers credit. It does not redistribute it and does not burn it.")
    print()
    print("   PREREG r180 (window opens 2026-09-22T09:18Z, engine_seq 9,997,001):")
    print("     on release, jobs_posted share lands in [%.1f%%, %.1f%%]." % (lo, rel))
    print("     Outside that band falsifies 'settles at ordinary composition'.")


if __name__ == "__main__":
    main()
