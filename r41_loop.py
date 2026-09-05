# -*- coding: utf-8 -*-
import json, sys, collections, hashlib, re
sys.stdout.reconfigure(encoding="utf-8")
FLEET = set(json.load(open("r41_ring.json", encoding="utf-8"))["attest_fleet"])
m = json.load(open("r41_export.json", encoding="utf-8"))
pool = json.load(open("r41_pool.json", encoding="utf-8"))
pool_jobs = {j for c in pool["cross_did_clusters"].values() for j in c["jobs"]}

deliverer = {}
pooled_by = collections.Counter()
for x in m:
    t = x.get("text") or ""
    if not (t.startswith("RESULT v1") or t.startswith("DELIVER v1")): continue
    p = t.split(" | ")
    if len(p) < 3: continue
    deliverer.setdefault(p[1].strip(), x.get("from"))
    if p[1].strip() in pool_jobs: pooled_by[x.get("from")] += 1
fleet_pooled = sum(n for d, n in pooled_by.items() if d in FLEET)
print("pooled delivery lines: %d, by the 6-key fleet: %d (%.1f%%)"
      % (sum(pooled_by.values()), fleet_pooled, 100.0*fleet_pooled/max(1,sum(pooled_by.values()))))

rows = collections.Counter(); credit = collections.Counter()
for x in m:
    t = x.get("text") or ""
    if not t.startswith("ATTEST v1"): continue
    p = [s.strip() for s in t.split("|")]
    if len(p) < 4: continue
    job, verdict, a = p[1], p[2].lower(), x.get("from")
    if verdict != "useful" or a not in FLEET: continue
    d = deliverer.get(job)
    tag = "fleet-key" if d in FLEET else ("self" if d == a else ("outsider" if d else "unseen"))
    if d == a: tag = "self"
    rows[tag] += 1
    if re.fullmatch(r"[0-9a-f]{16}", (p[3][3:] if p[3].startswith("rh:") else "")): credit[tag] += 1
print("useful verdicts issued BY the fleet, by author of the delivery they endorse:")
for k, n in rows.most_common(): print("   %-10s %4d   (creditable rh: %d)" % (k, n, credit.get(k, 0)))
