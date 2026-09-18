#!/usr/bin/env python3
"""sonnet2_frontier.py -- where has the sonnet-2 referee actually got to?

A deadline verdict tells you what the referee decided.  It does not tell you
WHICH arrival it decided about.  Round 145 showed those are different things:
the referee charges "deadline: outside contest window" on its own wall clock
at the moment it dequeues an item, so for hours it rejected ballots that had
arrived before the deadline.  The quantity that settles this is the
PROCESSING FRONTIER: the true arrival time of the items being ruled on now.

This tool measures the frontier, the lag and the drain rate, and refuses to
print any of them when it cannot date arrivals honestly.

HOW ARRIVALS ARE DATED
Fleet-style request_ids carry their own send time as a 13-digit epoch-ms
field (rzxyz-px-pelagashyce-1789733272039 -> 2026-09-18T12:07:52.039Z).
guide/sonnet2_rid_clock.py established that rule and validates it with
CONTROL A: for every ballot still in the ring, |room_ts - embedded_ts| must
be small.

CONTROL A CAN FAIL FOR A REASON THAT IS NOT AN ERROR.
On 2026-09-18T21:21Z control A returned n=0 -- not a disagreement, an empty
sample.  The live ballot population had switched to bare UUID request_ids
(7,424 of 7,545), which carry no epoch.  The rule had not stopped being true;
there was simply nothing live left to check it against.

So this tool takes a --reference export: an earlier export, PINNED TO DISK,
whose ring still contained epoch-bearing ballots.  Control A is re-run there.
That validates the DECODING RULE, which is a property of the generator, and
the validated rule is then applied to receipt subjects of the same rid
families in the current export.  What this does NOT do is re-validate the
rule against today's traffic, and the tool says so in its output every run.
If you have no reference export with a passing control A, you get
INCONCLUSIVE and no numbers.

COVERAGE IS ALWAYS PRINTED.  Undatable receipts are counted, never dropped
silently: on the run above, 83.3% of receipt rows were datable and 0% of live
ballots were.

usage:
  python guide/sonnet2_frontier.py <export.jsonl> [--reference <pinned.jsonl>]
                                    [--deadline 2026-09-18T12:00:00Z]
                                    [--prev-issue ISO --prev-lag-hours H]

--prev-issue / --prev-lag-hours supply the previous reading so the tool can
print the drain rate: arrival time consumed per unit wall clock.  Below 1.0
the backlog is growing.  Measured 2026-09-18: 0.221x.
"""
import argparse
import collections
import datetime
import json
import re
import statistics
import sys

EPOCH_MS = re.compile(r"(\d{13})")
LO = datetime.datetime(2026, 5, 1, tzinfo=datetime.timezone.utc).timestamp()
HI = datetime.datetime(2027, 1, 1, tzinfo=datetime.timezone.utc).timestamp()
# control A thresholds, identical to sonnet2_rid_clock.py
A_P95_MAX = 60.0
A_RANGE = (-5.0, 600.0)
A_MIN_N = 50


def T(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def iso(x):
    return datetime.datetime.fromtimestamp(x, datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def embedded(rid):
    """Epoch seconds encoded in rid, or None.  Control B (sanity window) lives here."""
    m = EPOCH_MS.search(rid or "")
    if not m:
        return None
    e = int(m.group(1)) / 1000.0
    return e if LO < e < HI else None


def family(rid):
    return re.sub(r"\d", "#", (rid or "").split("-")[0])


def rows(path):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except ValueError:
                continue


def split(path):
    """Return (ballots, receipt_rows).  A receipt row is (issue_ts, rid, status)."""
    ballots, receipts = [], []
    for r in rows(path):
        try:
            o = json.loads(str(r.get("text", "")))
        except ValueError:
            continue
        ts = T(r["ts"])
        if o.get("type") == "sonnet.ballot.v1":
            ballots.append((ts, o))
            continue
        batch = o.get("receipts")
        for x in (batch if isinstance(batch, list) else [o]):
            receipts.append((ts, x.get("request_id"), o.get("status")))
    return ballots, receipts


def control_a(ballots):
    d = sorted(ts - e for ts, o in ballots
               for e in [embedded(o.get("request_id"))] if e is not None)
    if len(d) < A_MIN_N:
        return {"ok": False, "n": len(d),
                "why": "no datable ballot in the ring" if not d else "sample too small"}
    p95 = d[int(0.95 * len(d))]
    out = sum(1 for x in d if not (A_RANGE[0] <= x <= A_RANGE[1]))
    return {"ok": p95 <= A_P95_MAX and out == 0, "n": len(d),
            "median_s": round(statistics.median(d), 2), "p95_s": round(p95, 2),
            "out_of_range": out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("export")
    ap.add_argument("--reference")
    ap.add_argument("--deadline", default="2026-09-18T12:00:00Z")
    ap.add_argument("--prev-issue")
    ap.add_argument("--prev-lag-hours", type=float)
    a = ap.parse_args()

    ballots, receipts = split(a.export)
    live = control_a(ballots)
    out = {"export": a.export, "deadline": a.deadline,
           "control_A_live": live, "ballots_in_ring": len(ballots),
           "receipt_rows": len(receipts)}

    used = live
    if not live["ok"] and a.reference:
        ref = control_a(split(a.reference)[0])
        out["control_A_reference"] = dict(ref, export=a.reference)
        out["rule_validated_on"] = "pinned reference export, NOT on live traffic"
        used = ref
    if not used["ok"]:
        out["verdict"] = "INCONCLUSIVE"
        out["note"] = "control A failed and no reference export passed it; nothing is dated"
        print(json.dumps(out, indent=1))
        return 1

    dated = [(it, e, st) for it, rid, st in receipts
             for e in [embedded(rid)] if e is not None]
    out["coverage"] = {
        "receipt_rows_datable": len(dated),
        "receipt_rows_datable_pct": round(100.0 * len(dated) / max(1, len(receipts)), 1),
        "live_ballots_datable_pct": round(100.0 * live["n"] / max(1, len(ballots)), 1),
        "rid_families": collections.Counter(family(rid) for _, rid, _ in receipts).most_common(6),
    }
    if not dated:
        out["verdict"] = "INCONCLUSIVE"
        out["note"] = "control A passed but no receipt subject carries an epoch"
        print(json.dumps(out, indent=1))
        return 1

    arr = sorted(x[1] for x in dated)
    iss = sorted(x[0] for x in dated)
    D = T(a.deadline)
    m_arr, m_iss = statistics.median(arr), statistics.median(iss)
    out["frontier"] = {
        "true_arrival_span": [iso(arr[0]), iso(arr[-1])],
        "median_arrival": iso(m_arr), "median_issue": iso(m_iss),
        "lag_hours_p50": round((m_iss - m_arr) / 3600.0, 2),
        "arrived_after_deadline": sum(1 for x in arr if x > D),
        "arrived_before_deadline": sum(1 for x in arr if x <= D),
        "verdicts": dict(collections.Counter(st for _, _, st in dated)),
        # which side of the deadline the frontier sits on is the whole point
        "frontier_past_deadline": m_arr > D,
    }

    if a.prev_issue and a.prev_lag_hours is not None:
        p_iss = T(a.prev_issue)
        p_arr = p_iss - a.prev_lag_hours * 3600.0
        wall = (m_iss - p_iss) / 3600.0
        adv = (m_arr - p_arr) / 3600.0
        if wall > 0:
            out["drain"] = {
                "wall_hours": round(wall, 2),
                "arrival_hours_consumed": round(adv, 2),
                "rate_x_realtime": round(adv / wall, 3),
                "lag_growth_h_per_h": round(((m_iss - m_arr) / 3600.0 - a.prev_lag_hours) / wall, 3),
                "backlog_growing": adv < wall,
            }
            # Bracket the deadline crossing between the two readings.
            if p_arr <= D < m_arr:
                frac = (D - p_arr) / (m_arr - p_arr)
                out["deadline_crossing"] = {
                    "bracket_measured": [iso(p_iss), iso(m_iss)],
                    "interpolated_estimate": iso(p_iss + frac * (m_iss - p_iss)),
                    "warning": "the bracket is measured; the interpolation is an ESTIMATE",
                }
    out["verdict"] = "OK"
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
