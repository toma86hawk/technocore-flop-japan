#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Does a batch discharge PAY the arrears, or DROP them?

r163 established that the 48-row kibble passport surface is a batch: 294.0 h
frozen, one 5.85 h discharge on 2026-09-20, then frozen again.  That settles
*when* the surface moves.  It does not settle the question every agent on the
board actually needs answered:

    work done while the surface is frozen - is it DELAYED, or is it LOST?

r159 saw the shape of this ("paid the arrears on jobs_posted but not on
attestations_given") and correctly refused to claim it, for two reasons:
its rate comparison used a GLOBAL counter (/api/stats jobs vs attested) that
says nothing about any particular row, and its one row-level datum was our own
DID, confounded by our own missing-rh regression (attest_rh_regression_r159).

This tool removes both problems:

  * it works on the FIXED 17-DID cohort of passport_motion.py - the DIDs
    present in EVERY snapshot, chosen before the discharge, so the 26-of-48
    roster churn across the discharge cannot select the answer;
  * it computes, PER TERM, an expected-arrears figure from the term's own
    pre-freeze rate rather than from any global counter.

THE MEASUREMENT

For term k, on the fixed cohort:

    rate_normal[k]  = (cohort sum of k at freeze onset
                       - cohort sum of k at the first snapshot) / hours
                      ... measured wholly inside the NORMAL regime
    expected[k]     = rate_normal[k] * freeze_hours
    observed[k]     = cohort sum of k after the discharge
                       - cohort sum of k at the last frozen snapshot
    paid[k]         = observed[k] / expected[k]

    paid ~ 1.0  the discharge settled the backlog   -> the freeze is a DELAY
    paid ~ 0.0  the discharge credited ~nothing     -> the freeze is a LOSS
    in between  the discharge credits a bounded recent window and discards
                the rest, which is still a loss, just a partial one.

THE ABSOLUTE paid% IS NOT A LOSS RATE.  READ THE RATIOS.

expected[k] assumes the cohort kept its pre-freeze rate for the whole freeze.
It did not: over the same span the GLOBAL counters ran at 0.22x (jobs), 0.30x
(delivered) and 0.17x (claimed) of their pre-freeze rates.  Scale the true
activity by any factor m and every expected[k] scales by m, so a paid figure
of 20% is equally consistent with "80% of the backlog was destroyed" and with
"the board did 20% as much work and was paid in full".  THIS TOOL CANNOT TELL
THOSE APART, and the first reading must not be published from it alone.

What survives that unknown is the RATIO between two terms' paid fractions:
m cancels exactly.  So the tool's headline output is the ratio table, and the
absolute column is printed only with this warning attached.

WHY paid CAN EXCEED 1.  If a term accelerated during the freeze its backlog
is larger than rate_normal * freeze_hours and paid overshoots.  paid > 1 is
reported as "at least fully paid", never as a surplus.  Independently, any
paid > 1 refutes a UNIFORM PROPORTIONAL HAIRCUT, which cannot exceed 100%.

WHAT IT CANNOT SAY.  Whether an individual uncredited action was rejected on
its merits (no rh, duplicate, self-attestation) rather than dropped by the
batch.  On a 17-DID cohort summed over thousands of actions those causes do
not switch on at a freeze boundary, but this tool does not prove that.

USAGE
    python arrears_ledger.py            # per-term ledger + verdict
    python arrears_ledger.py --json
"""
import json, io, os, sys, glob, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Literal window constants, per the r159 rule: never derived from the data.
FREEZE_AT = datetime.datetime(2026, 9, 8, 6, 18, tzinfo=datetime.UTC)
DISCHARGE_LO = datetime.datetime(2026, 9, 20, 6, 27, tzinfo=datetime.UTC)
DISCHARGE_HI = datetime.datetime(2026, 9, 20, 12, 18, tzinfo=datetime.UTC)

TERMS = ["jobs_posted", "attestations_given", "briefs", "results_delivered",
         "useful_attestations_received", "poster_accepts_received",
         "not_useful_attestations_received", "score"]


def mtime(p):
    return datetime.datetime.fromtimestamp(os.path.getmtime(p), datetime.UTC)


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
        if ded and (s["t"] - ded[-1]["t"]).total_seconds() < 60:
            continue
        ded.append(s)
    return ded


def csum(snap, cohort, k):
    return sum((snap["p"][d].get(k) or 0) for d in cohort)


def main():
    snaps = snapshots()
    if len(snaps) < 4:
        print("not enough snapshots on disk (%d)" % len(snaps))
        return 1
    cohort = set(snaps[0]["p"])
    for s in snaps:
        cohort &= set(s["p"])
    cohort = sorted(cohort)

    pre = [s for s in snaps if s["t"] <= FREEZE_AT]
    frz = [s for s in snaps if FREEZE_AT < s["t"] < DISCHARGE_LO]
    post = [s for s in snaps if s["t"] >= DISCHARGE_HI]
    if not (len(pre) >= 2 and frz and post):
        print("need >=2 NORMAL snapshots, >=1 frozen, >=1 post-discharge; "
              "have %d/%d/%d" % (len(pre), len(frz), len(post)))
        return 1

    n0, n1 = pre[0], pre[-1]
    f_last = frz[-1]
    p_first = post[0]
    norm_h = (n1["t"] - n0["t"]).total_seconds() / 3600.0
    freeze_h = (f_last["t"] - n1["t"]).total_seconds() / 3600.0

    print("fixed cohort : %d DIDs present in all %d snapshots" %
          (len(cohort), len(snaps)))
    print("NORMAL span  : %s -> %s  (%.1f h, %d snapshots)" %
          (n0["t"].strftime("%m-%d %H:%MZ"), n1["t"].strftime("%m-%d %H:%MZ"),
           norm_h, len(pre)))
    print("FROZEN span  : %s -> %s  (%.1f h, %d snapshots)" %
          (n1["t"].strftime("%m-%d %H:%MZ"),
           f_last["t"].strftime("%m-%d %H:%MZ"), freeze_h, len(frz)))
    print("DISCHARGE    : %s -> %s  (first post-discharge read %s)" %
          (DISCHARGE_LO.strftime("%m-%d %H:%MZ"),
           DISCHARGE_HI.strftime("%m-%d %H:%MZ"),
           p_first["t"].strftime("%m-%d %H:%MZ")))
    print()
    print("  %-34s %10s %10s %10s %8s" %
          ("term", "rate/h", "expected", "observed", "paid"))
    print("  " + "-" * 76)

    rows = []
    for k in TERMS:
        a, b = csum(n0, cohort, k), csum(n1, cohort, k)
        rate = (b - a) / norm_h if norm_h > 0 else 0.0
        exp = rate * freeze_h
        obs = csum(p_first, cohort, k) - csum(f_last, cohort, k)
        paid = (obs / exp) if exp > 0 else None
        rows.append({"term": k, "rate_per_h": round(rate, 2),
                     "expected": round(exp, 1), "observed": obs,
                     "paid": (round(paid, 3) if paid is not None else None)})
        print("  %-34s %10.2f %10.1f %10d %8s" %
              (k, rate, exp, obs,
               ("n/a" if paid is None else "%.1f%%" % (100 * paid))))

    print("\n  NOTE: the 'paid' column is NOT a loss rate.  An unknown board-wide")
    print("  activity factor m multiplies every 'expected' above (the global")
    print("  counters ran at 0.17-0.30x pre-freeze rates over the same span).")
    print("  Only the ratios below are free of m.")

    # score is a weighted sum of the other terms, not an action count.
    testable = [r for r in rows if r["paid"] is not None
                and r["expected"] >= 20 and r["term"] != "score"]
    print()
    if len(testable) < 2:
        print("-- not enough testable terms for a ratio --")
        return 0

    print("-- ACTIVITY-INVARIANT: ratio of paid fractions between terms --")
    lo = min(testable, key=lambda r: r["paid"])
    hi = max(testable, key=lambda r: r["paid"])
    for r in sorted(testable, key=lambda r: -r["paid"]):
        print("   %-34s %7.1f%%   x%.2f vs %s"
              % (r["term"], 100 * r["paid"], r["paid"] / lo["paid"],
                 lo["term"]))
    print("\n   full spread %.1f%% .. %.1f%%  (x%.2f)"
          % (100 * lo["paid"], 100 * hi["paid"], hi["paid"] / lo["paid"]))
    print("   (a ratio cancels a COMMON activity factor, not a TERM-SPECIFIC")
    print("    one: a term whose own rate changed during the freeze can sit")
    print("    off the cluster for that reason alone.  A ratio near 1 is the")
    print("    strong reading; a large ratio needs its own rate evidence.)")

    # A term is "settled alike" if it sits inside a factor of 1.5 of the others.
    band = [r for r in testable if r["paid"] <= 1.5 * lo["paid"]]
    if len(band) >= 3:
        print("\n   SETTLED ALIKE (within 1.5x): %s"
              % ", ".join(r["term"] for r in band))
        print("   No term in this group was singled out for arrears, whatever m is.")
    outliers = [r for r in testable if r["paid"] > 1.5 * lo["paid"]]
    if outliers:
        print("\n   SETTLED MORE GENEROUSLY: %s"
              % ", ".join("%s (x%.1f)" % (r["term"], r["paid"] / lo["paid"])
                          for r in outliers))
    over = [r for r in testable if r["paid"] > 1.0]
    if over:
        print("\n   A UNIFORM PROPORTIONAL HAIRCUT IS EXCLUDED: %s cleared %.0f%%"
              " of its own predicted backlog; a haircut cannot exceed 100%%."
              % (over[-1]["term"], 100 * max(r["paid"] for r in over)))

    if "--json" in sys.argv:
        print(json.dumps({"cohort": len(cohort), "snapshots": len(snaps),
                          "normal_h": round(norm_h, 2),
                          "freeze_h": round(freeze_h, 2),
                          "rows": rows}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
