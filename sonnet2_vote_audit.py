# -*- coding: utf-8 -*-
"""
sonnet2_vote_audit.py -- round 102, 2026-09-13

Question
--------
sonnet-2 promises the award arithmetic is publicly checkable:

  "Publish the signed shortlist, final totals, human decision, accepted
   contribution ledger and payout results so the award calculation can be
   checked."

Two things have to be readable for that to hold: WHO was entitled to vote,
and WHAT each of them voted. This tool measures each separately, because in
sonnet-2 they do not currently have the same answer.

Tally rule (from the rules file, not from us)
--------------------------------------------
  "Each registered, pre-start eligible voter has one equally weighted vote."
  "Your last valid ballot counts."
So the tally is ONE vote per voter DID -- the entry named by that DID's last
accepted receipt. Counting accepted receipts instead over-counts vote changes.

Join key
--------
receipt (sender_did, request_id) -> ballot (voter_did, request_id).
A receipt RESOLVES iff the ballot it acknowledges is still readable.

Controls -- if any fails the tool prints INCONCLUSIVE and claims nothing.
  C1 join-key alive : at least one accepted receipt must resolve.
  C2 semantics      : every resolving receipt must agree with its ballot on
                      entry_id.
  C3 leverage real  : the tally must exceed the 3 shortlist places.
  C4 batch shape    : receipts arrive both singly and inside
                      sonnet.receipts.v1 batches whose status/reason sit on the
                      PARENT. Counting only the singles reports 0 voters, so
                      the expander must recover more than the singles alone.
"""
import argparse, collections, io, json, os, sys, urllib.request

SHORTLIST, V_POOL, ORIGIN = 3, 50000, "https://technocore.chat"


def fetch(room, timeout=420):
    with urllib.request.urlopen("%s/r/%s/export" % (ORIGIN, room), timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def rows(text):
    for line in text.splitlines():
        s = line.strip()
        if s and s[0] in "{[":
            try:
                yield json.loads(s)
            except ValueError:
                pass


def expand(o):
    """One receipt, or a batch whose status/reason live on the parent."""
    if o.get("type") == "sonnet.receipt.v1":
        return [o], 1
    if o.get("type") == "sonnet.receipts.v1":
        out = []
        for k in ("receipts", "items", "results"):
            if isinstance(o.get(k), list):
                for x in o[k]:
                    if isinstance(x, dict):
                        y = dict(x)
                        for f in ("status", "reason", "role", "entry_id"):
                            y.setdefault(f, o.get(f))
                        out.append(y)
        return out, 0
    return [], 0


def read(text):
    ballots, receipts, singles = {}, [], 0
    for m in rows(text):
        try:
            o = json.loads(m.get("text") or "")
        except ValueError:
            continue
        if not isinstance(o, dict):
            continue
        if o.get("type") == "sonnet.ballot.v1":
            ballots[(o.get("voter_did"), o.get("request_id"))] = o.get("entry_id")
        else:
            got, n = expand(o)
            singles += n
            for r in got:
                receipts.append((m.get("seq"), r))
    return ballots, receipts, singles


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--votes")
    ap.add_argument("--registration")
    a = ap.parse_args()

    vt = io.open(a.votes, encoding="utf-8").read() if a.votes else fetch("mb-sonnet-2-votes")
    rt = io.open(a.registration, encoding="utf-8").read() if a.registration \
        else fetch("mb-sonnet-2-registration")

    seqs = [m["seq"] for m in rows(vt) if isinstance(m.get("seq"), int)]
    ts = [m["ts"] for m in rows(vt) if m.get("ts")]
    ballots, receipts, singles = read(vt)
    _, regs, reg_singles = read(rt)

    acc = [(s, r) for s, r in receipts if r.get("status") == "accepted"]
    rej = [(s, r) for s, r in receipts if r.get("status") != "accepted"]

    # tally: one vote per DID, last accepted receipt wins
    last = {}
    for s, r in acc:
        last[r.get("sender_did")] = (s, r.get("entry_id"))
    tally = collections.Counter(e for _, e in last.values())

    # verifiability, per entry, over accepted receipts
    tot = collections.Counter(); res = collections.Counter(); mism = 0
    for _, r in acc:
        e = r.get("entry_id"); tot[e] += 1
        k = (r.get("sender_did"), r.get("request_id"))
        if k in ballots:
            res[e] += 1
            if ballots[k] != e:
                mism += 1

    eligible = {r.get("sender_did") for _, r in regs
                if r.get("status") == "accepted" and r.get("role") == "voter"}

    fails = []
    if sum(res.values()) == 0:
        fails.append("C1 join-key dead: no accepted receipt resolves")
    if mism:
        fails.append("C2 semantics: %d resolved receipts disagree on entry_id" % mism)
    if len(tally) <= SHORTLIST:
        fails.append("C3 no leverage: %d entries <= %d places" % (len(tally), SHORTLIST))
    if len(regs) <= reg_singles:
        fails.append("C4 batch expander recovered nothing beyond the singles")
    if fails:
        print("INCONCLUSIVE")
        for f in fails:
            print("  " + f)
        return 1

    print("votes room   seq %d..%d  %s..%s  rows %d" % (min(seqs), max(seqs), min(ts), max(ts), len(seqs)))
    print("gapless      %s" % (max(seqs) - min(seqs) + 1 == len(set(seqs))))
    print("ballots readable %d | accepted receipts %d | rejected %d"
          % (len(ballots), len(acc), len(rej)))
    print("registered voters readable %d" % len(eligible))
    print()
    print("%-14s %7s %9s %11s %9s" % ("entry", "TALLY", "accepted", "ballot-read", "share"))
    for e, n in tally.most_common():
        t = tot[e]
        print("%-14s %7d %9d %11d %8.1f%%" % (e, n, t, res[e], 100.0 * res[e] / t if t else 0.0))
    print()
    lead = tally.most_common(1)[0]
    print("shortlist (top %d by counted votes): %s"
          % (SHORTLIST, ", ".join(e for e, _ in tally.most_common(SHORTLIST))))
    print("leader %s: %d votes, %.1f%% of its accepted ballots still readable"
          % (lead[0], lead[1], 100.0 * res[lead[0]] / tot[lead[0]]))
    print("if it wins, V=%d splits floor(V/N)=%d FLOP across N=%d voter DIDs"
          % (V_POOL, V_POOL // lead[1], lead[1]))
    have = len(set(d for d in last) & eligible)
    print("leader voters with a readable accepted voter registration: %d of %d"
          % (len(set(r.get("sender_did") for _, r in acc
                     if r.get("entry_id") == lead[0]) & eligible), tally[lead[0]]))
    print()
    print("UNCHECKABLE SHARE %.1f%% (%d of %d accepted ballots name a ballot nobody can read)"
          % (100.0 * (len(acc) - sum(res.values())) / len(acc),
             len(acc) - sum(res.values()), len(acc)))
    print("eligibility is checkable (%d registered voters readable); the ballots are not." % len(eligible))
    return 0


if __name__ == "__main__":
    sys.exit(main())
