# -*- coding: utf-8 -*-
"""Is the passport disagreement a TIME effect (known square wave) or an ENDPOINT split?

Interleaves /api/stats and /api/board. If each endpoint is internally stable across
its own samples while differing from the other, the difference is by endpoint, not
by time -- which the known r27 square wave cannot explain.
"""
import json, time, urllib.request

DID = "did:key:z6MkptCMeKbxLZKjzBfpWXxVQpvFNk7UqeUWNyhCDEiseaD4"
F = ["score", "jobs_posted", "results_delivered", "attestations_given",
     "useful_attestations_received", "not_useful_attestations_received"]

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "flop-jp-agent/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

def row(d):
    for p in d["passports"]:
        if p["did"] == DID:
            return tuple(p[f] for f in F)
    return None

samples = []
for i in range(3):
    for name, url in (("stats", "https://flop-kibble.onrender.com/api/stats"),
                      ("board", "https://flop-kibble.onrender.com/api/board")):
        d = get(url)
        seq = d.get("origin", {}).get("stats_engine_seq") or d.get("engine_seq")
        samples.append((name, time.strftime("%H:%M:%S"), seq, row(d)))
        print(samples[-1])
        time.sleep(3)

for name in ("stats", "board"):
    vals = {s[3] for s in samples if s[0] == name}
    print("%s: %d distinct value-tuples across %d samples" %
          (name, len(vals), sum(1 for s in samples if s[0] == name)))
sv = {s[3] for s in samples if s[0] == "stats"}
bv = {s[3] for s in samples if s[0] == "board"}
print("stats set and board set disjoint:", sv.isdisjoint(bv))
print("fields:", F)
