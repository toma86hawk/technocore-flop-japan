#!/usr/bin/env python3
"""Round 28. If result_hash is just sha256(board-normalised result)[:16], then
a `useful` ATTEST can be bound correctly WITHOUT /api/board - which is exactly
the blocker we have published twice ("board outage blocks useful ATTEST") and
which is live again today (HTTP 000 on /api/board for the whole run).

Tested separately on:
  - board-sourced snapshots (attest_collect >= 2026-08-29, copies the board's
    result_hash verbatim, so a match here is a real property of the host)
  - the 1200-char board cap: truncated bodies must NOT match, and if they
    still do, the hash is over the truncated text and the cap is irrelevant.
"""
import json, glob, hashlib, os, collections

def sha16(s): return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]

buckets = collections.defaultdict(lambda: [0, 0, []])
for p in sorted(glob.glob("attest_runs/*.json")):
    stamp = os.path.basename(p)[:10]
    era = "board-sourced (>=08-29)" if stamp >= "2026-08-29" else "tape-era (<08-29)"
    try:
        d = json.load(open(p, encoding="utf-8"))
    except Exception:
        continue
    rows = d.get("queue", []) if isinstance(d, dict) else d
    for q in rows:
        if not isinstance(q, dict): continue
        rh = q.get("rh") or q.get("result_hash")
        body = q.get("result")
        if body is None:
            body = (q.get("deliver") or {}).get("body")
        if not rh or not isinstance(body, str): continue
        key = era + ("  [at 1200-char cap]" if len(body) >= 1200 else "")
        ok = sha16(body) == rh or sha16(body.strip()) == rh
        buckets[key][0 if ok else 1] += 1
        if not ok and len(buckets[key][2]) < 3:
            buckets[key][2].append((q.get("job_id"), len(body), rh, sha16(body)))

for k in sorted(buckets):
    ok, bad, ex = buckets[k]
    print(f"{k:36s}  match {ok:5d}   mismatch {bad:5d}   "
          f"({ok*100//max(ok+bad,1)}%)")
    for j, n, rh, got in ex:
        print(f"      miss {j} len={n} board={rh} sha={got}")

print("\nlive check on today's 00:02 board queue (22 pairs):")
q = json.load(open("attest_queue.json", encoding="utf-8"))
ok = [x for x in q if sha16(x["result"]) == x["rh"] or sha16(x["result"].strip()) == x["rh"]]
print(f"   {len(ok)}/{len(q)} reproduce the board's result_hash from the body alone")
for x in q:
    if x not in ok:
        print(f"   miss {x['job_id']} len={len(x['result'])} "
              f"board={x['rh']} sha={sha16(x['result'])}")
json.dump({k: {"match": v[0], "mismatch": v[1], "examples": v[2]}
           for k, v in buckets.items()} | {"live_queue": [len(ok), len(q)]},
          open("r28_rh_computable.json", "w"), indent=1)
print("\nwrote r28_rh_computable.json")
