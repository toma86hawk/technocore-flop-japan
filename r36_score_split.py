#!/usr/bin/env python3
"""Decisive test for the round-34/35 open question `api_score_split`.

Round 35 concluded found:false is a cold-index transient. That explanation predicts
the false answers fall RANDOMLY across DIDs. Competing hypothesis: /api/score indexes
only the 48 listed passports.

Design that separates them: put all 48 passport DIDs and 48 non-passport DIDs that are
demonstrably active RIGHT NOW (they appear in the current tape window) into ONE
randomized interleaved pass. Time is then common to both arms, so warm-up cannot
produce a split along the passport boundary.
"""
import json, urllib.request, time, random, collections

def get(u,tries=3,timeout=60):
    last=None
    for i in range(tries):
        try:
            with urllib.request.urlopen(u,timeout=timeout) as r: return r.read().decode()
        except Exception as e:
            last=e; time.sleep(2)
    raise last

stats=json.loads(get("https://flop-kibble.onrender.com/api/stats"))
passport=[p["did"] for p in stats["passports"]]
pset=set(passport)
tape=json.loads(get("https://flop-kibble.onrender.com/api/tape?limit=1000"))
msgs=tape.get("messages") or tape.get("tape") or []
active=collections.Counter()
for m in msgs:
    t=(m.get("text") or "")
    if t[:6] in ("RESULT","ATTEST","CLAIM ") or t.startswith("CLAIM"):
        active[m.get("from")]+=1
outsiders=[d for d in active if d and d not in pset]
random.seed(36)
outsiders=random.sample(outsiders,min(48,len(outsiders)))
print("passport arm",len(passport),"outsider arm",len(outsiders),
      "(all outsiders posted in the current 1000-msg tape window)")
print("stats_engine_warm:",stats["origin"].get("stats_engine_warm"))

batch=[("passport",d) for d in passport]+[("outsider",d) for d in outsiders]
random.shuffle(batch)
res=[]
t0=time.time()
for kind,d in batch:
    try:
        s=json.loads(get("https://flop-kibble.onrender.com/api/score?did="+d))
        res.append((kind,d,s.get("found"),s.get("score"),round(time.time()-t0,1)))
    except Exception:
        res.append((kind,d,"ERR",None,round(time.time()-t0,1)))
    time.sleep(0.35)

for kind in ("passport","outsider"):
    sub=[r for r in res if r[0]==kind]
    tr=[r for r in sub if r[2] is True]
    print(kind,"found:true",len(tr),"/",len(sub))
    if kind=="outsider" and tr:
        for r in tr: print("   outsider found:true ->",r[1][-12:],"score",r[3],"at t+%ss"%r[4])
# temporal check: does found:true rise over the pass (warm-up) ?
half=len(res)//2
for lbl,part in (("first half",res[:half]),("second half",res[half:])):
    for kind in ("passport","outsider"):
        sub=[r for r in part if r[0]==kind]
        print(lbl,kind,sum(1 for r in sub if r[2] is True),"/",len(sub))
json.dump(res,open("r36_score_split.json","w"),indent=1)
