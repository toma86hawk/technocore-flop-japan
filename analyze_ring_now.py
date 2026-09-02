#!/usr/bin/env python3
"""Why did useful-on-thin fall? Split the current window's ATTESTs by the 8/31 ring DIDs."""
import json, glob, collections, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RING = {
 "did:key:z6MknDn3CH7vumHw5rXREhdQN5KjsSp2RWi4aUHusBDRVoRz": "r1",
 "did:key:z6Mkw1wmdRVLPScoJx1wczCcrs9ggFEufgAqK5gLusm9c7Bq": "r2",
 "did:key:z6MkvYoXPa8dJH8Zd3u5LHwZME4p9SXtYQK9b9VrUYBiHJdi": "r3",
 "did:key:z6Mkoxggbhq8Hv1Us2zhrvGt1SFRsMzaFezVuZpNGzDnKf3u": "r4",
 "did:key:z6Mku9ADH3QQPFVA4by9jkAojHRrCsiTLk2iHi3ubN7jCRvH": "r5",
}
THIN_DID = "did:key:z6MkvudSY2Ezd4suJDfD2DYE8GAVUBCGHgjHjPMowhojvBUG"
f = sorted(glob.glob("useful_on_thin_*.json"))[-1]
d = json.load(open(f))
msgs = d["messages"]
who = lambda m: m.get("did") or m.get("from")
att = [m for m in msgs if m.get("kind") == "attest"]
res = [m for m in msgs if m.get("kind") == "result"]
print("file", f, "attests", len(att))
ring_att = [m for m in att if who(m) in RING]
print("ring attests", len(ring_att), collections.Counter((RING[who(m)], str(m.get("verdict")).lower()) for m in ring_att))
ring_res = [m for m in res if who(m) in RING]
print("ring deliveries", len(ring_res), collections.Counter(RING[who(m)] for m in ring_res))
thin_res = [m for m in res if who(m) == THIN_DID]
print("thin DID deliveries", len(thin_res), "thin-flagged", sum(1 for m in thin_res if m.get("thin")))
thin_jobs = {m["job_id"] for m in res if m.get("thin") and not m.get("scored")}
att_on_thin = [m for m in att if m.get("job_id") in thin_jobs]
print("attests on thin jobs", len(att_on_thin), collections.Counter(str(m.get("verdict")).lower() for m in att_on_thin))
print("thin jobs attested at all", len({m["job_id"] for m in att_on_thin}), "of", len(thin_jobs))
useful = [m for m in att if str(m.get("verdict")).lower() == "useful"]
top = collections.Counter(who(m) for m in useful).most_common(5)
print("top useful casters", [(k[-10:], v) for k, v in top])
# who receives the useful now?
job_worker = {m["job_id"]: who(m) for m in res}
recv = collections.Counter(job_worker.get(m.get("job_id"), "?")[-10:] for m in useful)
print("useful receivers", recv.most_common(6))
# reason diversity among useful
reasons = collections.Counter((m.get("text") or "").split("|")[-1].strip()[:60] for m in useful)
print("distinct useful reasons", len(reasons), "most common", reasons.most_common(2))
