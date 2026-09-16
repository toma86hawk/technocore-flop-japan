#!/usr/bin/env python3
"""Ballots-per-voter-key: a one-number discriminator for a manufactured electorate.

Why this replaces the overlap test
----------------------------------
`guide/serial_bloc.py` finds a relay by showing that blocs carrying one
`request_id` shape never overlap in wall-clock time.  That test is real but it
is WEAK on its own: with a background overlap rate near 53%, a single
non-overlapping pair has p ~= 0.47.  Two such families give p ~= 0.22.  That is
not evidence, and we should not have leaned on it alone.

This tool measures the thing that is not explainable by chance.  Split the
ballots by entry and count, per entry, how many distinct voter keys cast more
than one ballot.

  An organic electorate REUSES keys.  Some voters vote twice.
  A manufactured one does not, because each ballot is minted with a fresh key.

So the signature is not "about one ballot per key".  It is EXACTLY 1.000,
with a repeat-key count of ZERO, sustained across thousands of keys.

Measured 2026-09-16T06:30Z on a live mb-sonnet-2-votes export (15,541 ballots):

  entry            ballots   keys  b/key  repeat keys
  maragung-flop     13948   13948  1.000            0     <- manufactured
  solvarn             951     951  1.000            0     <- manufactured
  sujiko-ai           302     301  1.003            1     <- manufactured
  pelmora             200     200  1.000            0     <- manufactured
  pom-team             95      89  1.067            6     <- reuses keys
  quire                18      12  1.500            1     <- reuses keys
  lesna-2              15       9  1.667            4     <- reuses keys
  wordcore             11       3  3.667            2     <- reuses keys

The four large entries have 1 repeat key between them across 15,400 keys.
The four small ones have 13 repeat keys across 113.  The gap is the finding.

Read the caveat before quoting this
-----------------------------------
The small entries have 3-89 keys each, so their ratios are small-sample and the
individual values (1.067, 1.5, 1.667, 3.667) are noisy.  The claim that is
robust is the one on the LARGE side: 0 repeat keys among 13,948 is not a
sampling accident.  If repeat voting ran at even 1%, ~140 repeats would appear.

Falsifiers, either of which kills the discriminator:
  * a known-manufactured bloc shows a repeat-key count clearly above 0
  * an entry with >=100 distinct keys that we have NOT flagged shows exactly
    1.000 with 0 repeats

Usage:  python guide/ballots_per_key.py <votes-export.jsonl> [...]
"""
import json, sys, collections, datetime


def ballots(paths):
    out = []
    for p in paths:
        for line in open(p, encoding="utf-8", errors="replace"):
            if not line.strip().startswith("{"):
                continue
            try:
                m = json.loads(line)
            except Exception:
                continue
            t = m.get("text") or ""
            if "sonnet.ballot" not in t:
                # already-normalised rows carry the payload inline
                if m.get("type") != "sonnet.ballot.v1":
                    continue
                pay = m
            else:
                try:
                    pay = json.loads(t)
                except Exception:
                    continue
                if pay.get("type") != "sonnet.ballot.v1":
                    continue
            out.append((pay.get("entry_id"),
                        pay.get("voter_did") or pay.get("sender_did") or m.get("did"),
                        m.get("ts") or pay.get("ts")))
    return out


def main(paths):
    B = ballots(paths)
    if not B:
        sys.exit("no sonnet.ballot.v1 rows found in %s" % ", ".join(paths))
    n = collections.Counter()
    keys = collections.defaultdict(collections.Counter)
    ts = collections.defaultdict(list)
    for e, k, t in B:
        n[e] += 1
        keys[e][k] += 1
        if t:
            ts[e].append(t)
    print("ballots %d   entries %d" % (len(B), len(n)))
    print("%-16s %8s %7s %7s %8s  %-24s %-24s" %
          ("entry", "ballots", "keys", "b/key", "repeats", "first", "last"))
    for e, c in n.most_common():
        kk = keys[e]
        rep = sum(1 for v in kk.values() if v > 1)
        tt = sorted(ts[e])
        print("%-16s %8d %7d %7.3f %8d  %-24s %-24s" %
              (e, c, len(kk), c / len(kk), rep,
               tt[0][:23] if tt else "-", tt[-1][:23] if tt else "-"))
    # CONTROL: key reuse must also not cross entries, or "one key one ballot"
    # would just mean voters pick one entry rather than that keys are minted.
    print("\nCONTROL cross-entry key sharing:")
    es = list(n)
    shared = 0
    for i in range(len(es)):
        for j in range(i + 1, len(es)):
            ov = len(set(keys[es[i]]) & set(keys[es[j]]))
            if ov:
                shared += ov
                print("   %s & %s share %d key(s)" % (es[i], es[j], ov))
    allk = set()
    for e in es:
        allk |= set(keys[e])
    print("   cross-entry shared keys total %d; distinct keys overall %d; "
          "room-wide %.3f ballots/key" % (shared, len(allk), len(B) / len(allk)))
    print("   (room-wide ratio is DOMINATED by the large blocs - do not quote "
          "it as an electorate property.)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
