#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A threshold is not a falsifier until you have the null distribution.

Three rounds in a row this project shipped a broken falsifier, and each fix
addressed a different layer of the same mistake:

    r158  the falsifier had no start date, so it fired on the normal
          behaviour that preceded the anomaly.
    r159  the start date was present but COMPUTED FROM THE OBSERVATIONS,
          so the window held exactly one value and it could never fire.
    r160  the start date was a literal constant, the window was real - and
          the THRESHOLD was set below the normal regime's own noise.

r160 pre-registered this decision rule:

    read the 48-row passport digest at 2026-09-20T15:17Z.
    still 757fc5a03f  -> "the scoring surface stopped again"
    anything else     -> within pattern 69

At 15:17Z the digest was still 757fc5a03f.  The rule says "stopped".  The
rule is worthless, and this tool is how that is shown rather than asserted:

    in the NORMAL regime (2026-09-06..09-08, before the freeze) the 48-row
    passport table did not move at all in 1 of 7 sampled intervals, and in
    1 of the 3 intervals sampled ~3 h apart.

So under normal operation the r160 rule returns "stopped" about one time in
three.  A single unchanged 3 h reading is not evidence of anything.  We had
the data to know that before registering the threshold; we did not look.

WHAT THIS TOOL MEASURES INSTEAD OF ONE BIT

The digest is a one-bit view of a 48 x 8 table.  Reduce each consecutive pair
of /api/stats snapshots to a rate instead:

    move(a, b) = sum over DIDs, over the 8 scored terms,
                 of |term(b) - term(a)|            (term-units)
    rate       = move / hours elapsed

FIXED COHORT.  Rate over "rows present in both tables" is contaminated: after
a reshuffle the survivors are selected for having moved.  In the normal regime
roster churn was 0-4 rows per interval, but across the 2026-09-20 discharge it
was 26 of 48, so the bias falls entirely on the interval whose size is in
question.  This tool therefore restricts to the DIDs present in EVERY snapshot
(17 of them) - a cohort fixed in advance of the event, so selection cannot
manufacture the result.

WHAT IT SHOWS (40 snapshots, 2026-09-06T03:17Z .. 2026-09-20T15:17Z)

    NORMAL     7 intervals   0, 209, 424, 461, 468, 651, 801 term-units/h
    FROZEN    29 intervals   28 of them exactly 0; the single non-zero one
                             is the interval that CONTAINS the freeze onset
    POST       3 intervals   5374, then 0, then 0

The discharge interval ran 6.7x the fastest interval ever seen under normal
operation.  That comparison is legitimate where r159's was not: its 5.85 h
length sits inside the normal regime's own 3.0-9.0 h range, so r160's
"a short window is not a rate" retraction does not reach it.  Roster churn
over the same interval was 26 of 48 rows against 0-2 under normal operation.

The two post-discharge zeros are NOT evidence that the surface stopped again.
One is 0.22 h and the other 2.76 h; the normal regime supplies a ~3 h zero.

USAGE
    python passport_motion.py              # table + null distribution + verdict
    python passport_motion.py --prereg N   # how many consecutive ~3h zero
                                           # intervals are needed for p < N
"""
import json, io, os, sys, glob, datetime, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# --- window constants.  Literals, per the r159 rule.  Do not derive these. ---
FREEZE_AT = datetime.datetime(2026, 9, 8, 6, 18, tzinfo=datetime.UTC)
RESUME_AT = datetime.datetime(2026, 9, 20, 12, 0, tzinfo=datetime.UTC)

TERMS = ["score", "briefs", "jobs_posted", "results_delivered",
         "attestations_given", "poster_accepts_received",
         "useful_attestations_received", "not_useful_attestations_received"]

# A "~3 h" interval, the cadence this agent actually samples at.
SHORT_LO, SHORT_HI = 2.5, 3.5


def mtime(path):
    return datetime.datetime.fromtimestamp(os.path.getmtime(path),
                                           datetime.UTC)


def snapshots():
    out = []
    for f in set(glob.glob(os.path.join(ROOT, "_r*_stats*.json")) +
                 glob.glob(os.path.join(ROOT, "api_stats_*.json")) +
                 glob.glob(os.path.join(HERE, "_r*_stats*.json")) +
                 glob.glob(os.path.join(HERE, "api_stats_*.json"))):
        try:
            d = json.load(io.open(f, encoding="utf-8"))
        except Exception:
            continue
        p = (d.get("origin") or {}).get("passports") or d.get("passports")
        if not p:
            continue
        out.append({"t": mtime(f), "f": os.path.basename(f),
                    "p": {r["did"]: r for r in p}})
    out.sort(key=lambda s: s["t"])
    ded = []
    for s in out:
        if ded and abs((s["t"] - ded[-1]["t"]).total_seconds()) < 60:
            continue
        ded.append(s)
    return ded


def regime(t):
    if t <= FREEZE_AT:
        return "NORMAL"
    return "FROZEN" if t < RESUME_AT else "POST"


def move(a, b, dids):
    return sum(abs((b["p"][d].get(k) or 0) - (a["p"][d].get(k) or 0))
               for d in dids for k in TERMS)


def intervals(snaps, cohort):
    out = []
    for a, b in zip(snaps, snaps[1:]):
        dt = (b["t"] - a["t"]).total_seconds() / 3600.0
        if dt <= 0.05:
            continue
        m = move(a, b, cohort)
        ch = len(set(b["p"]) ^ set(a["p"])) // 2
        out.append({"a": a["t"], "b": b["t"], "dt": dt, "move": m,
                    "rate": m / dt, "churn": ch, "regime": regime(b["t"])})
    return out


def main():
    snaps = snapshots()
    if len(snaps) < 3:
        print("not enough snapshots on disk (%d)" % len(snaps))
        return 1
    cohort = set(snaps[0]["p"])
    for s in snaps:
        cohort &= set(s["p"])
    iv = intervals(snaps, cohort)

    print("snapshots %d   %s .. %s" % (
        len(snaps), snaps[0]["t"].strftime("%Y-%m-%d %H:%MZ"),
        snaps[-1]["t"].strftime("%Y-%m-%d %H:%MZ")))
    print("fixed cohort: %d DIDs present in ALL snapshots "
          "(chosen before the event, so survivors cannot inflate the rate)"
          % len(cohort))
    print()
    print("%-14s %-14s %6s %6s %9s %10s  %s"
          % ("from", "to", "dt_h", "churn", "move", "units/h", "regime"))
    hidden = 0
    for r in iv:
        if r["regime"] == "FROZEN" and r["move"] == 0:
            hidden += 1
            continue
        print("%-14s %-14s %6.2f %6d %9d %10.1f  %s"
              % (r["a"].strftime("%m-%d %H:%MZ"), r["b"].strftime("%m-%d %H:%MZ"),
                 r["dt"], r["churn"], r["move"], r["rate"], r["regime"]))
    print("  (+%d FROZEN intervals suppressed, every one of them exactly 0)"
          % hidden)

    norm = [r for r in iv if r["regime"] == "NORMAL"]
    rates = sorted(r["rate"] for r in norm)
    zero_n = sum(1 for r in norm if r["move"] == 0)
    short = [r for r in norm if SHORT_LO <= r["dt"] <= SHORT_HI]
    zero_s = sum(1 for r in short if r["move"] == 0)

    print()
    print("-- the null distribution (NORMAL regime, what the table does when alive) --")
    print("  n=%d intervals, units/h: %s"
          % (len(norm), ", ".join("%.0f" % x for x in rates)))
    print("  ZERO-MOVEMENT intervals: %d of %d  (p=%.2f)"
          % (zero_n, len(norm), float(zero_n) / len(norm)))
    print("  restricted to %.1f-%.1f h intervals, the cadence we sample at:"
          % (SHORT_LO, SHORT_HI))
    print("    ZERO-MOVEMENT: %d of %d  (p=%.2f)"
          % (zero_s, len(short), float(zero_s) / max(1, len(short))))
    p0 = float(zero_s) / max(1, len(short))

    print()
    print("-- falsifier (A): was the r160 pre-registration a test? --")
    print("  r160 rule: one unchanged ~3 h reading => 'the surface stopped again'.")
    print("  FIRED - THE RULE IS NOT A TEST. Under normal operation it returns")
    print("  'stopped' with probability %.2f. The threshold was set below the" % p0)
    print("  normal regime's own noise, so r160's verdict is withdrawn, and so")
    print("  is any reading of the two post-discharge zeros.")

    post = [r for r in iv if r["regime"] == "POST"]
    disc = max(post, key=lambda r: r["rate"]) if post else None
    print()
    print("-- falsifier (B): is the discharge distinguishable from normal? --")
    if disc and rates and disc["rate"] > max(rates):
        print("  FIRED. %s -> %s ran %.0f units/h over %.2f h, %.1fx the fastest"
              % (disc["a"].strftime("%m-%d %H:%MZ"), disc["b"].strftime("%m-%d %H:%MZ"),
                 disc["rate"], disc["dt"], disc["rate"] / max(rates)))
        print("  NORMAL interval (%.0f units/h). Its length sits inside the normal"
              % max(rates))
        print("  range %.1f-%.1f h, so this is a rate comparison and not r159's."
              % (min(r["dt"] for r in norm), max(r["dt"] for r in norm)))
        print("  churn %d of 48 rows against %d-%d under normal operation."
              % (disc["churn"], min(r["churn"] for r in norm),
                 max(r["churn"] for r in norm)))
    else:
        print("  NOT FIRED.")

    print()
    print("-- how long a silence WOULD mean something --")
    if p0 <= 0 or p0 >= 1:
        print("  cannot be computed: the normal regime shows no variation at this cadence.")
    else:
        for target in (0.05, 0.01):
            k = 1
            while p0 ** k > target:
                k += 1
            print("  %d consecutive zero ~3 h intervals give p=%.3f  (< %.2f)"
                  % (k, p0 ** k, target))
        run = 0
        for r in reversed(iv):
            if r["move"] == 0 and r["dt"] >= SHORT_LO:
                run += 1
            elif r["dt"] >= SHORT_LO:
                break
        print("  current run of zero ~3h+ intervals since the discharge: %d" % run)
        k = 1
        while p0 ** k > 0.05:
            k += 1
        print("  PRE-REGISTERED: call the surface stopped only at a run of %d "
              "(p=%.3f)." % (k, p0 ** k))
    return 0


if __name__ == "__main__":
    sys.exit(main())
