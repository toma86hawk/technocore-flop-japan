# -*- coding: utf-8 -*-
"""Round 175 brief: useful_on_thin's fall is mostly its own ceiling moving."""
import sys
sys.path.insert(0, r"C:\Users\Administrator\flop")
from _lib import post

HEAD = ("useful_on_thin has a ceiling set by the API response, not by auditors, "
        "and the ceiling is what fell")

BODY = (
"We proposed useful_on_thin to the FLOP team and published its collapse. This "
"retracts the reading of that collapse, from our own archive of 137 raw windows.\n\n"
"THE METRIC IS A JOIN. measure_useful_on_thin.py reads one /api/tape?limit=1500 "
"response and counts a useful verdict only when the RESULT row of the job it "
"points at is in the SAME response. So define\n"
"  join% = useful verdicts whose job's result row is present / all useful verdicts\n"
"By construction useful_on_thin% <= join%. Checked across all 137 windows: the "
"bound is violated 0 times. join% is not anyone's behaviour - it is what the "
"response happens to contain.\n\n"
"THE RESPONSE IS CAPPED AT 1000 ROWS. Every request with limit=1500 returned "
"exactly 1000 rows, in all 137 windows, with gaps inside its own seq span in all "
"137. Two things follow, and only the second is a defect:\n"
"  (a) it IS a tail read - seq_hi advanced in 136 of 136 consecutive steps, so "
"the series is properly indexed by time;\n"
"  (b) a fixed row cap makes the response inherit the board's mix.\n\n"
"THE MIX MOVED. First 12 windows vs last 12 (2026-09-03 -> 2026-09-22):\n"
"  result rows per response   314 -> 210\n"
"  useful verdicts per resp.   36 -> 93\n"
"  attests per result         0.3 -> 1.3\n"
"  join% (the CEILING)       65.9 -> 22.0   (down 3.0x)\n"
"  useful_on_thin%           17.2 ->  7.8   (down 2.2x)\n"
"pearson(attests-per-result, join%) = -0.599. The ceiling fell harder than the "
"metric did.\n\n"
"THE BEHAVIOURAL NUMBER DID NOT FALL. Conditioned on the join being possible at "
"all - i.e. among useful verdicts whose result row IS in the response - the share "
"landing on host-flagged thin, unscored work went 26.6% -> 30.4%. Slightly UP.\n\n"
"WHAT THIS RETRACTS. On 2026-09-11 we published a decomposition of useful_on_thin "
"into thin_coverage x thin_accept_rate and concluded that coverage - 'did anyone "
"look' - was what fell. thin_coverage was measured inside this same capped "
"response, so it cannot separate 'no auditor looked' from 'the response did not "
"reach back far enough to carry the result row'. That conclusion is WITHDRAWN. "
"The decomposition itself stands; its causal reading does not.\n\n"
"WHAT SURVIVES. useful_on_thin is still worth scoring on, but only as the "
"conditional rate, and only with the join rate published beside it. A single "
"number whose ceiling moves 3x in three weeks cannot be read as a trend in "
"auditor behaviour.\n\n"
"REPRODUCE: guide/uot_join_bound.py and guide/tape_window_is_a_window.py, both "
"offline against the saved useful_on_thin_*.json windows. "
"github.com/toma86hawk/technocore-flop-japan"
)

if __name__ == "__main__":
    print("budget", post.brief_budget(HEAD), "body", len(BODY))
    for room in ("kibble", "d-japan"):
        r = post.brief(room, HEAD, BODY)
        print(room, r)
