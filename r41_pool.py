# -*- coding: utf-8 -*-
"""Delivery-side pool detector: group delivered bodies by rh = sha256(body)[:16]
and count how many DISTINCT worker DIDs file the same body. Cross-identity reuse
is a one-column GROUP BY - no content judgement, no model."""
import json, sys, hashlib, collections
sys.stdout.reconfigure(encoding="utf-8")

m = json.load(open("r41_export.json", encoding="utf-8"))
seqs = [x["seq"] for x in m]
print("window seq %d-%d  %s..%s  msgs %d" % (min(seqs), max(seqs), m[0]["ts"], m[-1]["ts"], len(m)))

rows = []           # (job_id, did, body, rh)
for x in m:
    t = x.get("text") or ""
    if not (t.startswith("RESULT v1") or t.startswith("DELIVER v1")):
        continue
    parts = t.split(" | ")
    if len(parts) < 3:
        continue
    job = parts[1].strip()
    body = " | ".join(parts[2:]).strip()
    if not body:
        continue
    rh = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
    rows.append((job, x.get("from"), body, rh))
print("delivery lines parsed", len(rows))

by_rh = collections.defaultdict(list)
for job, did, body, rh in rows:
    by_rh[rh].append((job, did, body))

multi_did = {rh: v for rh, v in by_rh.items() if len({d for _, d, _ in v}) >= 2}
covered = sum(len(v) for v in multi_did.values())
dids = {d for v in multi_did.values() for _, d, _ in v}
jobs = {j for v in multi_did.values() for j, _, _ in v}
print("bodies used by >=2 distinct DIDs: %d clusters, %d delivery lines (%.1f%% of all), %d DIDs, %d jobs"
      % (len(multi_did), covered, 100.0 * covered / max(1, len(rows)), len(dids), len(jobs)))

same_did = {rh: v for rh, v in by_rh.items() if len(v) > 1 and len({d for _, d, _ in v}) == 1}
print("bodies repeated by ONE DID only: %d clusters, %d lines (%.1f%%)"
      % (len(same_did), sum(len(v) for v in same_did.values()),
         100.0 * sum(len(v) for v in same_did.values()) / max(1, len(rows))))

print("\ntop cross-DID clusters (dids / lines / jobs):")
for rh, v in sorted(multi_did.items(), key=lambda kv: -len({d for _, d, _ in kv[1]}))[:12]:
    d = len({x[1] for x in v})
    print("  rh:%s  dids=%-3d lines=%-4d jobs=%-4d  %s" %
          (rh, d, len(v), len({x[0] for x in v}), v[0][2][:110].replace("\n", " ")))

# how many DIDs draw from more than one shared cluster -> a shared dictionary, not one leaked string
did_clusters = collections.defaultdict(set)
for rh, v in multi_did.items():
    for _, d, _ in v:
        did_clusters[d].add(rh)
multi = {d: c for d, c in did_clusters.items() if len(c) >= 2}
print("\nDIDs drawing from >=2 different shared bodies: %d of %d" % (len(multi), len(did_clusters)))
for d, c in sorted(multi.items(), key=lambda kv: -len(kv[1]))[:10]:
    print("  ...%s  %d shared bodies" % (d[-12:], len(c)))
json.dump({"window": [min(seqs), max(seqs)], "lines": len(rows),
           "cross_did_clusters": {rh: {"dids": sorted({x[1] for x in v}), "jobs": sorted({x[0] for x in v}),
                                       "body": v[0][2][:400]} for rh, v in multi_did.items()}},
          open("r41_pool.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
