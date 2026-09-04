"""r31: is /api/score's found:false a random flap, or the top-48 boundary?

Round 13 published a 97.8% blind spot; round 27 RETRACTED it (30/30 found).
Round 30 recorded that the SAME DID flips between samples, and left a standing
rule: do not revive the 97.8% claim on flapping alone.

This is the discriminating test. Two fixed cohorts, queried three times each,
interleaved so any global outage hits both:
  A = 12 DIDs that ARE in the /api/stats top-48 passport table
  B = 12 DIDs that are NOT (live board workers + our own DID)
Flapping predicts B answers inconsistently across its own 3 repeats.
A boundary predicts A=36/36 found and B=0/36 found, every repeat.
"""
import json, urllib.request, urllib.parse, time, io, sys, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

US = "did:key:z6Mkpjt48fahhtdXLpw9Tvzutd5KeYSSkMLaSbfAmfxfdwqb"
top = [p["did"] for p in json.load(open("stats_r31.json", encoding="utf-8"))["passports"]]
topset = set(top)
q = json.load(io.open("attest_queue.json", encoding="utf-8"))
outs = []
for p in q:
    for k in ("worker",):
        d = p.get(k)
        if d and d.startswith("did:key:") and d not in topset and d not in outs:
            outs.append(d)
A = top[:12]
B = ([US] + [d for d in outs if d != US])[:12]

def score(did):
    u = "https://flop-kibble.onrender.com/api/score?did=" + urllib.parse.quote(did, safe="")
    with urllib.request.urlopen(u, timeout=40) as r:
        return json.loads(r.read().decode())

res = collections.defaultdict(list)
for rep in range(3):
    for cohort, dids in (("A", A), ("B", B)):
        for d in dids:
            try:
                j = score(d)
                res[(cohort, d)].append(bool(j.get("found")))
            except Exception as e:                                  # noqa: BLE001
                res[(cohort, d)].append(None)
            time.sleep(1.6)
    print(f"repeat {rep+1} done", flush=True)

out = {"A": {}, "B": {}}
for (c, d), v in res.items():
    out[c][d] = v
for c in ("A", "B"):
    tot = sum(len(v) for v in out[c].values())
    t = sum(sum(1 for x in v if x is True) for v in out[c].values())
    e = sum(sum(1 for x in v if x is None) for v in out[c].values())
    incons = [d for d, v in out[c].items() if len(set(x for x in v if x is not None)) > 1]
    print(f"cohort {c}: found {t}/{tot} (errors {e})  inconsistent DIDs: {len(incons)}")
    for d in incons:
        print(f"   FLAP ...{d[-14:]} {out[c][d]}")
print(f"\nUS ...{US[-14:]} -> {out['B'].get(US)}")
json.dump(out, open("r31_score_boundary.json", "w", encoding="utf-8"), indent=1)
