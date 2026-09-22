#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Which /api/tape responses were actually a window?

useful_on_thin_series has 139 points.  Every one of them is computed over a
single GET /api/tape?limit=1500 and read as "the last few thousand rows".
r175 tested that reading and reported it CONFIRMED: seq_hi advanced in 136 of
136 consecutive steps, so the series is indexed by time.

That test is insufficient, and this tool is the demonstration.  seq_hi advancing
says only that the newest row in the response got newer.  It says nothing about
where the other 999 rows came from.  A response holding one recent row and 999
rows from the far end of the tape passes it.

The test that works is DENSITY:

    density = (seq_hi - seq_lo + 1) / rows_returned

A contiguous tail read of 1000 rows spans a few thousand seq, so density is a
small number.  A response scattered across the whole tape has a density in the
thousands.  The two are three orders of magnitude apart; there is no threshold
to tune.

  TAIL      density < 100 and the response starts near where the tape already was
  SCATTER   density >= 100       the response spans the tape, the point is not a window
  REWOUND   contiguous but seq_lo is far behind what earlier responses had already
            reached - the endpoint served the START of the tape

Every SCATTER and REWOUND response observed so far begins at exactly seq 400.

Run with no arguments to classify every archived window in the parent directory.
Points classified SCATTER or REWOUND must not be compared with points classified
TAIL, and must not be plotted on the same axis without saying so.
"""
import json, glob, os, sys, io, statistics

CUT = 100.0


def rows(pattern):
    out = []
    for f in sorted(glob.glob(pattern), key=os.path.getmtime):
        try:
            d = json.load(io.open(f, encoding="utf-8", errors="replace"))
        except Exception:
            continue
        m = d.get("messages", [])
        s = [x["seq"] for x in m if x.get("seq") is not None]
        if not s:
            continue
        span = max(s) - min(s) + 1
        out.append({"file": os.path.basename(f), "rows": len(m),
                    "seq_lo": min(s), "seq_hi": max(s), "span": span,
                    "density": span / float(len(s))})
    return out


def main():
    pat = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "useful_on_thin_*.json")
    rs = rows(pat)
    if not rs:
        print("no archived windows matched %s" % pat)
        return
    # The threshold must have a "since when", or it is a history display that
    # fires on normal growth and reports the opposite (the r158 correction,
    # applied to this falsifier).  A window is judged against the tape as it
    # stood WHEN IT WAS TAKEN, approximated by the highest seq any STRICTLY
    # EARLIER response reached - never against the archive maximum.
    reached = 0
    for r in rs:
        if reached == 0:
            r["kind"] = "UNKNOWN"          # no predecessor, nothing to judge against
        elif r["seq_lo"] < 0.5 * reached:
            r["kind"] = "SCATTER" if r["density"] >= CUT else "REWOUND"
        else:
            r["kind"] = "SCATTER" if r["density"] >= CUT else "TAIL"
        r["reached"] = reached
        reached = max(reached, r["seq_hi"])
    bad = [r for r in rs if r["kind"] not in ("TAIL", "UNKNOWN")]
    tail = [r for r in rs if r["kind"] == "TAIL"]
    print("archived responses: %d" % len(rs))
    print("  TAIL    %3d  density median %.2f, max %.2f"
          % (len(tail), statistics.median(r["density"] for r in tail),
             max(r["density"] for r in tail)))
    print("  SCATTER %3d  (spans the tape; density >= %.0f)"
          % (sum(1 for r in bad if r["kind"] == "SCATTER"), CUT))
    print("  REWOUND %3d  (contiguous, but starts far behind what the tape had already reached)"
          % sum(1 for r in bad if r["kind"] == "REWOUND"))
    print("\nNOT COMPARABLE - drop these points or label them:")
    for r in bad:
        print("  %-34s %-7s rows=%-5d seq %9d..%-9d density=%9.1f"
              % (r["file"], r["kind"], r["rows"], r["seq_lo"], r["seq_hi"],
                 r["density"]))
        print("      tape had already reached seq %d before this response" % r["reached"])
    print("\nshare of the published series that is not a window: %d/%d = %.1f%%"
          % (len(bad), len(rs), 100.0 * len(bad) / len(rs)))
    print("\nwhy r175's check missed them: seq_hi advanced on every one of these.")
    prev = None
    regress = 0
    for r in rs:
        if prev is not None and r["seq_hi"] <= prev:
            regress += 1
        prev = r["seq_hi"]
    print("  seq_hi regressions across all %d steps: %d" % (len(rs) - 1, regress))


if __name__ == "__main__":
    main()
