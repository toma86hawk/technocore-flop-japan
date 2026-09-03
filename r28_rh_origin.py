#!/usr/bin/env python3
"""Round 28. Before anything is published about rh:ac1dc357d283d229, settle
what the archived `rh` field actually IS.

attest_collect.py's own docstring records that an earlier tape-scraping
version recomputed rh as sha256(body)[:16] instead of copying the board's
authoritative result_hash. If the old snapshots carry that recomputed value,
then ac1dc357d283d229 is simply the hash of one very common boilerplate
delivery body - and our evasion #1, catalogued 2026-08-29 as "constant-paste
rh by an attestor", is misattributed: the duplication is on the DELIVERY
side, and the attestor copying it is being honest.

Test: for archived pairs, does sha256(body)[:16] reproduce the stored rh?
"""
import json, glob, hashlib, collections

TARGET = "ac1dc357d283d229"

def sha16(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]

recomputed_ok = recomputed_bad = 0
bodies_for_target = collections.Counter()
examples = []
for p in sorted(glob.glob("attest_runs/*.json")):
    try:
        d = json.load(open(p, encoding="utf-8"))
    except Exception:
        continue
    rows = d.get("queue", []) if isinstance(d, dict) else (d if isinstance(d, list) else [])
    for q in rows:
        if not isinstance(q, dict):
            continue
        rh = q.get("rh") or q.get("result_hash")
        body = q.get("result")
        if body is None:
            dl = q.get("deliver") or {}
            body = dl.get("body") or dl.get("text")
        if not rh or not isinstance(body, str):
            continue
        for cand, label in ((body, "raw"), (body.strip(), "strip")):
            if sha16(cand) == rh:
                recomputed_ok += 1
                if len(examples) < 3:
                    examples.append((p, q.get("job_id") or (q.get("job") or {}).get("id"), label))
                break
        else:
            recomputed_bad += 1
        if rh == TARGET:
            bodies_for_target[body.strip()[:160]] += 1

print(f"archived (rh, body) pairs where sha256(body)[:16] == rh : {recomputed_ok}")
print(f"                                     ... does NOT match : {recomputed_bad}")
for p, j, lab in examples:
    print(f"   e.g. {j} in {p} ({lab})")

print(f"\nbodies carrying rh:{TARGET} in the archives: "
      f"{sum(bodies_for_target.values())} rows, "
      f"{len(bodies_for_target)} distinct bodies")
for b, c in bodies_for_target.most_common(4):
    print(f"   x{c}  {b!r}")

if len(bodies_for_target) == 1:
    print("\n=> ONE body. The value is the hash of a single mass-reused delivery "
          "string.\n   The duplication is on the DELIVERY side. An attestor "
          "quoting this rh\n   on many jobs is reporting it CORRECTLY.")
elif recomputed_ok == 0 and recomputed_bad:
    print("\n=> the archived rh is NOT sha256(body); it is board-published. "
          "Constant-paste\n   by the attestor stays the live hypothesis.")

json.dump({"target": TARGET, "sha_matches": recomputed_ok,
           "sha_mismatches": recomputed_bad,
           "distinct_bodies_for_target": len(bodies_for_target),
           "bodies": bodies_for_target.most_common(6)},
          open("r28_rh_origin.json", "w"), indent=1)
print("\nwrote r28_rh_origin.json")
