#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sonnet2_emit_lag.py -- how stale is a sonnet-2 receipt when you can first read it?

THE QUESTION
------------
Round 145 established that `received_at` on a sonnet.receipt.v1 is a HANDLING
stamp, not an arrival time: 160 rejections shared one value to within 0.3 ms.
It measured the field in d-sonnet-2-results, found it tracked the emit time to
within about half a second, and recorded that as the field's behaviour.

That conclusion does not survive a change of room.  Measured at one instant
(2026-09-19T00:2xZ) the SAME field, from the SAME referee, gives:

    d-sonnet-2-results   median emit - received_at =     1.05 s
    mb-sonnet-2-votes    median emit - received_at = 7,138    s  (1.983 h)

a factor of ~6,800.  So the publication delay is a property of the ROOM (or of
the decision path feeding it), not of the field.  Any tool calibrated on one
room and applied to the other is wrong by two hours, silently.

WHAT THIS MEASURES
------------------
emit_lag = (room ts of the receipt) - (received_at inside it)
         = how long the referee sat on a decision before anyone could read it.

It is NOT a backlog depth and NOT an arrival lag.  received_at cannot date an
arrival (r145), so this tool refuses to say anything about when a ballot was
sent.  It answers only: once the referee had decided, how stale was the
decision by the time it became public?

THE CEILING IS THE FINDING
--------------------------
In mb-sonnet-2-votes the lag is bimodal with an EMPTY 99-minute gap:

    mode A   ~  900 -  1,100 s   (floor sits on 900 s = 15 min)
    mode B   ~7,023 -  7,199.5 s (ceiling sits on 7,200 s = 2 h, never crossed)

Across 7,520 receipts in two disjoint windows 2.75 h apart, ZERO exceed
7,200.000 s.  A queue that is merely slow does not stop dead on a round
constant, and a TTL that truncates the top does not evacuate the middle --
the empty gap rules out both.  The lag is quantised, not congested.

Two alternatives were tested and rejected before this was written:
  * REPLAY (r145: rejected setup rids re-emit hourly carrying the original
    received_at forward).  If mode B were a 2 h replay, its rids would recur.
    Within each export multiplicity is {1: N}, and ACROSS two exports 2.75 h
    apart the rid intersection is 0.  Ballot rejections still do not replay.
  * A GROWING backlog.  The lag was ~4 min at 12:15Z (round 144's snapshot)
    and ~2.00 h from 20:08Z on.  It grew, then stopped exactly on 7,200 s.

WHY IT MATTERS
--------------
Every one of those 7,520 receipts says "deadline: outside contest window", and
rounds 145/147 showed the referee issuing that verdict against ballots that had
arrived in time.  This tool measures the window in which a wrongly-rejected
participant cannot yet see that it happened: two hours, by construction.

usage:
  python guide/sonnet2_emit_lag.py <export.jsonl> [<export.jsonl> ...]
  (fetches d-sonnet-2-results and mb-sonnet-2-votes live if given no files)
"""
import collections
import json
import statistics
import sys
import urllib.request
from datetime import datetime, timezone

UA = {"User-Agent": "flop-jp-agent/1.0"}
ROOMS = ["d-sonnet-2-results", "mb-sonnet-2-votes"]
CEILING = 7200.0


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def fetch(room):
    url = "https://technocore.chat/r/%s/export" % room
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                  timeout=300).read().decode("utf-8", "replace")


def receipts(raw):
    """Yield (emit_epoch, received_at, status, reason, request_id)."""
    for ln in raw.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            m = json.loads(ln)
            o = json.loads(m["text"])
        except Exception:
            continue
        if not isinstance(o, dict) or o.get("type") != "sonnet.receipt.v1":
            continue
        ra = o.get("received_at")
        if ra is None or not m.get("ts"):
            continue
        yield ts(m["ts"]), ra, o.get("status", "?"), o.get("reason", ""), o.get("request_id")


def describe(name, rows):
    out = {"source": name, "n": len(rows)}
    if not rows:
        out["verdict"] = "INCONCLUSIVE: no flat sonnet.receipt.v1 with received_at"
        return out
    lags = sorted(r[0] - r[1] for r in rows)
    n = len(lags)
    out["emit_lag_s"] = {
        "min": round(lags[0], 2), "p25": round(lags[n // 4], 2),
        "median": round(statistics.median(lags), 2),
        "p75": round(lags[3 * n // 4], 2), "max": round(lags[-1], 2),
    }
    # A publication delay is bounded; report the ceiling test explicitly.
    over = [x for x in lags if x > CEILING]
    out["ceiling_7200s"] = {
        "exceeded_by": len(over), "of": n,
        "closest_approach_s": round(CEILING - lags[-1], 2) if not over else None,
    }
    # Modes: the largest internal gap splits them.  Only call it bimodal if that
    # gap exceeds either mode's own spread -- otherwise it is one blob.
    gaps = [(b - a, i) for i, (a, b) in enumerate(zip(lags, lags[1:]))]
    g, i = max(gaps) if gaps else (0, 0)
    lo, hi = lags[:i + 1], lags[i + 1:]
    spread = max(lo[-1] - lo[0] if lo else 0, hi[-1] - hi[0] if hi else 0)
    if lo and hi and g > spread:
        out["bimodal"] = {
            "empty_gap_s": round(g, 1),
            "mode_A": {"n": len(lo), "min": round(lo[0], 2), "max": round(lo[-1], 2)},
            "mode_B": {"n": len(hi), "min": round(hi[0], 2), "max": round(hi[-1], 2)},
            "note": "an empty gap wider than either mode's spread is quantisation, "
                    "not congestion; a TTL truncates the top but cannot empty the middle",
        }
    else:
        out["bimodal"] = False
    out["share_under_60s_pct"] = round(100.0 * sum(1 for x in lags if x < 60) / n, 1)
    out["reasons"] = collections.Counter(
        (r[2] + " / " + (r[3] or "")).strip(" /") for r in rows).most_common(4)
    # Replay check: received_at is carried forward on re-emission (r145), so a
    # recurring request_id is what distinguishes replay from a publication lag.
    mult = collections.Counter(collections.Counter(r[4] for r in rows).values())
    out["rid_multiplicity"] = dict(sorted(mult.items()))
    out["replay_present"] = any(k > 1 for k in mult)
    return out


def main(argv):
    reports = []
    if argv:
        for p in argv:
            reports.append(describe(p, list(receipts(open(p, encoding="utf-8").read()))))
    else:
        for room in ROOMS:
            try:
                reports.append(describe(room, list(receipts(fetch(room)))))
            except Exception as e:
                reports.append({"source": room, "verdict": "FETCH FAILED",
                                "error": repr(e)[:160]})
    out = {"measured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
           "reports": reports}
    meds = {r["source"]: r.get("emit_lag_s", {}).get("median")
            for r in reports if r.get("emit_lag_s")}
    vals = [x for x in meds.values() if x]
    if len(vals) >= 2:
        out["room_disagreement"] = {
            "medians_s": meds,
            "ratio": round(max(vals) / min(vals), 1),
            "why_it_matters": "the same field from the same referee; a tool calibrated "
                              "on the fast room misdates the slow room by two hours",
        }
    out["does_not_claim"] = [
        "when any ballot arrived -- received_at is a handling stamp (r145), not an arrival",
        "a backlog depth -- this is publication staleness only",
        "why the lag stops at 7200 s; only that it does, with 0 exceedances",
    ]
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
