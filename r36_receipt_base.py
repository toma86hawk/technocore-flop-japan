#!/usr/bin/env python3
"""Falsification pass for round 36: is 'only 2 of 18 non-paper rooms carry a
receipt frame' specific to the value rail, or is receipt simply rare everywhere?

Baseline = a random sample of PAPER deal rooms from tclk_rail_state.seen_locks.
Same reader, same frame parser, so the comparison is apples to apples.
"""
import json, random, urllib.request, collections, time
from datetime import datetime

ORIGIN = "https://technocore.chat"
st = json.load(open("tclk_rail_state.json", encoding="utf-8"))
paper = [v for v in st["seen_locks"].values() if v.get("rail") == "paper"]
random.seed(36)
sample = random.sample(paper, min(40, len(paper)))
print("paper locks known:", len(paper), "sampling", len(sample))

def get(url, tries=3, timeout=60):
    last=None
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.read().decode("utf-8","replace")
        except Exception as e:
            last=e; time.sleep(2+2*i)
    raise last

def ts(s): return datetime.strptime(s.replace("Z","")[:26], "%Y-%m-%dT%H:%M:%S.%f")

rows=[]
for v in sample:
    room=v["room"]
    try: raw=get("%s/r/%s/export"%(ORIGIN,room))
    except Exception as e:
        print(room,"ERR",str(e)[:50]); continue
    frames=[]; nontclk=0
    for line in raw.splitlines():
        line=line.strip()
        if not line: continue
        try: o=json.loads(line)
        except Exception: continue
        if not isinstance(o,dict) or "text" not in o: continue
        t=o["text"]
        if t.startswith("tclk1 "):
            try: j=json.loads(t[6:])
            except Exception: j={"type":"badjson"}
            frames.append((j.get("type"),o.get("ts"),o.get("from")))
        else: nontclk+=1
    k=collections.Counter(f[0] for f in frames)
    lock=next((f for f in frames if f[0]=="lock"),None)
    rev=next((f for f in frames if f[0]=="reveal"),None)
    dt=round((ts(rev[1])-ts(lock[1])).total_seconds(),3) if lock and rev else None
    rows.append(dict(room=room,kinds=dict(k),nontclk=nontclk,
                     receipt=("receipt" in k),revealed=("reveal" in k),
                     signers=len({f[2] for f in frames}),gap=dt))

n=len(rows)
print("rooms read:",n)
print("receipt present:",sum(r['receipt'] for r in rows),"/",n)
print("reveal present :",sum(r['revealed'] for r in rows),"/",n)
print("single-signer  :",sum(r['signers']==1 for r in rows),"/",n)
print("non-tclk msgs  :",sum(r['nontclk']>0 for r in rows),"/",n)
gaps=sorted(r['gap'] for r in rows if r['gap'] is not None)
print("paper lock->reveal median:", gaps[len(gaps)//2] if gaps else None, "n=",len(gaps))
print("kind totals:",collections.Counter(k for r in rows for k in r['kinds']))
json.dump(rows,open("r36_receipt_base.json","w"),indent=1)
