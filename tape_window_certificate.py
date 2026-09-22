#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Which /api/tape responses were actually a window?

useful_on_thin_series has 139 points.  Every one is computed over a single
GET /api/tape?limit=1500 and read as "the last few thousand rows".  r175 tested
that reading with: did seq_hi advance from one archived response to the next?
It did, 136 of 136, and r175 recorded the tail reading as CONFIRMED.

seq_hi advancing constrains only the NEWEST row in a response.  It cannot see a
response whose BULK moved somewhere else.

THE FIRST DRAFT OF THIS TOOL WAS WRONG AND THAT IS RECORDED HERE ON PURPOSE.
It used density = (seq_hi - seq_lo + 1) / rows and flagged 13 responses as
"spanning the whole tape".  They do not.  Each is an ordinary contiguous tail
read that happens to carry 1-4 stray rows near seq 400.  Density is a function
of the MINIMUM, so one outlier row set it, and one row was allowed to condemn
999 others.  That is the r152 mistake - a single passer-by vetoing a population
claim - with the sign reversed.  Any statistic resting on an extreme of the
sample has this defect.  Use the bulk.

WHAT THIS MEASURES NOW
  bulk    = median seq of the response
  strays  = rows further than STRAY from the bulk (reported, never fatal)
  RESET   = the bulk fell below RESET_RATIO of the highest bulk any STRICTLY
            EARLIER response reached.  The tape's ordinal restarted: rows carry
            CURRENT timestamps at LOW seq and seq is no longer unique.
  TAIL    = the bulk kept advancing.

The baseline is taken from strictly earlier responses, never from the archive
maximum.  A falsifier without an as-of date is a history display that fires on
normal growth (the r158 rule, applied to this tool).

OBSERVED 2026-09-22: between the 06:26Z and 09:38Z responses the bulk fell from
9,971,168 to 897.  The 12:32Z response holds 1,000 rows at seq 400..1393 whose
timestamps run 11:30:30Z..12:17:14Z - current traffic at low seq - and seq 400
appears 7 times inside it.  /api/stats tape_head_seq froze at 9,997,001 on the
same step and still read 9,997,001 at 12:41Z.
"""
import json, glob, os, sys, io, statistics, collections

STRAY = 50000
RESET_RATIO = 0.5


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
        med = statistics.median(s)
        ts = sorted(x["ts"] for x in m if x.get("ts"))
        c = collections.Counter(s)
        out.append({"file": os.path.basename(f), "rows": len(m),
                    "seq_lo": min(s), "seq_hi": max(s), "bulk": int(med),
                    "strays": sum(1 for v in s if abs(v - med) > STRAY),
                    "max_seq_multiplicity": max(c.values()),
                    "ts_lo": ts[0][:19] if ts else None,
                    "ts_hi": ts[-1][:19] if ts else None})
    return out


def main():
    pat = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "useful_on_thin_*.json")
    rs = rows(pat)
    if not rs:
        print("no archived responses matched %s" % pat)
        return
    reached = 0
    for r in rs:
        r["baseline"] = reached
        r["kind"] = ("UNKNOWN" if reached == 0
                     else "RESET" if r["bulk"] < RESET_RATIO * reached
                     else "TAIL")
        reached = max(reached, r["bulk"])
    tail = [r for r in rs if r["kind"] == "TAIL"]
    reset = [r for r in rs if r["kind"] == "RESET"]
    stray = [r for r in rs if r["strays"]]
    print("archived responses: %d" % len(rs))
    print("  TAIL    %3d  (bulk kept advancing)" % len(tail))
    print("  RESET   %3d  (bulk fell below %.0f%% of every earlier bulk)"
          % (len(reset), RESET_RATIO * 100))
    print("  carrying stray rows >%d from the bulk: %d responses, %d..%d strays each"
          % (STRAY, len(stray),
             min([r["strays"] for r in stray] or [0]),
             max([r["strays"] for r in stray] or [0])))
    print("  -> strays are a handful of rows out of 1000 and do NOT void a response")
    for r in reset:
        print("\nRESET at %s" % r["file"])
        print("  bulk %d, while every earlier response reached a bulk of %d"
              % (r["bulk"], r["baseline"]))
        print("  rows %d  seq %d..%d  one seq repeated up to %d times"
              % (r["rows"], r["seq_lo"], r["seq_hi"], r["max_seq_multiplicity"]))
        print("  timestamps inside it: %s .. %s" % (r["ts_lo"], r["ts_hi"]))
    first = rs.index(reset[0]) if reset else len(rs)
    print("\npoints taken BEFORE the first reset: %d of %d - seq-based reasoning "
          "holds inside that stretch" % (first, len(rs)))
    print("points taken AT OR AFTER it: %d - their seq cannot be compared with the "
          "earlier ones and must be labelled" % (len(rs) - first))


if __name__ == "__main__":
    main()
