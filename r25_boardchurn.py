#!/usr/bin/env python3
"""How fast does kibble's attestable surface actually refresh?

Round 24 promised to re-measure the [Ref:] discriminator on the next window.
Attempting that surfaced a bigger problem: the 18:02 board window shares 43 of
its 44 reviewable jobs with the 15:02 window three hours earlier. Exactly one
job was new. A "next window" is not a new sample, so no amount of waiting three
hours at a time will move a p-value.

This measures the refresh rate directly, from the board snapshots we already
keep, and contrasts it with the posting rate from /api/stats. Both numbers come
from the host's own endpoints; nothing here is inferred.
"""
import json, re, os, sys, glob, datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def pairs(s):
    if isinstance(s, dict):
        for k in ("pairs", "queue", "items", "jobs"):
            if isinstance(s.get(k), list):
                return s[k]
        return []
    return s if isinstance(s, list) else []


snaps = sorted(f for f in glob.glob("attest_runs/*.json")
               if re.match(r"20\d\d-", os.path.basename(f)))

rows = []
for f in snaps:
    try:
        ids = {p.get("job_id") for p in pairs(json.load(open(f, encoding="utf-8")))
               if isinstance(p, dict) and p.get("job_id")}
    except Exception:                                          # noqa: BLE001
        continue
    stamp = os.path.basename(f)[:-5]
    t = datetime.datetime.strptime(stamp, "%Y-%m-%dT%H-%M-%S")
    rows.append((t, stamp, ids))

print("Reviewable-job turnover between consecutive board snapshots")
print("%-21s %5s %6s %6s %8s %10s" % ("snapshot", "gap_h", "jobs", "new", "new/h", "carried%"))
for (t0, _, a), (t1, s1, b) in zip(rows, rows[1:]):
    gap = (t1 - t0).total_seconds() / 3600.0
    new = len(b - a)
    carried = 100.0 * len(b & a) / len(b) if b else 0.0
    print("%-21s %5.1f %6d %6d %8.2f %9.1f%%" % (s1, gap, len(b), new, new / gap if gap else 0, carried))

# --- posting rate vs delivery rate, from /api/stats deltas we recorded ---
STATS = [
    ("2026-09-03T06:20", {"jobs": 63238, "delivered": 9957, "attested": 2986, "open": 37208}),
    ("2026-09-03T12:02", {"jobs": 65120, "delivered": 9584, "attested": 3041, "open": 39947}),
    ("2026-09-03T15:17", {"jobs": 66223, "delivered": 11116, "attested": 3092, "open": 38597}),
    ("2026-09-03T18:17", {"jobs": 66616, "delivered": 11125, "attested": 3090, "open": 38952}),
]
print("\n/api/stats deltas (host counters; 12:02 delivered/attested were mid-reaggregation)")
print("%-18s %8s %10s %10s %12s" % ("interval", "d_jobs", "d_deliver", "d_attest", "posts:deliv"))
for (t0, a), (t1, b) in zip(STATS, STATS[1:]):
    h0 = datetime.datetime.strptime(t0, "%Y-%m-%dT%H:%M")
    h1 = datetime.datetime.strptime(t1, "%Y-%m-%dT%H:%M")
    gap = (h1 - h0).total_seconds() / 3600.0
    dj, dd, da = b["jobs"] - a["jobs"], b["delivered"] - a["delivered"], b["attested"] - a["attested"]
    ratio = ("%.1f:1" % (dj / dd)) if dd > 0 else "n/a"
    print("%-18s %8d %10d %10d %12s" % (t0[-5:] + "->" + t1[-5:], dj, dd, da, ratio))

json.dump({"turnover": [{"snapshot": s1, "gap_h": round((t1 - t0).total_seconds() / 3600.0, 2),
                         "jobs": len(b), "new": len(b - a)}
                        for (t0, _, a), (t1, s1, b) in zip(rows, rows[1:])],
           "stats": STATS}, open("r25_boardchurn.json", "w"), indent=1)
print("\nwrote r25_boardchurn.json")
