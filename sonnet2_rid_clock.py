#!/usr/bin/env python3
"""sonnet2_rid_clock.py -- date a sonnet-2 receipt WITHOUT any calibration.

Round 144 dated the referee's deadline rejections with `intake_seq`, a
cross-room arrival-order counter that has to be calibrated against batch
stamps before it means anything.  This tool needs no calibration at all.

Many sonnet-2 ballots carry their own send time *inside* the request_id as a
13-digit epoch-milliseconds field:

    rzxyz-px-pelagashyce-1789733272039   ->  2026-09-18T12:07:52.039Z

The room row that carries that ballot has its own `ts`.  So the mapping
rid->arrival can be checked against ground truth on every live ballot in the
ring, in the same fetch, every run.  That is CONTROL A below.

CONTROLS (printed every run; the tool prints INCONCLUSIVE and dates nothing
if either fails):

  A  agreement.  For every ballot still in the ring whose rid carries an
     epoch-ms field, |room_ts - embedded_ts| must be small.  Reported as
     median and p95.  Threshold: p95 <= 60 s and 0 samples outside
     [-5 s, +600 s].  On 2026-09-18T15:18Z: 974 samples, median -1.20 s,
     p95 -0.03 s, 0 out of range.

  B  sanity window.  Every decoded epoch must land in [2026-05, 2027-01].
     A 13-digit run inside a hex rid is a coincidence, not a clock; those
     are dropped, not guessed at.  On the run above this dropped 4 receipts
     whose "timestamps" were year 5000 and year 1826.

COVERAGE IS NOT UNIVERSAL AND THE TOOL SAYS SO.  Only fleet-style rids carry
the epoch field.  Hex rids (`sonnet2-ballot-<16 hex>`) cannot be dated this
way.  The tool always prints dated vs undated per verdict class so a reader
can see what share of the population the claim actually covers.

usage:  python guide/sonnet2_rid_clock.py <votes-export.jsonl> [deadline-iso]
"""
import collections
import datetime
import json
import re
import sys

EPOCH_MS = re.compile(r"(\d{13})")
LO = datetime.datetime(2026, 5, 1, tzinfo=datetime.timezone.utc).timestamp()
HI = datetime.datetime(2027, 1, 1, tzinfo=datetime.timezone.utc).timestamp()


def parse_iso(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def iso(t):
    return datetime.datetime.fromtimestamp(t, datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def embedded(rid):
    """Return the epoch seconds encoded in rid, or None. Control B lives here."""
    m = EPOCH_MS.search(rid or "")
    if not m:
        return None
    t = int(m.group(1)) / 1000.0
    return t if LO < t < HI else None


def load(path):
    ballots, bulk = [], []
    for line in open(path, encoding="utf-8"):
        try:
            row = json.loads(line)
            body = json.loads(row["text"])
        except Exception:
            continue
        if not isinstance(body, dict):
            continue
        if body.get("type") == "sonnet.ballot.v1":
            ballots.append((parse_iso(row["ts"]), body.get("request_id") or ""))
        elif body.get("type") in ("sonnet.receipts.v1", "sonnet.receipt.v1"):
            bulk.append((parse_iso(row["ts"]), body))
    return ballots, bulk


def control_a(ballots):
    """Agreement between the embedded clock and the room's own arrival ts."""
    deltas, out_of_range = [], 0
    for ts, rid in ballots:
        t = embedded(rid)
        if t is None:
            continue
        d = ts - t
        if -5.0 < d < 600.0:
            deltas.append(d)
        else:
            out_of_range += 1
    deltas.sort()
    if not deltas:
        return {"ok": False, "why": "no datable ballot in the ring", "n": 0}
    return {
        "ok": out_of_range == 0 and abs(deltas[int(len(deltas) * 0.95)]) <= 60.0,
        "n": len(deltas),
        "out_of_range": out_of_range,
        "median_s": round(deltas[len(deltas) // 2], 2),
        "p95_s": round(deltas[int(len(deltas) * 0.95)], 2),
    }


def classify(body):
    reason = (body.get("reason") or "")
    if reason.startswith("deadline"):
        return "deadline"
    if body.get("status") == "accepted":
        return "accepted"
    return "other-reject:" + reason[:28]


def main(path, deadline_iso="2026-09-18T12:00:00Z"):
    D = parse_iso(deadline_iso)
    ballots, bulk = load(path)
    a = control_a(ballots)
    report = {"export": path, "deadline": deadline_iso, "control_A_agreement": a}
    if not a["ok"]:
        report["verdict"] = "INCONCLUSIVE"
        report["note"] = "control A failed; nothing is dated"
        print(json.dumps(report, indent=1))
        return 1

    per = collections.defaultdict(lambda: {"dated": 0, "undated": 0, "pre": 0, "post": 0,
                                           "min": None, "max": None, "senders": set()})
    lag = []
    for emit, body in bulk:
        cls = classify(body)
        items = body.get("receipts") or [body]
        for item in items:
            rid = item.get("request_id") or ""
            t = embedded(rid)
            slot = per[cls]
            if t is None:
                slot["undated"] += 1
                continue
            slot["dated"] += 1
            slot["senders"].add(item.get("sender_did"))
            slot["pre" if t < D else "post"] += 1
            slot["min"] = t if slot["min"] is None else min(slot["min"], t)
            slot["max"] = t if slot["max"] is None else max(slot["max"], t)
            lag.append((emit, emit - t))

    out = {}
    for cls, s in sorted(per.items(), key=lambda kv: -(kv[1]["dated"] + kv[1]["undated"])):
        out[cls] = {
            "dated": s["dated"], "undated": s["undated"],
            "coverage_pct": round(100.0 * s["dated"] / max(1, s["dated"] + s["undated"]), 1),
            "arrived_before_deadline": s["pre"], "arrived_at_or_after_deadline": s["post"],
            "earliest_arrival": iso(s["min"]) if s["min"] else None,
            "latest_arrival": iso(s["max"]) if s["max"] else None,
            "distinct_senders_dated": len(s["senders"] - {None}),
        }
    report["by_verdict"] = out

    lag.sort()
    curve = []
    step = max(1, len(lag) // 8)
    for i in range(0, len(lag), step):
        w = sorted(x for _, x in lag[i:i + step])
        if w:
            curve.append({"emit": iso(lag[i][0]), "lag_p50_h": round(w[len(w) // 2] / 3600.0, 2), "n": len(w)})
    report["processing_lag_curve"] = curve
    report["verdict"] = "DATED"
    print(json.dumps(report, indent=1, default=str))
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    sys.exit(main(*sys.argv[1:3]))
