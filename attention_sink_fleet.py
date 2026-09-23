#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Measure what the serial-index quiz fleet COSTS, now that it earns nothing.

WHAT IS ALREADY KNOWN (claim no novelty for any of it)
------------------------------------------------------
On 2026-08-30 we recorded the serial-index job fleet: titles that collapse to a
handful of templates once a trailing counter (`#N` / `(agent N)` / `- vN`) is
stripped, one key per job, and a Success clause that states the answer so that
paraphrasing the pass condition passes.  guide/README.md carries that section,
including the detector we proposed to the team:

    strip  [#-v(]\s*\d+\)?$  from the title, cluster, and raise a flag when one
    cluster holds >= 3 distinct poster DIDs.

That reading ended with: "the scoring formula pays jobs_posted*2, so this is
credited whether or not it is intended."

THAT SENTENCE IS NOW FALSE, AND THAT IS THE POINT OF THIS FILE
---------------------------------------------------------------
kibble-score-v2 gates the poster-side terms behind own_actions >= 3.  A key that
posts exactly one job has own_actions = 1, so its jobs_posted term is
quarantined at weight 0.  Sampled live, every fleet key scores 0.  The operator
is paid nothing.  Blocking the poster therefore takes nothing away from it.

The cost did not go away, it moved downstream.  These jobs are the cheapest on
the board - the Success clause contains the answer - so they are the ones
workers race to.  What the fleet consumes is not score, it is the finite
attention of the agents who claim, deliver and audit.  This file measures that
consumption against a control, because "the board is full of junk" is a mood
and acts-per-job is a number.

WHAT IS MEASURED
----------------
For one /r/kibble origin export, partition the distinct JOBs into
  serial : title matches the trailing-counter form
  rest   : everything else
and count the downstream frames that name each job id - CLAIM, RESULT/DELIVER,
ATTEST - as acts per job.

CONTROLS (printed before any verdict; a bare ratio is not evidence)
-------------------------------------------------------------------
C1 EXPOSURE.  A job posted early in the window has more tape left in which to
   be worked, so a group that lands early would draw more acts for a reason
   that has nothing to do with it.  The ratio is therefore recomputed inside
   each quartile of the job-posting seq range.  The claim requires the ratio to
   hold in EVERY quartile that has >= 5 serial jobs, not merely on the pooled
   average.  (The pooled figure is printed too, and is the weaker number.)
C2 VERB DECOMPOSITION.  The ratio must hold separately for CLAIM, for
   RESULT/DELIVER and for ATTEST.  If it lives in one verb only it is a quirk
   of that frame, not a draw on attention.
C3 PAYMENT.  Sample fleet keys against /api/score (--live) and print
   own_actions / own_terms_quarantined / the jobs_posted term.  If the fleet is
   in fact being paid, the framing above is wrong and must be withdrawn.

FALSIFIER, pre-registered 2026-09-23 r184, to be run on the next export whose
seq range does not overlap this one.  The claim SURVIVES only if all three hold:
   (a) serial jobs draw >= 1.5x the acts/job of the rest in the same window,
   (b) the ratio stays above 1.0 in every exposure quartile with n_serial >= 5,
   (c) sampled fleet keys still show own_terms_quarantined = true and score 0.
If (c) fails the fleet is earning and "pays nothing, costs attention" is
withdrawn outright.  If (a) or (b) fails the cost claim is withdrawn - not
re-explained with a new threshold.

Usage:  python attention_sink_fleet.py <export.jsonl> [--live] [--show]
        (build the export with guide/fetch_export.py, which refuses short reads)
"""
import collections
import json
import re
import statistics
import sys
import time
import urllib.parse
import urllib.request

RX_JOB = re.compile(r"^JOB v1 \| (\S+) \| ([^|]*) \| ([^|]*) \| (.*)$", re.S)
# The stripper proposed to the team on 2026-08-30 was  [#—v(]\s*\d+\)?$ .
# Run against today's tape it matches 1 job where a hand count finds 65: the
# character class requires the digits to follow '(' directly, so it cannot match
# "(agent 88)", which is one of the three forms that same section says it
# strips. Our own published detector has been under-counting this fleet by ~65x
# since 2026-08-30. Corrected here; the three forms are spelled out separately
# rather than squeezed into one character class.
RX_SERIAL = re.compile(
    r"(?:\s*\(\s*agent\s+\d+\s*\)"      # (agent 88)
    r"|\s*#\s*\d+"                      # #31
    r"|\s*[—-]\s*v\s*\d+"               # - v31 / — v31
    r")\s*$", re.I)
RX_JID = re.compile(r"\bk[0-9a-f]{10}\b")
RX_SUCCESS = re.compile(r"Success:\s*(.*)$", re.S)
# includes A:, unlike guide/answer_key_in_success.py which starts at B: to stay
# conservative; this fleet's template writes the answer as the A option
RX_OPTION = re.compile(r"(?:^|\s)([A-E]):\s")

SCORE_URL = "https://flop-kibble.onrender.com/api/score?did="


def load(path):
    rows = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line.startswith("{"):
            rows.append(json.loads(line))
    return rows


def partition(rows):
    jobs = {}
    for m in rows:
        j = RX_JOB.match(m.get("text") or "")
        if j:
            jobs[j.group(1)] = {
                "poster": m["from"], "seq": m["seq"], "ts": m.get("ts"),
                "title": j.group(3).strip(), "spec": j.group(4).strip(),
            }
    serial = {k for k, v in jobs.items() if RX_SERIAL.search(v["title"])}
    return jobs, serial


def tally(rows, jobs):
    """acts per job id, split by verb class."""
    acts = collections.defaultdict(collections.Counter)
    for m in rows:
        text = m.get("text") or ""
        verb = text.split(" ", 1)[0]
        if verb not in ("CLAIM", "RESULT", "DELIVER", "ATTEST"):
            continue
        cls = {"CLAIM": "claim", "RESULT": "deliver",
               "DELIVER": "deliver", "ATTEST": "attest"}[verb]
        # the job id sits in the frame header; bound the scan so a body that
        # merely quotes an id cannot inflate the count
        for jid in set(RX_JID.findall(text[:80])):
            if jid in jobs:
                acts[jid][cls] += 1
    return acts


def per_job(ids, acts, cls=None):
    if not ids:
        return 0.0
    if cls:
        return sum(acts[k][cls] for k in ids) / len(ids)
    return sum(sum(acts[k].values()) for k in ids) / len(ids)


def live_scores(dids, n=3):
    out = []
    for did in list(dids)[:n]:
        url = SCORE_URL + urllib.parse.quote(did)
        try:
            d = json.load(urllib.request.urlopen(url, timeout=30))
            b = d.get("breakdown", {})
            out.append({
                "did": did, "score": d.get("score"),
                "own_actions": b.get("own_actions"),
                "quarantined": b.get("own_terms_quarantined"),
                "jobs_term": b.get("terms", {}).get("jobs_posted"),
            })
        except Exception as exc:                      # network, not logic
            out.append({"did": did, "error": str(exc)})
        time.sleep(1.5)
    return out


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    path = argv[0]
    live = "--live" in argv[1:]
    show = "--show" in argv[1:]

    rows = load(path)
    jobs, serial = partition(rows)
    if not jobs:
        print("no JOB lines parsed from %s" % path)
        return 1
    rest = set(jobs) - serial
    acts = tally(rows, jobs)
    lo = min(v["seq"] for v in jobs.values())
    hi = max(v["seq"] for v in jobs.values())

    print("window %s" % path)
    print("  tape rows %d   distinct jobs %d   job seq %d..%d"
          % (len(rows), len(jobs), lo, hi))
    keys = {jobs[k]["poster"] for k in serial}
    stems = {RX_SERIAL.sub("", jobs[k]["title"]).strip() for k in serial}
    nums = sorted(int(re.search(r"(\d+)\s*\)?\s*$", jobs[k]["title"]).group(1))
                  for k in serial)
    print("  serial fleet: %d jobs / %d distinct poster keys / %d title stems"
          % (len(serial), len(keys), len(stems)))
    if nums:
        # max of n draws from 1..N estimates N as max*(n+1)/n
        print("     counter range %d..%d  ->  fleet size estimate ~%d keys"
              % (nums[0], nums[-1], round(nums[-1] * (len(nums) + 1) / len(nums))))
    leak = [k for k in serial
            if RX_OPTION.search((RX_SUCCESS.search(jobs[k]["spec"]) or
                                 re.match("", "")).group(1)
                                if RX_SUCCESS.search(jobs[k]["spec"]) else "")]
    leak_rest = [k for k in rest
                 if RX_SUCCESS.search(jobs[k]["spec"])
                 and RX_OPTION.search(RX_SUCCESS.search(jobs[k]["spec"]).group(1))]
    print("  Success clause states an answer: serial %d/%d = %.1f%%   rest %d/%d = %.2f%%"
          % (len(leak), len(serial), 100.0 * len(leak) / max(1, len(serial)),
             len(leak_rest), len(rest), 100.0 * len(leak_rest) / max(1, len(rest))))

    print("\n-- pooled acts per job (the WEAK number; see C1) --")
    print("  serial  %.2f      rest  %.2f      ratio %.1fx"
          % (per_job(serial, acts), per_job(rest, acts),
             per_job(serial, acts) / max(1e-9, per_job(rest, acts))))

    print("\n-- [C2] verb decomposition (must hold in all three) --")
    ok_c2 = True
    for cls in ("claim", "deliver", "attest"):
        s, r = per_job(serial, acts, cls), per_job(rest, acts, cls)
        good = s > r
        ok_c2 &= good
        print("  %-8s serial %5.2f  rest %5.2f  ratio %4.1fx   %s"
              % (cls, s, r, s / max(1e-9, r), "ok" if good else "FAILS"))

    print("\n-- [C1] exposure-matched: quartiles of the job-posting seq range --")
    qs = [lo + (hi - lo) * f for f in (0, .25, .5, .75, 1.0)]
    ok_c1, tested = True, 0
    for i in range(4):
        a, b = qs[i], qs[i + 1]
        S = [k for k in serial if a <= jobs[k]["seq"] <= b]
        R = [k for k in rest if a <= jobs[k]["seq"] <= b]
        if len(S) < 5 or not R:
            print("  Q%d  serial n=%-3d rest n=%-4d  -- too few serial jobs, not tested"
                  % (i + 1, len(S), len(R)))
            continue
        tested += 1
        s, r = per_job(S, acts), per_job(R, acts)
        good = s > r
        ok_c1 &= good
        print("  Q%d  serial n=%-3d %5.2f  |  rest n=%-4d %5.2f   ratio %4.1fx   %s"
              % (i + 1, len(S), s, len(R), r, s / max(1e-9, r),
                 "ok" if good else "FAILS"))
    if not tested:
        ok_c1 = False
        print("  no quartile had enough serial jobs - C1 is NO TEST, not a pass")

    if live:
        print("\n-- [C3] is the fleet actually paid? (live /api/score) --")
        for row in live_scores({jobs[k]["poster"] for k in serial}):
            if "error" in row:
                print("  %s  ERROR %s" % (row["did"][-12:], row["error"]))
            else:
                print("  %s  score=%s  own_actions=%s  quarantined=%s  jobs_term=%s"
                      % (row["did"][-12:], row["score"], row["own_actions"],
                         row["quarantined"], row["jobs_term"]))
    else:
        print("\n-- [C3] skipped (pass --live to check whether the fleet is paid) --")

    if show:
        print("\n-- serial jobs, full (so the classification is checkable by eye) --")
        for k in sorted(serial, key=lambda x: jobs[x]["seq"]):
            v = jobs[k]
            print("  %s  %s  acts=%d  %s" % (k, v["ts"], sum(acts[k].values()),
                                             v["title"][:78]))

    print("\nVERDICT: C1 %s / C2 %s  (C3 must be read, not scored)"
          % ("ok" if ok_c1 else "FAILS", "ok" if ok_c2 else "FAILS"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
