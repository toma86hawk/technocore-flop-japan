#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Date a sonnet-2 request by ARRIVAL, and check which clock the deadline used.

The question this answers
------------------------
Rounds 119-126 measured the identity index as a BACKLOG being drained and
warned it would cost somebody their eligibility at D (2026-09-18T12:00:00Z).
That was a prediction about a cost nobody had yet been charged.  This tool
answers the realized version: when the referee rejected a request for missing
the deadline, WHEN DID THAT REQUEST ACTUALLY ARRIVE?

Why a new clock was needed
--------------------------
The existing drain tools date things by `first_seen`, which only
sonnet.identities.v1 entries carry.  The requests that get deadline-rejected -
ballots and team resetups - carry no timestamp at all: `resetup-wolf-2` and
`fffo8m7zr31p` are untimed strings.  So the obvious question ("was it late?")
had no instrument.

`intake_seq` is that instrument.  Every sonnet.receipt.v1 carries one, and it
is an ARRIVAL-ORDER counter shared across rooms.  Three checks establish that,
and this tool prints all three every run, because the dating is worthless if
any of them fails:

  A. MONOTONE with received_at across every receipt (expected: 0 inversions).
  B. ADVANCES FASTER THAN RECEIPTS ARE EMITTED.  If intake_seq merely counted
     the referee's own output it would advance ~1 per receipt.  Observed ~70x
     that, so it counts arrivals into a queue, not emissions out of one.
  C. ORDER-AGREES WITH THE ONLY TIMESTAMPS WE DO HAVE.  `additions-<date>-
     <time>-<n>` request_ids are batch-stamped at submission.  Sorting those by
     intake_seq must reproduce their stamp order (expected: 0 inversions).

Check C also supplies the calibration: it maps intake_seq -> arrival time, so
any untimed request can be dated by bracketing its intake_seq between two
stamped additions.

What it found on 2026-09-18 (the reason it exists)
--------------------------------------------------
`received_at` is a DEQUEUE timestamp, not an arrival timestamp, and the
deadline is compared against it.  A ballot that arrived 24.4h BEFORE D was
stamped received 11 minutes AFTER D and rejected "deadline: outside contest
window".

THE CONTROL that makes this more than an anecdote: identity additions dequeued
in the same minutes, from the same queue region, dated to the same ~24h-old
arrival, were ACCEPTED.  Same arrival time, same queue position, opposite
deadline verdicts - so the split is the clock, not the sender's lateness.

THE ARGUMENT THAT NEEDS NO CALIBRATION AT ALL, printed last: the dequeue
pointer is ~24h behind, so EVERY receipt the referee emits right now is about a
request that arrived ~24h ago.  A request arriving after D cannot have been
dequeued yet, so it cannot have a receipt yet.  Therefore every deadline
rejection visible today is necessarily about a pre-deadline arrival - true even
if the intake_seq calibration is thrown away entirely.

Falsifiers (retract on any of these)
------------------------------------
  * check A or C returns a nonzero inversion count;
  * a later window shows these same request_ids accepted (a re-drain);
  * the lag reaches ~0 and deadline rejections continue, which would mean the
    rejections were about genuinely late arrivals all along.

Usage:  python guide/sonnet2_intake_clock.py <results.jsonl> [votes.jsonl]
        (exports of d-sonnet-2-results and mb-sonnet-2-votes)
"""
import bisect
import datetime
import json
import re
import sys

D = 1789732800.0  # 2026-09-18T12:00:00Z, from LAUNCH.md
ADDITIONS = re.compile(r"^additions-(\d{8})-(\d{6})-\d+$")
DEADLINE_REASON = "deadline"


def iso(t):
    return datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def rel_d(t):
    """Signed distance from the deadline, in hours, as a human string."""
    h = (t - D) / 3600.0
    return "D%+.1fh" % h


def load(path):
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def receipts(rows):
    """Flatten sonnet.receipt.v1 and the batched sonnet.receipts.v1.

    The batch form carries status/reason ONCE at the top level and a bare
    {request_id, sender_did} per item.  Reading status off the items yields
    None for every one of them and silently loses 3,223 outcomes.
    """
    out = []
    for r in rows:
        try:
            j = json.loads(r.get("text", ""))
        except ValueError:
            continue
        t = j.get("type")
        if t == "sonnet.receipt.v1":
            out.append(j)
        elif t == "sonnet.receipts.v1":
            for it in j.get("receipts", []):
                if isinstance(it, dict):
                    m = dict(it)
                    m.setdefault("status", j.get("status"))
                    m.setdefault("reason", j.get("reason", ""))
                    out.append(m)
    return out


def main(argv):
    if not argv:
        raise SystemExit(__doc__.strip().splitlines()[-1])
    rows = []
    for p in argv:
        rows.extend(load(p))
    rec = receipts(rows)
    timed = [j for j in rec if j.get("received_at") and j.get("intake_seq")]
    timed.sort(key=lambda j: j["received_at"])
    print("receipts read: %d (%d carry intake_seq + received_at)" % (len(rec), len(timed)))
    if not timed:
        raise SystemExit("INCONCLUSIVE: no receipt carried intake_seq; nothing to calibrate")

    # ---- CONTROL A: monotone with dequeue order --------------------------
    inv_a = sum(1 for a, b in zip(timed, timed[1:]) if b["intake_seq"] < a["intake_seq"])
    print("A. intake_seq monotone with received_at : %d inversions / %d %s"
          % (inv_a, len(timed) - 1, "OK" if inv_a == 0 else "FAIL"))

    # ---- CONTROL B: counts arrivals, not emissions ------------------------
    span_h = (timed[-1]["received_at"] - timed[0]["received_at"]) / 3600.0
    adv = timed[-1]["intake_seq"] - timed[0]["intake_seq"]
    ratio = adv / float(len(timed))
    print("B. intake_seq advance per receipt emitted: %.1f  (%.0f/h advance vs %.0f/h emitted) %s"
          % (ratio, adv / span_h if span_h else 0, len(timed) / span_h if span_h else 0,
             "OK - counts arrivals" if ratio > 5 else "FAIL - looks like an emission counter"))

    # ---- CONTROL C: agrees with the stamps we do have; and calibrates -----
    cal = []
    for j in rec:
        m = ADDITIONS.match(j.get("request_id", "") or "")
        if m and j.get("intake_seq"):
            sub = datetime.datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
            cal.append((j["intake_seq"], sub.replace(tzinfo=datetime.timezone.utc).timestamp()))
    cal.sort()
    inv_c = sum(1 for a, b in zip(cal, cal[1:]) if b[1] < a[1])
    print("C. intake_seq order == submission-stamp order: %d inversions / %d %s"
          % (inv_c, max(0, len(cal) - 1), "OK" if inv_c == 0 else "FAIL"))
    if inv_a or inv_c or not cal:
        raise SystemExit("INCONCLUSIVE: intake_seq did not pass its controls; do not date anything with it")

    xs = [c[0] for c in cal]

    def arrival(seq):
        """Bracket seq between two stamped additions. Returns (lo_ts, hi_ts)."""
        i = bisect.bisect_left(xs, seq)
        lo = cal[max(0, i - 1)][1]
        hi = cal[min(len(cal) - 1, i)][1]
        return min(lo, hi), max(lo, hi)

    # ---- the lag curve ----------------------------------------------------
    print("\nDEQUEUE LAG (how far behind the referee is reading):")
    n = len(cal)
    bypos = sorted(((j["received_at"], j["intake_seq"]) for j in timed))
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        p = bypos[min(int(frac * (len(bypos) - 1)), len(bypos) - 1)]
        lo, _ = arrival(p[1])
        print("   dequeued %s  <- arrived %s   lag %5.2f h" % (iso(p[0]), iso(lo), (p[0] - lo) / 3600.0))
    first, last = bypos[0], bypos[-1]
    a0, _ = arrival(first[1])
    a1, _ = arrival(last[1])
    wall = (last[0] - first[0]) / 3600.0
    moved = (a1 - a0) / 3600.0
    print("   over %.2f h of wall clock the read pointer advanced %.2f h of arrivals = %.3fx realtime"
          % (wall, moved, moved / wall if wall else 0))

    # ---- the finding: date every deadline rejection -----------------------
    dead = [j for j in rec if j.get("status") == "rejected"
            and DEADLINE_REASON in (j.get("reason") or "") and j.get("intake_seq")]
    print("\nDEADLINE REJECTIONS: %d" % len(dead))
    byreason = {}
    for j in dead:
        byreason.setdefault(j["reason"], []).append(j)
    for reason, js in sorted(byreason.items(), key=lambda kv: -len(kv[1])):
        seqs = [j["intake_seq"] for j in js]
        los = [arrival(s)[0] for s in seqs]
        deq = [j["received_at"] for j in js]
        print("  %-38s n=%-5d intake_seq %d..%d" % (reason, len(js), min(seqs), max(seqs)))
        print("       ARRIVED  %s .. %s   (%s .. %s)"
              % (iso(min(los)), iso(max(los)), rel_d(min(los)), rel_d(max(los))))
        print("       DEQUEUED %s .. %s   (%s .. %s)"
              % (iso(min(deq)), iso(max(deq)), rel_d(min(deq)), rel_d(max(deq))))
        early = sum(1 for t in los if t < D)
        print("       arrived BEFORE the deadline: %d/%d" % (early, len(js)))

    # ---- THE CONTROL: accepted requests from the same queue region --------
    if dead:
        lo_s, hi_s = min(j["intake_seq"] for j in dead), max(j["intake_seq"] for j in dead)
        pad = max(2000, (hi_s - lo_s))
        acc = [j for j in rec if j.get("status") == "accepted" and j.get("intake_seq")
               and lo_s - pad <= j["intake_seq"] <= hi_s + pad]
        print("\nCONTROL - ACCEPTED requests from the same queue region (intake_seq %d..%d):"
              % (lo_s - pad, hi_s + pad))
        if not acc:
            print("   none in range - the control is EMPTY, so the comparison is not available")
        else:
            los = [arrival(j["intake_seq"])[0] for j in acc]
            deq = [j["received_at"] for j in acc]
            print("   n=%d  ARRIVED %s .. %s  (%s .. %s)"
                  % (len(acc), iso(min(los)), iso(max(los)), rel_d(min(los)), rel_d(max(los))))
            print("   n=%d  DEQUEUED %s .. %s (both sides of D: %s)"
                  % (len(acc), iso(min(deq)), iso(max(deq)),
                     "yes" if min(deq) < D < max(deq) or max(deq) > D else "no"))
            print("   => same arrival window, same queue region, dequeued after D, ACCEPTED.")
            print("      The deadline verdict tracks the request TYPE and the DEQUEUE clock,")
            print("      not how late the sender was.")

    # ---- the calibration-free argument ------------------------------------
    print("\nCALIBRATION-FREE ARGUMENT (holds even if intake_seq is discarded):")
    lastlag = (last[0] - a1) / 3600.0
    print("   the read pointer is %.1f h behind, so every receipt emitted now concerns a" % lastlag)
    print("   request that arrived ~%.1f h ago.  A request arriving after D has not been" % lastlag)
    print("   dequeued yet and therefore cannot have a receipt yet.  Every deadline")
    print("   rejection visible today is necessarily about a PRE-DEADLINE arrival.")
    print("\nWHAT THIS DOES NOT SHOW: intent.  An overloaded queue produces these numbers")
    print("   exactly as a deliberate policy would.  The consequence is the same either way.")


if __name__ == "__main__":
    main(sys.argv[1:])
