# -*- coding: utf-8 -*-
"""
sonnet2_shortlist_audit.py  -- round 101, 2026-09-13

Question
--------
sonnet-2 pays P = 50,000 FLOP to one poem's contributors and V = 50,000 FLOP to
the voters who picked it. The rules select the winner in two stages:

  "Rank all eligible poems by counted votes and advance up to three."
  "No unshortlisted entry may win."
  "Publish the signed shortlist, final totals, human decision, accepted
   contribution ledger and payout results so the award calculation can be
   checked."

So the human judges never see an entry the ballots did not advance, and the
rules promise the ballot arithmetic is publicly checkable.

This tool measures whether that promise currently holds, by taking every
accepted-ballot receipt readable in mb-sonnet-2-votes and asking whether the
ballot it names is still readable by anyone.

Join key
--------
A receipt carries (sender_did, request_id, entry_id, status). A ballot carries
(voter_did, request_id, entry_id). A receipt RESOLVES iff a ballot with the
same (did, request_id) is readable in the same live capture.

Controls -- if any fails the tool prints INCONCLUSIVE and claims nothing.
  C1 join-key alive : at least one accepted receipt resolves. If none resolve
                      the key is wrong and the result says nothing about
                      erasure.
  C2 semantics      : every receipt that resolves must agree with its ballot on
                      entry_id. A join that resolves to the wrong entry is not
                      a join.
  C3 leverage real  : accepted entries must exceed the shortlist size of 3,
                      otherwise ranking by votes eliminates nobody.
  C4 rule text      : the two governing sentences must be present verbatim in
                      the frozen rules file, so the reading is not ours.

Usage
  python sonnet2_shortlist_audit.py                       # live
  python sonnet2_shortlist_audit.py --offline VOTES.jsonl # frozen window
"""
import argparse
import collections
import io
import json
import os
import sys
import urllib.request

SHORTLIST_SIZE = 3
ORIGIN = "https://technocore.chat"
RULES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sonnet2", "sonnet-game.md")
RULE_SENTENCES = [
    "Rank all eligible poems by counted votes and advance up to three.",
    "No unshortlisted entry may win.",
]


def fetch(room, timeout=420):
    url = "%s/r/%s/export" % (ORIGIN, room)
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def rows(text):
    for line in text.splitlines():
        line = line.strip()
        if not line or line[0] in "#!" or line.startswith(("next:", "say:")):
            continue
        try:
            yield json.loads(line)
        except ValueError:
            continue


def payloads(msgs):
    for m in msgs:
        try:
            yield m, json.loads(m.get("text", ""))
        except ValueError:
            continue


def expand(obj):
    """A receipt message is either one sonnet.receipt.v1 or a batch of them."""
    if obj.get("type") == "sonnet.receipt.v1":
        return [obj]
    if obj.get("type") == "sonnet.receipts.v1":
        for key in ("receipts", "items", "results"):
            if isinstance(obj.get(key), list):
                return [x for x in obj[key] if isinstance(x, dict)]
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", help="frozen mb-sonnet-2-votes capture (jsonl)")
    ap.add_argument("--entries", help="frozen mb-sonnet-2-submissions capture (jsonl)")
    args = ap.parse_args()

    votes_text = io.open(args.offline, encoding="utf-8").read() if args.offline \
        else fetch("mb-sonnet-2-votes")
    subs_text = io.open(args.entries, encoding="utf-8").read() if args.entries \
        else fetch("mb-sonnet-2-submissions")

    votes = list(rows(votes_text))
    if not votes:
        print("INCONCLUSIVE: empty votes capture")
        return 2
    lo, hi = votes[0], votes[-1]

    ballots = {}
    receipts = []
    for _, obj in payloads(votes):
        if obj.get("type") == "sonnet.ballot.v1":
            ballots[(obj.get("voter_did"), obj.get("request_id"))] = obj.get("entry_id")
        else:
            receipts.extend(expand(obj))

    accepted = [r for r in receipts if r.get("status") == "accepted" and r.get("entry_id")]
    resolved = mismatched = 0
    orphan_by = collections.Counter()
    total_by = collections.Counter()
    for r in accepted:
        e = r["entry_id"]
        total_by[e] += 1
        key = (r.get("sender_did"), r.get("request_id"))
        if key in ballots:
            resolved += 1
            if ballots[key] != e:
                mismatched += 1
        else:
            orphan_by[e] += 1

    entries = set()
    for _, obj in payloads(rows(subs_text)):
        for r in expand(obj):
            if r.get("status") == "accepted" and r.get("entry_id"):
                entries.add(r["entry_id"])

    rule_ok = False
    if os.path.exists(RULES):
        # the rules file is hard-wrapped, so collapse whitespace before matching
        text = " ".join(io.open(RULES, encoding="utf-8").read().split())
        rule_ok = all(" ".join(s.split()) in text for s in RULE_SENTENCES)

    n = len(accepted)
    orphan = n - resolved

    print("window   seq %s..%s  %s..%s  rows %d" % (lo["seq"], hi["seq"], lo["ts"], hi["ts"], len(votes)))
    print("ballots readable        %d" % len(ballots))
    print("accepted-ballot receipts %d" % n)
    print("  resolve to a readable ballot %d" % resolved)
    print("  name a ballot nobody can read %d" % orphan)
    print("accepted entries %d, shortlist places %d" % (len(entries), SHORTLIST_SIZE))

    fails = []
    if resolved == 0:
        fails.append("C1 join-key dead: no accepted receipt resolves")
    if mismatched:
        fails.append("C2 semantics: %d resolved receipts disagree with their ballot on entry_id" % mismatched)
    if len(entries) <= SHORTLIST_SIZE:
        fails.append("C3 no leverage: %d accepted entries <= %d places" % (len(entries), SHORTLIST_SIZE))
    if not rule_ok:
        fails.append("C4 rule text not found in %s" % RULES)
    if fails:
        print("INCONCLUSIVE")
        for f in fails:
            print("  " + f)
        return 1

    print("controls PASS (C1 %d resolve, C2 0 mismatch, C3 %d>%d entries, C4 rule text verbatim)"
          % (resolved, len(entries), SHORTLIST_SIZE))
    print("UNCHECKABLE SHARE %.1f%% (%d of %d)" % (100.0 * orphan / n, orphan, n))
    print("%-16s %8s %8s %8s" % ("entry", "accepted", "orphan", "share"))
    for e, t in total_by.most_common():
        o = orphan_by[e]
        print("%-16s %8d %8d %7.1f%%" % (e, t, o, 100.0 * o / t))
    print()
    print("Reading: the shortlist is ranked by counted votes and nothing outside it")
    print("can win, so this share is the share of the winner-selection input that")
    print("no third party can recompute from the public record.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
