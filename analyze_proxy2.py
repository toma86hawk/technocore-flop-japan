#!/usr/bin/env python3
"""What did the proxy DID stamp useful? Look at the deliverables it certified."""
import json, glob, collections, sys, hashlib
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PROXY = "CMK3R8eJcc"
f = sorted(glob.glob("useful_on_thin_*.json"))[-1]
msgs = json.load(open(f))["messages"]
who = lambda m: (m.get("did") or m.get("from") or "")
by_seq = {m["seq"]: m for m in msgs}
res_by_job = collections.defaultdict(list)
jobs = {}
for m in msgs:
    if m.get("kind") == "result":
        res_by_job[m["job_id"]].append(m)
    if m.get("kind") == "job":
        jobs[m["job_id"]] = m
mine = [m for m in msgs if m.get("kind") == "attest" and who(m).endswith(PROXY) and str(m.get("verdict")).lower() == "useful"]
bodies = collections.Counter()
for a in sorted(mine, key=lambda x: x["seq"]):
    rs = res_by_job.get(a["job_id"], [])
    for r in rs:
        body = (r.get("text") or "").split("|", 3)[-1].strip()
        h = hashlib.sha256(body.encode()).hexdigest()[:8]
        bodies[h] += 1
        dt = ""
        try:
            from datetime import datetime
            t1 = datetime.fromisoformat(r["ts"].replace("Z", "+00:00")); t2 = datetime.fromisoformat(a["ts"].replace("Z", "+00:00"))
            dt = "%.0fs" % (t2 - t1).total_seconds()
        except Exception:
            pass
        print("%s attest %d <- result %d by %s  gap %s  len %d  %s" % (a["job_id"], a["seq"], r["seq"], who(r)[-10:], dt, len(body), body[:110].replace("\n", " ")))
    if not rs:
        print("%s attest %d <- (result not in window)" % (a["job_id"], a["seq"]))
print("distinct body hashes", len(bodies), bodies.most_common(3))
