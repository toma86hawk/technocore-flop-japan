# -*- coding: utf-8 -*-
"""Deadline-bounded probe: does /api/stats serve more than one counter batch?
Records every distinct 8-counter state together with the live tape_head_seq."""
import json, time, urllib.request, collections
UA = {"User-Agent": "flop-jp-agent/1.0"}
U = "https://flop-kibble.onrender.com/api/stats"
KEYS = ("jobs", "open", "briefs", "parsed", "claimed", "attested", "rejected", "delivered")
DEADLINE = time.time() + 40 * 60
rows = []
while time.time() < DEADLINE:
    try:
        d = json.loads(urllib.request.urlopen(urllib.request.Request(U, headers=UA), timeout=60).read())
        s, o = d["stats"], d.get("origin") or {}
        rows.append({"t": time.strftime("%H:%M:%SZ", time.gmtime()),
                     "state": tuple(s.get(k) for k in KEYS),
                     "head": o.get("tape_head_seq"), "engine": o.get("stats_engine_seq")})
    except Exception as e:
        rows.append({"t": time.strftime("%H:%M:%SZ", time.gmtime()), "err": repr(e)[:80]})
    time.sleep(6)
good = [r for r in rows if "state" in r]
grp = collections.Counter(r["state"] for r in good)
order = []
for r in good:
    if not order or order[-1][0] != r["state"]:
        order.append((r["state"], r["t"], r["head"]))
json.dump({"keys": KEYS, "n": len(good), "distinct": len(grp),
           "transitions": [{"state": list(s), "first_seen": t, "head": h} for s, t, h in order]},
          open("guide/_r172_batch_probe.json", "w"), indent=1)
print("reads", len(good), "distinct counter states", len(grp), "transitions", len(order))
for s, t, h in order:
    print(" ", t, "head", h, s)
