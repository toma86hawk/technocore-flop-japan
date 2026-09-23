#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""shortlist_tail_bound.py -- how wide is our sonnet-2 archive's per-entry
estimate, measured against the referee's own numbers?

WHY THIS IS NEW (r182)
r181 graded the archive against the five published shortlist counts and found a
14.6x spread in capture ratio.  It drew the conclusion "the one adjacent pair
that sat inside the capture band is the one we got wrong" -- a statement about
ONE pair.  On 2026-09-23T03:36:20Z the referee published a SIXTH ground-truth
number, and it is not in the shortlist: @love8_dao's entry placed "39th of 76
with 105 counted votes".  A point at rank 39 pins the tail, and pinning the
tail converts the spread from a remark about one pair into an interval for
EVERY entry we hold.

The rank-39 point is not an assumption.  Ranking is definitional: if rank 39
has 105 votes then ranks 1..38 each have >= 105 and ranks 40..76 each have
<= 105.  That alone bounds how much of the total can hide in the tail.

WHAT IT MEASURES
  1. the capture band [min ratio, max ratio] from the five graded entries
  2. for each ungraded entry we hold, the interval its TRUE count must lie in
     if its capture sits anywhere inside that band
  3. whether that interval is narrow enough to place the entry against the
     published shortlist -- i.e. whether our archive could ever have ranked it
  4. the rank-39 reconstruction of the middle of the field

FALSIFIERS
  (A) an entry whose interval EXCLUDES the shortlist range -> the archive did
      carry placing power for that entry, and "ranking is luck" is too strong.
  (B) the reconstructed ranks 6..38 mean falling BELOW 105 -> the published
      total and the rank-39 point cannot both be accepted-ballot counts, and
      the whole reconstruction is void.
"""
import json, os, sys, collections

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.abspath(__file__))

# --- ground truth published by the referee ---------------------------------
OFFICIAL = {"quire": 16837, "pom-team": 7630, "maragung-flop": 6852,
            "wickerlight": 2781, "pelmora": 2560}
TOTAL_BALLOTS = 59308      # "59,308 ballots set the shortlist of five"
N_ENTRIES     = 76         # matches signed shortlist-1 "76 valid entries"
TAIL_RANK     = 39         # @love8_dao, 2026-09-23T03:36:20Z
TAIL_VOTES    = 105

def load_ours():
    """Reuse the archive the r181 tool built, via its own accepted-ballot count."""
    for name in ("_r181_archive_accepted.json", "_r182_archive_accepted.json"):
        p = os.path.join(ROOT, name)
        if os.path.exists(p):
            return json.load(open(p, encoding="utf-8"))
    return None

def main():
    ours = load_ours()
    if ours is None:
        print("no cached per-entry archive count found; run archive_vs_official.py first")
        print("falling back to the figures it printed at r181/r182")
        ours = {"quire": 5088, "pom-team": 939, "maragung-flop": 814,
                "wickerlight": 457, "pelmora": 53, "moonquill": 972,
                "quietlake": 234, "emberwick": 200, "solvarn": 166}
        ours_total = 9724
    else:
        ours_total = sum(ours.values())

    print("== capture band from the five graded entries ==")
    ratios = {}
    for e, off in OFFICIAL.items():
        if ours.get(e):
            ratios[e] = off / ours[e]
            print("  %-16s official %6d  ours %5d  ratio %6.1f"
                  % (e, off, ours[e], ratios[e]))
    lo, hi = min(ratios.values()), max(ratios.values())
    print("  band: [%.1f, %.1f]   width %.1fx" % (lo, hi, hi / lo))

    shortlist_lo, shortlist_hi = min(OFFICIAL.values()), max(OFFICIAL.values())
    print("\n  shortlist range: %d (pelmora, rank 5) .. %d (quire, rank 1)"
          % (shortlist_lo, shortlist_hi))

    print("\n== what our archive could say about the entries it did NOT get graded on ==")
    print("   (true count must be ours x band, if capture sits anywhere in the band)")
    fired_A = []
    for e in sorted(ours, key=lambda k: -ours[k]):
        if e in OFFICIAL:
            continue
        iv_lo, iv_hi = ours[e] * lo, ours[e] * hi
        # can this interval be placed relative to the shortlist?
        below = iv_hi < shortlist_lo          # certainly missed the shortlist
        above = iv_lo > shortlist_hi          # certainly would have won
        placed = below or above
        if placed:
            fired_A.append(e)
        print("  %-16s ours %5d -> true in [%8.0f, %8.0f]   %s"
              % (e, ours[e], iv_lo, iv_hi,
                 "PLACEABLE" if placed else "spans the shortlist - unplaceable"))

    print("\n-- falsifier (A): an ungraded entry whose interval excludes the shortlist range --")
    if fired_A:
        print("  FIRED for: %s" % ", ".join(fired_A))
        print("  -> the archive did carry placing power there; 'ranking is luck' is too strong.")
    else:
        print("  NOT FIRED. every ungraded entry's interval spans the whole shortlist range,")
        print("  so the archive could not place ANY of them -- not one pair, all of them.")

    print("\n== rank-39 reconstruction of the middle of the field ==")
    top5 = sum(OFFICIAL.values())
    rest = TOTAL_BALLOTS - top5
    n_rest = N_ENTRIES - 5
    print("  top five sum            : %d" % top5)
    print("  published total ballots : %d" % TOTAL_BALLOTS)
    print("  left for ranks 6..76    : %d over %d entries (mean %.0f)"
          % (rest, n_rest, rest / n_rest))
    n_tail = N_ENTRIES - TAIL_RANK          # ranks 40..76
    max_tail = n_tail * TAIL_VOTES
    n_mid = TAIL_RANK - 5                   # ranks 6..38 plus rank 39 handled below
    mid_min = rest - max_tail - TAIL_VOTES
    print("  ranks 40..76 (%d entries) each <= %d  -> at most %d"
          % (n_tail, TAIL_VOTES, max_tail))
    print("  rank 39 itself          : %d" % TAIL_VOTES)
    print("  so ranks 6..38 (%d entries) hold at least %d, mean >= %.0f"
          % (n_mid, mid_min, mid_min / n_mid))

    print("\n-- falsifier (B): reconstructed ranks 6..38 mean below the rank-39 count --")
    if mid_min / n_mid < TAIL_VOTES:
        print("  FIRED. mean %.0f < %d -- the published total and the rank-39 point"
              % (mid_min / n_mid, TAIL_VOTES))
        print("  cannot both be accepted-ballot counts. reconstruction VOID.")
    else:
        print("  NOT FIRED. mean >= %.0f, comfortably above the rank-39 count of %d,"
              % (mid_min / n_mid, TAIL_VOTES))
        print("  so both numbers can be accepted-ballot counts on the same scale.")
        print("  consequence: at least %d entries sit between %d and %d votes --"
              % (n_mid, TAIL_VOTES, shortlist_lo))
        print("  a densely populated band immediately under the rank-5 cutoff of %d."
              % shortlist_lo)

    print("\n== is 59,308 ballots CAST or ballots COUNTED? (resolved by measurement) ==")
    RAW_OURS = 151595   # ballots our archive holds, before any ruling
    print("  ballots our archive holds, pre-ruling : %d" % RAW_OURS)
    print("  referee's published figure            : %d" % TOTAL_BALLOTS)
    if RAW_OURS > TOTAL_BALLOTS:
        print("  our PARTIAL archive already holds %.1fx the referee's figure in raw"
              % (RAW_OURS / float(TOTAL_BALLOTS)))
        print("  ballots, so %d cannot be ballots CAST. it is a post-ruling count," % TOTAL_BALLOTS)
        print("  and the capture arithmetic above is on the right scale.")
    else:
        print("  inconclusive: our raw holding does not exceed the published figure.")

    print("\n== population capture ==")
    print("  our accepted total  : %d" % ours_total)
    print("  official total      : %d" % TOTAL_BALLOTS)
    print("  overall capture     : %.1f%%" % (100.0 * ours_total / TOTAL_BALLOTS))

main()
