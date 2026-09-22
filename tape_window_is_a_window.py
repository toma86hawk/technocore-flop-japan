# -*- coding: utf-8 -*-
"""Is each saved /api/tape?limit=1500 response a RECENT window of the tape?

useful_on_thin is published as a time series.  That only means anything if the
response the metric reads moves forward with wall clock.  Two live probes this
round found /api/tape?limit=20 returning seq 1..20 - the twenty OLDEST rows on a
tape whose head is near 9,991,418 - so "limit=N" is not obviously a tail read,
and the whole series depends on which end it reads from.

The 137 saved raw windows answer this offline.  For each, in timestamp order:
seq_lo, seq_hi, and whether seq_hi advanced since the previous window.  A tail
read gives a monotonically rising seq_hi.  Anything else means the series is not
indexed by time.

Offline.  Reads useful_on_thin_*.json in the repo root.
"""
import json, glob, os, sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
rows = []
for path in sorted(glob.glob(os.path.join(root, "useful_on_thin_*.json"))):
    stamp = os.path.basename(path)[len("useful_on_thin_"):-len(".json")]
    try:
        d = json.load(open(path, encoding="utf-8", errors="replace"))
    except Exception:
        continue
    seqs = sorted(m["seq"] for m in d.get("messages", []) if m.get("seq") is not None)
    if not seqs:
        continue
    rows.append({"stamp": stamp, "rows": len(seqs), "lo": seqs[0], "hi": seqs[-1],
                 "span": seqs[-1] - seqs[0] + 1, "gaps": seqs[-1] - seqs[0] + 1 - len(seqs)})

print("windows:", len(rows))
adv = back = same = 0
backsteps = []
for a, b in zip(rows, rows[1:]):
    if b["hi"] > a["hi"]:
        adv += 1
    elif b["hi"] < a["hi"]:
        back += 1
        backsteps.append((a["stamp"], a["hi"], b["stamp"], b["hi"]))
    else:
        same += 1
print("seq_hi advanced: %d   went backwards: %d   unchanged: %d" % (adv, back, same))
if backsteps:
    print("backward steps (first 8):")
    for x in backsteps[:8]:
        print("   %s hi=%d  ->  %s hi=%d" % x)

lo_small = [r for r in rows if r["lo"] < 10000]
print("windows whose seq_lo is below 10,000 (i.e. reaching the start of the tape): %d" % len(lo_small))
for r in lo_small[:8]:
    print("   %s  lo=%d hi=%d rows=%d" % (r["stamp"], r["lo"], r["hi"], r["rows"]))

gapped = [r for r in rows if r["gaps"] > 0]
print("windows with gaps inside their own span: %d of %d" % (len(gapped), len(rows)))

print()
print("%-14s %6s %12s %12s %10s %10s" % ("stamp", "rows", "seq_lo", "seq_hi", "span", "gaps"))
for r in rows[:5] + [None] + rows[-8:]:
    if r is None:
        print("   ...")
        continue
    print("%-14s %6d %12d %12d %10d %10d" % (r["stamp"], r["rows"], r["lo"], r["hi"],
                                             r["span"], r["gaps"]))

print()
print("READING:")
if back == 0 and len(lo_small) == 0:
    print("  seq_hi never regresses and no window reaches the start of the tape:")
    print("  limit=1500 IS a tail read and the series is indexed by time.")
else:
    print("  the response is NOT a simple tail read: %d backward steps and %d windows"
          % (back, len(lo_small)))
    print("  reaching the start of the tape. Each affected point is not 'the window at")
    print("  that time' and cannot be read as one.")
