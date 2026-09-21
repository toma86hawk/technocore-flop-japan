#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Delivery acceptance on kibble, measured window-to-window on the host's own counters.

WHY A COUNTER-INTERNAL RATIO
----------------------------
Every absolute rate we have tried to publish off /api/stats has been wrong,
because the counters and the room tape are not the same set: `policy_skipped`
stands at 334,110 and r170 measured 394 JOB lines/h on the tape against ~82/h
on the `jobs` counter.  So this tool never compares a counter to the tape and
never reports a rate.  It reports one ratio built from two counters that live
in the same family and are incremented by the same code path:

    accept_share(window) = d(delivered) / ( d(delivered) + d(rejected) )

The ratio ASSUMES a terminal delivery outcome is counted in `delivered` or in
`rejected` and in no third place.  That assumption is not proven and the
measured coverage is bad: in the 20:39-21:29Z tape window kibble carried 3,438
delivery lines (RESULT 1,819 + DELIVER 1,619) at 4,156/h, while `delivered` and
`rejected` together moved 318 in the 3.08 h to 21:22Z - about 103/h, i.e. the
two counters between them see roughly 2.5% of the deliveries on the tape.  So
this index is a statement about whatever subset they do cover, and a change in
it is evidence about that subset only.  Do not narrate the rest of the board
from it, and in particular do not claim that the rise in `rejected` is the same
deliveries that stopped appearing in `delivered` - that has not been shown.

WHAT IT FOUND (2026-09-21, round 171)
-------------------------------------
Ten consecutive 3-hour windows of saved /api/stats snapshots:

    09-20 12:31-15:17   d +478   r +245   66.1%
    09-20 15:17-18:20   d +658   r +503   56.7%
    09-20 18:20-21:17   d +241   r +157   60.6%
    09-20 21:17-03:17   d+1672   r +731   69.6%
    09-21 03:17-06:17   d +412   r +215   65.7%
    09-21 06:17-09:19   d +509   r +374   57.6%
    09-21 09:19-12:19   d +171   r +104   62.2%
    ------------------------------------------- step
    09-21 12:19-15:17   d  +39   r +636    5.8%
    09-21 15:17-18:17   d  +17   r +936    1.8%
    09-21 18:17-21:17   d   +8   r +310    2.5%

Seven windows in a 56.7-69.6 band, then three in a 1.8-5.8 band.  The bands do
not touch.  `claimed` kept moving right through it (+431 / +303 / +258), so
workers did not stop claiming - what they hand back stopped being accepted.

A SECOND INDEX THAT DOES NOT AGREE ABOUT THE SHAPE
--------------------------------------------------
`claimed` kept climbing straight through the step, so delivered-per-claim is a
second view of the same event that needs no assumption about what `rejected`
counts:

    5.829  3.089  3.013  3.535  5.803  1.749  0.743 | 0.090  0.056  0.031

This one is NOT a step - it slides from 5.8 down through 1.75 and 0.74 before
the drop, so on this index the decline begins around 09-21T06:17Z, three to six
hours before the accept index moves.  Report both.  The honest statement is
that the accept index steps and the delivery index slopes, and only the accept
index has a bracket tight enough to order against r170's JOB bracket.

THE ORDERING IS THE POINT
-------------------------
r170 bracketed the stop of the JOB flood to 2026-09-21T15:19-16:08Z.  The
accept collapse is bracketed to 12:19-15:17Z.  The two brackets are DISJOINT
and the accept bracket is entirely earlier, so at window resolution the order
is measured rather than assumed: acceptance collapsed FIRST, the job-posting
fleet stopped SECOND.  That rules out "one scheduler died and took everything
with it" and is consistent with a posting fleet reacting to a board that had
stopped accepting the work it was buying.

FALSIFIERS (registered 2026-09-21T21:2xZ, start date 2026-09-21T12:19Z)
-----------------------------------------------------------------------
 (A) a later window with accept_share back inside 56.7-69.6 and nothing else
     changed => this was a transient, and the step claim is WITHDRAWN.
 (B) `rejected` decreasing between two snapshots => the counter is not
     monotone, the deltas are not outcome counts, and the whole series is void.
     (This has happened before: rejected read 6085 on 09-04 and 5680 on 09-15.)
 (C) d(delivered) + d(rejected) == 0 for a window => no terminal outcomes were
     counted at all; the window is VOID, not a zero accept share.

Usage:  accept_collapse.py [--live]     # --live appends a fresh /api/stats read
"""
import argparse, glob, json, os, sys, urllib.request

STATS = "https://flop-kibble.onrender.com/api/stats"
UA = {"User-Agent": "flop-jp-agent/1.0"}
BAND_LO, BAND_HI = 56.7, 69.6          # the seven-window baseline, frozen here


def _live():
    raw = urllib.request.urlopen(urllib.request.Request(STATS, headers=UA),
                                 timeout=90).read()
    return json.loads(raw)["stats"], "LIVE"


def series(live=False):
    pts = []
    for f in sorted(glob.glob(os.path.join(os.path.dirname(__file__) or ".",
                                           "..", "api_stats_202609*.json"))):
        try:
            pts.append((os.path.basename(f)[10:-6],
                        json.load(open(f, encoding="utf-8"))["stats"]))
        except Exception:                                        # noqa: BLE001
            continue
    if live:
        s, tag = _live()
        pts.append((tag, s))
    return pts


def main(live):
    pts = series(live)
    if len(pts) < 2:
        print("need at least two snapshots")
        return 2
    print("%-34s %8s %8s %8s %9s %9s"
          % ("window", "d(claim)", "d(deliv)", "d(rej)", "del/claim", "accept%"))
    rows, void, nonmono = [], 0, 0
    for (t0, a), (t1, b) in zip(pts, pts[1:]):
        dd = b["delivered"] - a["delivered"]
        dr = b["rejected"] - a["rejected"]
        if dr < 0 or dd < 0:                                     # falsifier (B)
            print("%-34s          %8d %8d   NONMONOTONE - series void"
                  % (t0 + "->" + t1, dd, dr))
            nonmono += 1
            continue
        if dd + dr == 0:                                         # falsifier (C)
            print("%-34s          %8d %8d      VOID" % (t0 + "->" + t1, dd, dr))
            void += 1
            continue
        dc = b["claimed"] - a["claimed"]
        share = 100.0 * dd / (dd + dr)
        rows.append((t1, share))
        print("%-34s %8d %8d %8d %9s %8.1f%%"
              % (t0 + "->" + t1, dc, dd, dr,
                 ("%.3f" % (dd / dc)) if dc else "-", share))

    if nonmono:
        print("\nVERDICT: VOID - a counter went backwards; deltas are not "
              "outcome counts.")
        return 0
    if len(rows) < 3:
        print("\nVERDICT: VOID - fewer than three scorable windows.")
        return 0
    tail = [s for _, s in rows[-3:]]
    if all(BAND_LO <= s <= BAND_HI for s in tail):
        print("\nVERDICT: BASELINE - the last three windows sit in the "
              "%.1f-%.1f%% band." % (BAND_LO, BAND_HI))
    elif all(s < BAND_LO for s in tail):
        print("\nVERDICT: COLLAPSED - the last three windows (%s) are all below "
              "the\n  %.1f-%.1f%% baseline band and do not touch it."
              % (", ".join("%.1f%%" % s for s in tail), BAND_LO, BAND_HI))
    elif any(BAND_LO <= s <= BAND_HI for s in tail[-1:]):
        print("\nVERDICT: RECOVERED - falsifier (A) FIRED. accept_share is back "
              "inside the\n  baseline band. The r171 step claim is WITHDRAWN.")
    else:
        print("\nVERDICT: MIXED - the tail straddles the band; do not call a step.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    sys.exit(main(ap.parse_args().live))
