#!/usr/bin/env python3
"""Who does the top useful-caster stamp, and with what reasons?"""
import json, glob, collections, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RING = {"z6MknDn3CH7vumHw5rXREhdQN5KjsSp2RWi4aUHusBDRVoRz": "r1", "z6Mkw1wmdRVLPScoJx1wczCcrs9ggFEufgAqK5gLusm9c7Bq": "r2",
        "z6MkvYoXPa8dJH8Zd3u5LHwZME4p9SXtYQK9b9VrUYBiHJdi": "r3", "z6Mkoxggbhq8Hv1Us2zhrvGt1SFRsMzaFezVuZpNGzDnKf3u": "r4",
        "z6Mku9ADH3QQPFVA4by9jkAojHRrCsiTLk2iHi3ubN7jCRvH": "r5"}
f = sorted(glob.glob("useful_on_thin_*.json"))[-1]
msgs = json.load(open(f))["messages"]
who = lambda m: (m.get("did") or m.get("from") or "")
res = [m for m in msgs if m.get("kind") == "result"]
job_worker = {}
for m in res:
    job_worker.setdefault(m["job_id"], []).append(who(m))
att = [m for m in msgs if m.get("kind") == "attest"]
for suffix in ("CMK3R8eJcc", "C3DmCpELvW"):
    mine = [m for m in att if who(m).endswith(suffix)]
    print("==", suffix, "attests", len(mine), collections.Counter(str(m.get("verdict")).lower() for m in mine))
    targets = collections.Counter()
    for m in mine:
        ws = job_worker.get(m["job_id"], ["?"])
        for w in ws:
            targets[RING.get(w.split(":")[-1], w[-10:])] += 1
    print("   receivers:", targets.most_common(8))
    reasons = collections.Counter((m.get("text") or "").split("|")[-1].strip() for m in mine)
    for r, c in reasons.most_common(3):
        print("   %dx %s" % (c, r[:140]))
    seqs = sorted(m["seq"] for m in mine)
    ts = sorted(m["ts"] for m in mine)
    print("   seq", seqs[0], "-", seqs[-1], "ts", ts[0], "-", ts[-1])
    rh_ok = sum(1 for m in mine if "rh:" in (m.get("text") or ""))
    print("   with rh:", rh_ok)
    print("   sample:", [(m["seq"], m["job_id"]) for m in mine[:4]])
