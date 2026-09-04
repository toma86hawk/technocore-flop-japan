"""r31: when did 'Posted by host timer' jobs first appear, and on what topics?

Several jobs in the 2026-09-04 12:02 board window restate findings we published
in the guide README (claimant-only RESULT, franchise gate, result_hash
clustering, ingest stall = parsed frozen while the room still accepts lines).
Before reading anything into that, establish whether host-timer jobs are new at
all, by walking every board snapshot we have kept.
"""
import json, glob, io, os, re, sys, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

rows = []
for f in sorted(glob.glob("attest_runs/*.json")):
    try:
        d = json.load(io.open(f, encoding="utf-8"))
    except Exception:
        continue
    jobs = d if isinstance(d, list) else (d.get("jobs") or d.get("board") or d.get("pairs") or [])
    if isinstance(jobs, dict): jobs = list(jobs.values())
    n = ht = 0
    titles = []
    for j in jobs:
        if not isinstance(j, dict): continue
        n += 1
        blob = (j.get("spec") or "") + " " + (j.get("title") or "")
        if "host timer" in blob:
            ht += 1
            titles.append(j.get("title"))
    stamp = os.path.basename(f).replace(".json", "")
    rows.append((stamp, n, ht, titles))

print(f"{'snapshot':22s} {'jobs':>5s} {'host-timer':>10s}")
for s, n, ht, t in rows:
    print(f"{s:22s} {n:5d} {ht:10d}")

first = next((r for r in rows if r[2] > 0), None)
print()
if first:
    print(f"FIRST host-timer job appears in snapshot {first[0]}")
else:
    print("no host-timer jobs in any kept snapshot")
print()
print("host-timer titles in the newest snapshot that has them:")
for s, n, ht, t in reversed(rows):
    if ht:
        for x in t: print("  -", x)
        break
