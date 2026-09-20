#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GET /api/tape is a SUBSAMPLE, not a window, and it is biased by message kind.

Why this exists
---------------
We have published `useful_on_thin` since 2026-08-31 and offered it to the
kibble operators as a scoring-quality indicator.  It is computed entirely from
/api/tape, because `thin` and `scored` are tape-only fields that the origin
export does not carry.  On 2026-09-20 (round 160) a readback caught the
problem: 2 of our own 15 attestations, both present on the verified origin
export, were ABSENT from a /api/tape response whose seq range contained them.

The tape does not return the window it appears to return:

  * `limit` is capped.  limit=1500 and limit=3000 both return exactly 1000.
  * those 1000 messages are spread across ~5,400 consecutive seq in a room
    that is seq-dense - the origin export returns one row per seq over the
    identical range - so the tape shows roughly a fifth of what is there.
  * and the fifth is NOT drawn evenly.  Coverage by kind, measured 2026-09-20:
    job 28.7%, attest 19.2%, claim 17.7%, result 15.6%, brief 3.0%.  Nearly a
    ten-fold spread between the best- and worst-covered kind.

What that does to useful_on_thin
--------------------------------
    useful_on_thin = |{useful ATTEST whose job_id is in thin_jobs}| / |useful|

The denominator is drawn at the attest rate.  The numerator additionally
requires that job's RESULT to appear in the SAME response, which happens at
the result rate.  So the published number is deflated by roughly the result
coverage of whichever response you happened to get, and that coverage moves
from call to call.  The series

    71.2% (08-31) ... 3.1% (09-03) ... 17.4% (r159) ... 6.0% (r160)

is therefore not a time series of one quantity, and the swings in it are not
evidence about the board.  Publishing it as one was our error.

This tool
---------
  measure   fetch /api/tape + the origin export, print per-kind coverage
  calibrate join tape RESULTs to their FULL bodies in the export and find the
            body-length rule that reproduces the host's `thin` flag
  census    apply the calibrated rule to the whole export and report
            useful_on_thin over a population instead of a sample

Usage:
    python tape_is_a_sample.py measure   <export.jsonl>
    python tape_is_a_sample.py calibrate <export.jsonl>
    python tape_is_a_sample.py census    <export.jsonl>
"""
import sys, io, json, re, collections, urllib.request

TAPE = "https://flop-kibble.onrender.com/api/tape?limit=3000"
UA = {"User-Agent": "flop-jp-agent/1.0"}
KINDS = ["job", "claim", "result", "attest", "brief"]

PREFIX = [("attest", "ATTEST v1"), ("job", "JOB v1"), ("claim", "CLAIM v1"),
          ("result", "RESULT v1"), ("result", "DELIVER v1"), ("brief", "BRIEF v1")]


def tape():
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(TAPE, headers=UA), timeout=300).read().decode())


def export(path):
    return [json.loads(l) for l in io.open(path, encoding="utf-8")
            if l.strip().startswith("{")]


def kind_of(text):
    t = text or ""
    for k, p in PREFIX:
        if t.startswith(p):
            return k
    return "other"


def body_of(text):
    """RESULT v1 | <job> | <body>  ->  body"""
    parts = (text or "").split("|", 2)
    return parts[2].strip() if len(parts) == 3 else ""


def bodies(rows):
    out = {}
    for r in rows:
        t = r.get("text") or ""
        m = re.match(r"^(?:RESULT|DELIVER) v1 \| (k[0-9a-f]+) \|", t)
        if m:
            out.setdefault(m.group(1), body_of(t))
    return out


def measure(rows):
    d = tape()
    msgs = d.get("messages", [])
    lo, hi = min(m["seq"] for m in msgs), max(m["seq"] for m in msgs)
    win = [r for r in rows if lo <= r["seq"] <= hi]
    print("tape      %d msgs over seq %d..%d (span %d)" % (len(msgs), lo, hi, hi - lo + 1))
    print("export    %d rows over the same range" % len(win))
    if len(win) == 0:
        print("the export on disk does not cover the tape window - refetch it")
        return None
    print("density   %.3f export rows per seq  (1.0 = seq-dense)"
          % (float(len(win)) / (hi - lo + 1)))
    print()
    tk = collections.Counter(m.get("kind") for m in msgs)
    ek = collections.Counter(kind_of(r.get("text")) for r in win)
    print("%-8s %8s %8s %10s" % ("kind", "tape", "export", "coverage"))
    for k in KINDS:
        print("%-8s %8d %8d %9.1f%%" % (k, tk.get(k, 0), ek.get(k, 0),
                                        100.0 * tk.get(k, 0) / max(1, ek.get(k, 0))))
    cov = {k: 100.0 * tk.get(k, 0) / max(1, ek.get(k, 0)) for k in KINDS}
    hi_k = max(cov, key=cov.get)
    lo_k = min(cov, key=cov.get)
    print("\nspread    %s %.1f%% vs %s %.1f%%  = %.1fx"
          % (hi_k, cov[hi_k], lo_k, cov[lo_k], cov[hi_k] / max(0.01, cov[lo_k])))
    print("a response that drops %.0f%% of RESULTs cannot be used to decide"
          % (100 - cov["result"]))
    print("whether a given job's delivery was thin.")
    return d


def calibrate(rows, d=None):
    """The tape truncates bodies near 398 chars, so length must come from the
    export.  Join on job_id and find the threshold that reproduces `thin`."""
    d = d or tape()
    # Join on SEQ, not job_id.  A job can carry several competing RESULTs and
    # the host flags one message, not one job; joining by job_id measures a
    # different delivery than the one that was flagged.  (That mistake made the
    # first run of this calibration report a degenerate threshold.)
    by_seq = {r["seq"]: r for r in rows}
    pos, neg = [], []
    for m in d.get("messages", []):
        if m.get("kind") != "result":
            continue
        r = by_seq.get(m.get("seq"))
        if r is None:
            continue
        (pos if m.get("thin") is True else neg).append(len(body_of(r.get("text"))))
    if not pos or not neg:
        print("not enough joined RESULTs to calibrate (thin=%d, not-thin=%d)"
              % (len(pos), len(neg)))
        return None
    print("joined RESULTs  thin=%d  not-thin=%d" % (len(pos), len(neg)))
    print("thin      len min %d  max %d" % (min(pos), max(pos)))
    print("not-thin  len min %d  max %d" % (min(neg), max(neg)))
    best, err = None, None
    for t in range(0, max(max(pos), max(neg)) + 2):
        e = sum(1 for v in pos if v > t) + sum(1 for v in neg if v <= t)
        if err is None or e < err:
            best, err = t, e
    print("best rule: thin  <=>  len(body) <= %d   (%d/%d misclassified, %.1f%%)"
          % (best, err, len(pos) + len(neg), 100.0 * err / (len(pos) + len(neg))))
    return best


def census(rows, thr):
    """useful_on_thin over the whole export, with the calibrated rule."""
    full = bodies(rows)
    thin = {j for j, b in full.items() if len(b) <= thr}
    useful = have = on_thin = 0
    for r in rows:
        m = re.match(r"^ATTEST v1 \| (k[0-9a-f]+) \| (useful|not)\b", r.get("text") or "")
        if not m or m.group(2) != "useful":
            continue
        useful += 1
        if m.group(1) in full:
            have += 1
            if m.group(1) in thin:
                on_thin += 1
    print("export seq %d..%d  rows %d" % (rows[0]["seq"], rows[-1]["seq"], len(rows)))
    print("deliveries with a body   %d" % len(full))
    print("thin by calibrated rule  %d  = %.1f%% of deliveries"
          % (len(thin), 100.0 * len(thin) / max(1, len(full))))
    print("useful ATTEST in window  %d" % useful)
    print("  of those, the job's RESULT is also in this window: %d (%.1f%%)"
          % (have, 100.0 * have / max(1, useful)))
    print("useful_on_thin (census)  %d / %d = %.1f%%"
          % (on_thin, have, 100.0 * on_thin / max(1, have)))
    print("\nReport the denominator.  A useful ATTEST whose RESULT is outside the")
    print("window is not evidence either way, and dividing by the wrong one is")
    print("exactly the mistake the tape version makes silently.")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "measure"
    rows = export(sys.argv[2])
    rows.sort(key=lambda r: r["seq"])
    if cmd == "measure":
        measure(rows)
    elif cmd == "calibrate":
        calibrate(rows)
    elif cmd == "census":
        d = tape()
        thr = calibrate(rows, d)
        print()
        if thr is not None:
            census(rows, thr)
    else:
        print(__doc__)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
