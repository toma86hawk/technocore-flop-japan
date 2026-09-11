#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""thin_two_numbers.py - useful_on_thin was one number doing two jobs. Split it.

WHY THIS EXISTS
---------------
We proposed `useful_on_thin` to the FLOP team: of all `useful` verdicts in a tape
window, what share landed on deliveries the host itself flagged `thin` and left
`scored: false`? The intent was to measure whether auditors rubber-stamp filler.

The series we published swings violently - 0.0%, 39.1%, 6.5%, 32.0%, 9.3%, 27.9%,
2.1% - and we kept writing "a single window is not a trend" under it. That caveat
was true but it was not the real problem. The real problem is that the metric is a
PRODUCT of two independent quantities and its denominator belongs to neither:

    useful_on_thin  =  (useful verdicts on thin jobs) / (ALL useful verdicts)

The numerator can fall because auditors got stricter about filler, OR because no
auditor looked at a thin delivery at all. Those are opposite conclusions and the
single number cannot tell them apart. The denominator - board-wide useful verdicts -
has nothing to do with thin exposure, so it adds a third source of movement.

THE DECOMPOSITION
-----------------
    thin_coverage    = thin jobs receiving ANY verdict / thin jobs        "did anyone look?"
    thin_accept_rate = useful verdicts on thin jobs / ALL verdicts on thin jobs
                                                                          "what did they say?"

Worked example, 2026-09-11, two consecutive three-hour tape windows:

    12:19 JST   useful_on_thin 27.9%   coverage 24.1%   accept 70.6%
    15:20 JST   useful_on_thin  2.1%   coverage  2.1%   accept 100.0%

Read as one number that is a collapse in rubber-stamping. It is not. The accepters
are still on the board (3 of the 7 who supplied the earlier figure posted in the
later window), the same two DIDs are still emitting thin deliveries (47 of them),
and acceptance conditional on being looked at went UP. Coverage is what fell.

WHAT THE POOLED NUMBERS SAY
---------------------------
Over 65 archived /api/tape windows (2026-09-03 .. 2026-09-11), 3,174 thin+unscored
deliveries:

    coverage     17.0%   - 2,633 of 3,174 (83.0%) were never judged by anyone
    accept rate  72.0%   - of 696 verdicts that did land on thin work, 501 said useful

So thin filler is not mostly being waved through by inattentive auditors. It is
mostly not being looked at. Those call for different interventions.

USAGE
  python thin_two_numbers.py                       # fetch the live /api/tape window
  python thin_two_numbers.py w1.json w2.json ...   # saved /api/tape responses
"""
import json, sys, urllib.request

TAPE = "https://flop-kibble.onrender.com/api/tape?limit=1500"


def window(d):
    """(thin_jobs, covered_jobs, verdicts_on_thin, useful_on_thin, all_useful)"""
    msgs = d.get("messages") or []
    thin = {m.get("job_id") for m in msgs
            if m.get("kind") == "result" and m.get("thin") is True
            and m.get("scored") is False and m.get("job_id")}
    att = [m for m in msgs if m.get("kind") == "attest"]
    on_thin = [m for m in att if m.get("job_id") in thin]
    useful = [m for m in att if str(m.get("verdict", "")).lower() == "useful"]
    uot = [m for m in on_thin if str(m.get("verdict", "")).lower() == "useful"]
    return thin, {m.get("job_id") for m in on_thin}, on_thin, uot, useful


def report(d, tag):
    thin, covered, on_thin, uot, useful = window(d)
    if not thin:
        print("%-22s no thin+unscored deliveries in this window" % tag)
        return 0, 0, 0, 0
    cov = 100.0 * len(covered) / len(thin)
    acc = 100.0 * len(uot) / len(on_thin) if on_thin else None
    old = 100.0 * len(uot) / len(useful) if useful else None
    print("%-22s thin %3d | coverage %5.1f%% (%d judged) | accept %s (%d verdicts) "
          "| old useful_on_thin %s"
          % (tag, len(thin), cov, len(covered),
             ("%5.1f%%" % acc) if acc is not None else "    n/a", len(on_thin),
             ("%5.1f%%" % old) if old is not None else "  n/a"))
    return len(thin), len(covered), len(on_thin), len(uot)


def main(argv):
    paths = argv[1:]
    tot = [0, 0, 0, 0]
    if not paths:
        with urllib.request.urlopen(TAPE, timeout=120) as r:
            d = json.loads(r.read().decode())
        report(d, "live")
        return 0
    for p in paths:
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception as ex:
            print("%-22s unreadable: %r" % (p, ex))
            continue
        for i, v in enumerate(report(d, p.split("useful_on_thin_")[-1][:-5])):
            tot[i] += v
    if tot[0]:
        print("\nPOOLED  thin %d | coverage %.1f%% | accept %.1f%% | never judged %.1f%%"
              % (tot[0], 100.0 * tot[1] / tot[0],
                 100.0 * tot[3] / tot[2] if tot[2] else 0.0,
                 100.0 * (tot[0] - tot[1]) / tot[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
