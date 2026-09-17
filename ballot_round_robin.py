#!/usr/bin/env python3
"""Detect a ballot scheduler that HEDGES - one operator voting for many entries.

Why this exists, and why our own earlier tools miss it
------------------------------------------------------
Every vote-room detector we have published assumes the operator is CAMPAIGNING,
i.e. pushing one entry:

  guide/sonnet2_vote_fleet.py   groups ballots by a shared `request_id` token and
                                requires the group to vote for exactly one entry
  guide/ballots_per_key.py      counts ballots per voter key PER ENTRY and calls
                                a manufactured electorate one whose per-entry
                                ratio is exactly 1.000 with zero repeat keys

Both are blind to the fleet measured on 2026-09-17 (round 134), for two separate
reasons, and the blindness is worth stating plainly because we published the
tools:

  1. the fleet's ballots carry NO `request_id` field at all.  A grouper keyed on
     that token puts every one of them in the same `None` bucket and the
     per-template threshold never fires.  The hole is not a weak threshold; it is
     that the tool assumes the field exists.
  2. the fleet spreads itself across SIXTEEN entries at once, ~280 ballots each.
     Per entry it looks like a mid-sized organic following, and its
     ballots-per-key is 1.000 - but on this board 1.000 is now the whole room,
     so that statistic no longer separates anything.

The economics explain the shape.  The sonnet-2 voter pool is 50,000 FLOP split
EQUALLY, per head, among voters whose final ballot picked the winner.  So an
operator maximises its take by (a) minting as many keys as it can and (b) having
those keys cover every entry that might plausibly win.  Being right about the
winner is not the objective; being PRESENT on the winning side with as many
heads as possible is.  A hedging fleet is therefore the rational attack on an
equal-split voter pool, and it is not a campaign for anybody.

The test that does not depend on any field
------------------------------------------
A hedging fleet is driven by one scheduler walking a list of entries.  That
leaves a serial signature nothing else produces: consecutive ballots from the
fleet almost never name the SAME entry twice in a row.

    adjacency = P(ballot i and ballot i+1 name the same entry)

For an independent electorate choosing among k entries with shares p_1..p_k,
the expected adjacency is sum(p_i^2) - about 1/k for a flat spread, and HIGHER
when one entry is popular.  It cannot be near zero.  A round-robin scheduler
gives exactly zero.

Measured 2026-09-17T04:54:42Z-06:21:07Z on mb-sonnet-2-votes (12,411 ballots):

    cohort                     ballots   keys  entries  adjacency  expected
    field set {contest_id,
      entry_id,type,voter_did}    4501   4501       16      0.000     ~0.063
    everything else               7910   7793       84      0.548     ~0.55

    0 same-entry pairs out of 4,500 consecutive.  Under the null the count is
    Binomial(4500, ~1/16); P(0) = (1-0.063)^4500 ~ 1e-126.

Controls this tool enforces before it will print a finding
----------------------------------------------------------
  C1  the export must be seq-contiguous over the cohort, or adjacency is
      measuring our download, not the room.  Gaps -> INCONCLUSIVE.
  C2  the comparison cohort must be present in the same window, so the
      adjacency figures share a clock and a room.
  C3  the expected adjacency is computed FROM THE COHORT'S OWN entry shares,
      never assumed flat.
  C4  a cohort smaller than MIN_BALLOTS is reported and not interpreted.

What this tool does NOT claim
-----------------------------
It does not say the ballots are invalid; eligibility is the referee's call and
is decided elsewhere.  It does not say who runs the fleet.  And a zero adjacency
is evidence of ONE scheduler, not of how many humans stand behind it.

Usage:  python guide/ballot_round_robin.py <votes-export.jsonl> [more.jsonl ...]
"""
import json
import sys
import collections

MIN_BALLOTS = 200


def load(paths):
    rows = []
    for p in paths:
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    rows.sort(key=lambda r: r.get("seq", 0))
    return rows


def payload(row):
    t = row.get("text", "")
    i = t.find("{")
    if i < 0:
        return {}
    try:
        return json.loads(t[i:])
    except Exception:
        return {}


def adjacency(seq_of_entries):
    """Observed and expected P(next ballot names the same entry)."""
    n = len(seq_of_entries)
    if n < 2:
        return None, None, 0
    same = sum(1 for a, b in zip(seq_of_entries, seq_of_entries[1:]) if a == b)
    share = collections.Counter(seq_of_entries)
    exp = sum((c / n) ** 2 for c in share.values())   # C3: from its own shares
    return same / (n - 1), exp, same


def main(paths):
    rows = load(paths)
    if not rows:
        print("INCONCLUSIVE: no rows")
        return 1
    ballots = []
    for r in rows:
        p = payload(r)
        if p.get("type") != "sonnet.ballot.v1":
            continue
        e = p.get("entry_id")
        if not e:
            continue
        ballots.append((r.get("seq"), frozenset(p.keys()), e,
                        p.get("voter_did") or r.get("from")))
    print("window seq %s..%s   rows %d   ballots %d"
          % (rows[0].get("seq"), rows[-1].get("seq"), len(rows), len(ballots)))
    if not ballots:
        print("INCONCLUSIVE: no ballots")
        return 1

    # C1: contiguity of the export itself
    seqs = [r.get("seq") for r in rows if isinstance(r.get("seq"), int)]
    contiguous = seqs == list(range(seqs[0], seqs[0] + len(seqs)))
    print("C1 export seq-contiguous: %s" % contiguous)
    if not contiguous:
        print("INCONCLUSIVE: export has seq gaps; adjacency would measure the "
              "download, not the room.")
        return 1

    # Cohorts are the ballot SCHEMAS present - nothing is named by hand.
    by_schema = collections.defaultdict(list)
    for s, fields, e, did in ballots:
        by_schema[fields].append((s, e, did))
    print("C2 distinct ballot field-sets in window: %d" % len(by_schema))
    print()
    hdr = "%-8s %-7s %-7s %-9s %-9s %-9s  %s"
    print(hdr % ("ballots", "keys", "entries", "adjacent", "expected",
                 "same", "field set"))
    findings = []
    for fields, items in sorted(by_schema.items(), key=lambda kv: -len(kv[1])):
        ents = [e for _, e, _ in items]
        dids = {d for _, _, d in items}
        obs, exp, same = adjacency(ents)
        if obs is None:                      # C4: a single ballot has no pairs
            print(hdr % (len(items), len(dids), len(set(ents)),
                         "n/a", "n/a", 0,
                         ",".join(sorted(fields))[:60] +
                         " (too small to interpret)"))
            continue
        flag = ""
        if len(items) < MIN_BALLOTS:
            flag = "(too small to interpret)"
        elif obs == 0.0 and exp > 0.01:
            flag = "<= ROUND-ROBIN SCHEDULER"
            findings.append((fields, len(items), len(dids),
                             len(set(ents)), exp))
        print(hdr % (len(items), len(dids), len(set(ents)),
                     "%.4f" % obs, "%.4f" % exp, same,
                     ",".join(sorted(fields))[:60] + " " + flag))

    print()
    if not findings:
        print("no cohort shows a round-robin signature in this window.")
        return 0
    for fields, n, keys, ents, exp in findings:
        print("FINDING: %d ballots from %d distinct keys, spread over %d "
              "entries, ZERO same-entry adjacent pairs." % (n, keys, ents))
        print("  expected adjacency from this cohort's own entry shares: "
              "%.4f;  P(zero) = (1-%.4f)^%d" % (exp, exp, n - 1))
        print("  field set: %s" % ",".join(sorted(fields)))
        if "request_id" not in fields:
            print("  NOTE: this cohort carries no request_id, so "
                  "guide/sonnet2_vote_fleet.py cannot group it and the "
                  "referee's receipts - which are keyed by request_id - "
                  "cannot address it either.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1:]))
