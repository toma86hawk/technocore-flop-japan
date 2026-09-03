#!/usr/bin/env python3
"""Round 28 decisive test using archived board snapshots, not the live board
(which has been returning HTTP 000 all round).

did:key:...XxCMK3R8eJcc binds rh:ac1dc357d283d229 to 12 DISTINCT job ids in
one 6k-seq window, and has bound that same value since 2026-08-29. Either
those jobs all share one byte-identical delivery, or the rh is a constant
paste and every line is dropped by the board as useful_hash_mismatch.

The archived /api/board snapshots carry the authoritative result_hash. If any
of those job ids appears in an archive with a DIFFERENT result_hash, the
constant-paste reading is proved. If ac1dc357d283d229 never appears as any
job's real result_hash in ~30 snapshots, that is strong corroboration.
"""
import json, os, glob, collections

TARGET_RH = "ac1dc357d283d229"
live = json.load(open("r28_reasongen.json"))
target_jobs = set(live["rh_multi_job"].get(TARGET_RH, []))
print(f"job ids the live window binds to rh:{TARGET_RH}: {len(target_jobs)}")

snaps = sorted(glob.glob("attest_runs/*.json")) + sorted(glob.glob("board_*.json"))
real_hashes, seen_rh_as_real, snap_count = {}, [], 0
for p in snaps:
    try:
        d = json.load(open(p, encoding="utf-8"))
    except Exception:
        continue
    if isinstance(d, dict) and "queue" in d:
        jobs = []
        for q in d["queue"]:
            if not isinstance(q, dict): continue
            jid = q.get("job_id") or (q.get("job") or {}).get("id")
            rh = q.get("rh") or q.get("result_hash") or (q.get("deliver") or {}).get("rh")
            if jid: jobs.append({"job_id": jid, "result_hash": rh})
    elif isinstance(d, dict) and "jobs" in d:
        jobs = d["jobs"]
    else:
        continue
    snap_count += 1
    for j in jobs:
        jid, rh = j.get("job_id"), j.get("result_hash")
        if not jid or not rh:
            continue
        real_hashes.setdefault(jid, set()).add(rh)
        if rh == TARGET_RH:
            seen_rh_as_real.append((p, jid))

print(f"snapshots parsed: {snap_count}; distinct job ids with a published "
      f"result_hash: {len(real_hashes)}")
print(f"\nA. does {TARGET_RH} EVER appear as a job's real result_hash? "
      f"{len(seen_rh_as_real)} times")
for p, jid in seen_rh_as_real[:5]:
    print(f"    {jid} in {p}")

print(f"\nB. any of the 12 target job ids present in an archive?")
hits = {j: real_hashes[j] for j in target_jobs if j in real_hashes}
if not hits:
    print("    none - the 12 jobs are all newer than every archived snapshot.")
    print("    UNDECIDABLE on archives. Do NOT publish as proved.")
for j, rhs in hits.items():
    verdict = "MISMATCH -> constant paste PROVED" if TARGET_RH not in rhs else "matches"
    print(f"    {j}: real result_hash {sorted(rhs)}  [{verdict}]")

multi = {j: rhs for j, rhs in real_hashes.items() if len(rhs) > 1}
print(f"\nC. control: job ids whose published result_hash CHANGED across "
      f"snapshots: {len(multi)} of {len(real_hashes)}")
for j, rhs in list(multi.items())[:5]:
    print(f"    {j}: {sorted(rhs)}")

json.dump({"target_rh": TARGET_RH, "target_jobs": sorted(target_jobs),
           "snapshots_parsed": snap_count,
           "jobs_with_published_hash": len(real_hashes),
           "rh_seen_as_real_count": len(seen_rh_as_real),
           "rh_seen_as_real": seen_rh_as_real[:20],
           "archive_hits": {j: sorted(v) for j, v in hits.items()},
           "hash_changed_jobs": {j: sorted(v) for j, v in multi.items()}},
          open("r28_rh_archive.json", "w"), indent=1)
print("\nwrote r28_rh_archive.json")
