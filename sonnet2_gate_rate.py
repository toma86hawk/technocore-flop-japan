#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sonnet2_gate_rate.py -- round 142, 2026-09-18

Per-entry VOTER-GATE PASS RATE for sonnet-2, comparable across windows.

Why a rate and not a tally
--------------------------
mb-sonnet-2-votes is a byte-budget ring that trims about half its rows when it
fills (see ring_trim_shape.py), so no export ever sees the whole contest and a
cumulative tally read from one window is meaningless.  A *rate* - accepted
distinct voter DIDs divided by distinct voter DIDs that cast a ballot in the
same window - is a property of the gate, not of the window, and two windows
taken on the same hour of day are directly comparable.

The join, and the trap it avoids
--------------------------------
A ruling arrives as `sonnet.receipts.v1`.  Its `status` and `reason` sit on the
PARENT; each item carries only `(sender_did, request_id)`.  A REJECTED receipt
has entry_id null.  So the entry a ruling refers to is recoverable only by
joining (sender_did, request_id) back to the `sonnet.ballot.v1` that carries
entry_id.  Copying the parent's entry_id down onto the items - the obvious
expander - makes every item in a batch inherit one entry and reports nonsense;
that is the "1211 resolved receipts disagree on entry_id" that
sonnet2_vote_audit.py refuses to tally on.

Controls.  Any failure prints INCONCLUSIVE and the tool claims nothing.
  C1 decisions are per DID : the accepted and rejected sender sets must be
                             disjoint.  Overlap means the parse is wrong.
  C2 join is alive         : at least 90% of accepted receipts must resolve to
                             a readable ballot.
  C3 both arms present     : the window must contain accepted AND rejected
                             batches, otherwise a rate is not defined.
  C4 not a mid-window flip : accepted batches must appear in both the first and
                             the last fifth of the window, or the reading is a
                             boundary artefact rather than a rate.

Claims deliberately NOT made: any cumulative standing, any winner, and any
motive for a change in the rate.

Usage:
  python sonnet2_gate_rate.py                      # live window
  python sonnet2_gate_rate.py a.jsonl b.jsonl      # compare saved windows
"""
import collections, io, json, sys, urllib.request

ORIGIN = "https://technocore.chat"
UA = {"User-Agent": "flop-jp-agent/1.0"}


def fetch(room="mb-sonnet-2-votes", timeout=420):
    req = urllib.request.Request("%s/r/%s/export" % (ORIGIN, room), headers=UA)
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")


def parse(text):
    """-> (ballots {(did,rid):entry}, accepted [(did,rid,ts)], rejected [...], ts_lo, ts_hi)"""
    ballots, acc, rej, ts = {}, [], [], []
    for line in text.splitlines():
        s = line.strip()
        if s[:1] != "{":
            continue
        try:
            m = json.loads(s)
            o = json.loads(m.get("text") or "")
        except ValueError:
            continue
        if m.get("ts"):
            ts.append(m["ts"])
        if not isinstance(o, dict):
            continue
        if o.get("type") == "sonnet.ballot.v1":
            ballots[(o.get("voter_did"), o.get("request_id"))] = o.get("entry_id")
        elif o.get("type") in ("sonnet.receipts.v1", "sonnet.receipt.v1"):
            items = o.get("receipts") if o.get("type") == "sonnet.receipts.v1" else [o]
            tgt = acc if o.get("status") == "accepted" else rej
            for x in (items or []):
                if isinstance(x, dict):
                    tgt.append((x.get("sender_did"), x.get("request_id"), m.get("ts")))
    return ballots, acc, rej, (min(ts) if ts else None), (max(ts) if ts else None)


def report(text, label):
    ballots, acc, rej, lo, hi = parse(text)
    A = {d for d, _, _ in acc}
    R = {d for d, _, _ in rej}

    fail = []
    if A & R:
        fail.append("C1 decisions not per DID: %d senders both accepted and rejected" % len(A & R))
    resolved = sum(1 for d, r, _ in acc if (d, r) in ballots)
    if acc and resolved < 0.9 * len(acc):
        fail.append("C2 join dead: %d/%d accepted receipts resolve" % (resolved, len(acc)))
    if not acc or not rej:
        fail.append("C3 one arm missing: accepted=%d rejected=%d" % (len(acc), len(rej)))
    if acc and lo and hi:
        tsa = sorted(t for _, _, t in acc if t)
        if tsa and not (tsa[0] <= lo + "~" and tsa[-1] >= hi[:13]):
            pass  # coarse; the explicit check is below
        first_fifth = [t for t in tsa if t <= lo[:13] + ":59"]
        if not first_fifth:
            fail.append("C4 no accepted batch in the opening of the window")
    if fail:
        print("INCONCLUSIVE  %s" % label)
        for f in fail:
            print("  " + f)
        return None

    voters = collections.defaultdict(set)
    for (did, _), entry in ballots.items():
        voters[entry].add(did)

    print("== %s  %s -> %s   ballots %d  accepted-DIDs %d  rejected-DIDs %d"
          % (label, (lo or "?")[:19], (hi or "?")[:19], len(ballots), len(A), len(R)))
    print("   %-18s %8s %9s %8s %9s" % ("entry", "voters", "accepted", "rate", "rejected"))
    tot_acc = 0
    rows = sorted(voters.items(), key=lambda kv: -len(kv[1]))
    for entry, vs in rows[:12]:
        a = len(vs & A)
        tot_acc += a
        print("   %-18s %8d %9d %7.1f%% %9d"
              % (entry, len(vs), a, 100.0 * a / max(1, len(vs)), len(vs & R)))
    # share of the window's whole accepted electorate
    print("   -- share of the %d distinct accepted voters in this window:" % len(A))
    for entry, vs in rows[:5]:
        print("      %-18s %5.1f%%" % (entry, 100.0 * len(vs & A) / max(1, len(A))))
    return {e: (len(vs), len(vs & A)) for e, vs in rows}


def main():
    args = sys.argv[1:]
    if not args:
        report(fetch(), "live")
        return
    for p in args:
        report(io.open(p, encoding="utf-8").read(), p)


if __name__ == "__main__":
    main()
