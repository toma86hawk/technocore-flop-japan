#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""counter_onset.py -- when did kibble's /api/stats counters start going
backwards, and is that a property of the route or something it began doing?

BACKGROUND
----------
Round 172 showed that a difference between two /api/stats reads is not an event
count, because the route does not always answer with the same values.  That
result was correct and it voided our own r171 acceptance index.  But it was
stated as though it were timeless - "the counters are not monotone" - and that
is a stronger claim than the measurement supports.  A route that has always
behaved this way and a route that started behaving this way three hours ago
look identical inside one window.  Only the saved series can tell them apart.

WHAT THIS TOOL DOES
-------------------
It walks the saved api_stats_*.json snapshots in timestamp order and asks, for
each consecutive pair, whether any CUMULATIVE counter is lower in the later
snapshot.  `open` is excluded: it is a gauge and jobs legitimately leave the
open pool, so a decrease there means nothing.

Then it asks whether the regressions are spread through the series or bunched
at the end.  If all R regressing steps are the last R of N steps, the one-sided
probability of that under a null of uniform placement is 1 / C(N, R), which the
tool reports.  That number is the whole argument for calling it an onset rather
than a standing property, so it is printed with the counts it came from.

WHY THE NULL IS WEAK ON PURPOSE
-------------------------------
"Uniformly placed among the steps" is not a physical model of the route; it is
just the least informative thing that could have produced the pattern.  A small
p rules out "regressions happen at a constant rate across the saved series".
It does NOT establish a cause, and it cannot: our snapshots are ~3 h apart, so
the onset can only ever be located to the step it falls in, never finer.

A REGRESSION IS EVIDENCE, A NON-REGRESSION IS NOT
-------------------------------------------------
Two reads landing on the same responding replica look monotone even when the
split is active.  So a clean step is weak evidence of absence while a regressing
step is strong evidence of presence.  That asymmetry is why the tool reports
the clean-step count as an upper bound on quiet, never as proof the route was
healthy then.

THE CONFOUND THIS TOOL HAS TO REMOVE
------------------------------------
Step length is not constant in our saved series.  Most steps are the ~3 h
round cadence, but a few are minutes apart because a round took two reads close
together.  A short step covers a smaller true increment, so the same stale read
is far more likely to show up as a NET decrease there.  Bunching regressions at
the end of the series therefore proves nothing if the short steps are also at
the end - which, in the 2026-09-22 series, one of them is.

So the tool computes the bunching probability twice: once over all steps, and
once over only the steps whose duration is within `--tol` of the median step
length.  The duration-matched number is the one to quote.  If dropping the odd
-length steps destroys the result, the result was about cadence, not the route.

USAGE
    python guide/counter_onset.py [--glob "api_stats_2026*.json"] [--tol 0.5]
"""
import argparse, datetime, glob, json, math, os

COUNTERS = ("jobs", "open", "briefs", "parsed", "claimed",
            "attested", "rejected", "delivered")
# `open` is a gauge; the rest are cumulative by name and should never fall.
CUMULATIVE = tuple(c for c in COUNTERS if c != "open")


def _stamp(path):
    """api_stats_20260922T031758Z.json -> 20260922T031758Z"""
    return os.path.basename(path)[len("api_stats_"):-len(".json")]


def load(pattern):
    rows = []
    for f in sorted(glob.glob(pattern), key=_stamp):
        d = json.load(open(f, encoding="utf-8"))
        s, o = d.get("stats") or {}, d.get("origin") or {}
        rows.append({"t": _stamp(f), "file": os.path.basename(f),
                     "engine": o.get("stats_engine_seq"),
                     "head": o.get("tape_head_seq"),
                     "c": {k: s.get(k) for k in COUNTERS}})
    return rows


def _dt(stamp):
    return datetime.datetime.strptime(stamp, "%Y%m%dT%H%M%SZ")


def steps(rows):
    out = []
    for i in range(1, len(rows)):
        a, b = rows[i - 1], rows[i]
        back = []
        for k in CUMULATIVE:
            x, y = a["c"].get(k), b["c"].get(k)
            if x is not None and y is not None and y < x:
                back.append({"counter": k, "from": x, "to": y, "drop": x - y})
        out.append({"from": a["t"], "to": b["t"], "regressions": back,
                    "hours": round((_dt(b["t"]) - _dt(a["t"])).total_seconds()
                                   / 3600.0, 2),
                    "engine_from": a["engine"], "engine_to": b["engine"]})
    return out


def _bunched(flags):
    """P(all R regressing steps are the last R) under uniform placement."""
    n, bad = len(flags), [i for i, f in enumerate(flags) if f]
    r = len(bad)
    if r == 0 or r == n or bad != list(range(n - r, n)):
        return None
    return {"steps": n, "regressing": r, "comb": math.comb(n, r),
            "p": 1.0 / math.comb(n, r), "as_fraction": "1/%d" % math.comb(n, r)}


def duration_matched(st, tol):
    """Re-run the bunching test over only the steps of near-median length."""
    hrs = sorted(s["hours"] for s in st)
    med = hrs[len(hrs) // 2]
    keep = [s for s in st if abs(s["hours"] - med) <= tol]
    dropped = [{"from": s["from"], "to": s["to"], "hours": s["hours"]}
               for s in st if s not in keep]
    return {"median_step_hours": med, "tolerance_hours": tol,
            "kept": len(keep), "dropped": dropped,
            "bunching": _bunched([bool(s["regressions"]) for s in keep])}


def report(rows, tol=0.5):
    st = steps(rows)
    n = len(st)
    bad = [i for i, s in enumerate(st) if s["regressions"]]
    r = len(bad)
    res = {"snapshots": len(rows), "steps": n,
           "span": (rows[0]["t"], rows[-1]["t"]) if rows else None,
           "regressing_steps": r,
           "detail": [st[i] for i in bad],
           "duration_matched": duration_matched(st, tol)}

    if r and bad == list(range(n - r, n)):
        dm = res["duration_matched"]["bunching"]
        res["pattern"] = "ALL %d REGRESSING STEPS ARE THE LAST %d OF %d" % (r, r, n)
        res["p_uniform"] = 1.0 / math.comb(n, r)
        res["p_as_fraction"] = "1/%d" % math.comb(n, r)
        res["onset_window"] = (st[bad[0]]["from"], st[bad[0]]["to"])
        if dm:
            res["verdict"] = (
                "ONSET, AND IT SURVIVES THE CADENCE CONTROL. All %d regressing "
                "steps are the last %d of %d (p %s under uniform placement). "
                "Restricting to the %d steps within %.1f h of the median length "
                "- which drops the short steps that make a stale read look like "
                "a decrease - it is still all %d at the end, p %s. The route "
                "began doing this between %s and %s."
                % (r, r, n, res["p_as_fraction"],
                   res["duration_matched"]["kept"], tol,
                   dm["regressing"], dm["as_fraction"],
                   res["onset_window"][0], res["onset_window"][1]))
        else:
            res["verdict"] = (
                "ONSET IN THE RAW SERIES ONLY - DO NOT PUBLISH AS AN ONSET. "
                "All %d regressing steps are the last %d of %d (p %s), but the "
                "bunching does not survive restricting to steps of near-median "
                "duration, so it may be an artifact of when we happened to take "
                "closely spaced reads." % (r, r, n, res["p_as_fraction"]))
    elif r == 0:
        res["pattern"] = "no regression anywhere in the saved series"
        res["verdict"] = ("NO EFFECT IN THIS SERIES. Note this is weak: two "
                          "reads can land on the same responding replica and "
                          "look monotone while the split is active.")
    else:
        res["pattern"] = "regressions at steps %s of %d" % (bad, n)
        res["verdict"] = ("SPREAD, NOT AN ONSET. Regressions occur through the "
                          "series, so this looks like a standing property of "
                          "the route rather than something it started.")
    return res


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--glob", default="api_stats_2026*.json")
    p.add_argument("--out", default="")
    p.add_argument("--tol", type=float, default=0.5)
    a = p.parse_args()
    rows = load(a.glob)
    if len(rows) < 3:
        raise SystemExit("need at least 3 snapshots, found %d" % len(rows))
    hdr = "%-18s %10s %8s %9s %7s %7s %7s %8s %6s" % (
        "snapshot", "engine", "jobs", "parsed", "claimed", "attested",
        "rejected", "delivered", "briefs")
    print(hdr)
    for x in rows:
        c = x["c"]
        print("%-18s %10s %8s %9s %7s %7s %7s %8s %6s" % (
            x["t"], x["engine"], c["jobs"], c["parsed"], c["claimed"],
            c["attested"], c["rejected"], c["delivered"], c["briefs"]))
    res = report(rows, a.tol)
    print()
    print(json.dumps(res, ensure_ascii=False, indent=1))
    if a.out:
        json.dump(res, open(a.out, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
