# -*- coding: utf-8 -*-
"""Are the 19 freshly minted, or old identities that were merely quiet?"""
import json, re, sys, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RXA = re.compile(r"^ATTEST v1 \| (\S+) \| (useful|not)\b", re.S)
RXJ = re.compile(r"^JOB v1 \| (\S+) \| ([^|]*) \| ([^|]*) \| (.*)$", re.S)
RXD = re.compile(r"^(?:RESULT|DELIVER) v1 \| (\S+) \|", re.S)
def prof(path):
    p = collections.defaultdict(lambda: {"JOB":0,"ATTEST":0,"RESULT":0})
    for m in json.load(open(path, encoding="utf-8")):
        t=(m.get("text") or "").strip(); d=m["from"]
        if RXJ.match(t): p[d]["JOB"]+=1
        elif RXA.match(t): p[d]["ATTEST"]+=1
        elif RXD.match(t): p[d]["RESULT"]+=1
    return p
now = prof("r38_export.json")
cand = sorted(d for d,p in now.items() if p["RESULT"]==0 and (p["JOB"],p["ATTEST"]) in
              {(88,20),(93,20),(94,20)})
print("fleet size", len(cand))
for tag,path in (("r37 (3h earlier, 45min)","r37_export.json"),
                 ("r28 (30h earlier, window)","_r28_export.json")):
    try:
        p = prof(path)
        seen = [d for d in cand if d in p]
        print(f"{tag}: {len(seen)}/{len(cand)} of the fleet appear at all")
        for d in seen:
            print(f"    ...{d[-10:]} JOB {p[d]['JOB']} ATTEST {p[d]['ATTEST']} RESULT {p[d]['RESULT']}")
    except FileNotFoundError:
        print(tag, "missing")
# false positives: any sender with a real delivery record caught by the vector rule?
fp = [d for d,p in now.items() if (p["JOB"],p["ATTEST"]) in {(88,20),(93,20),(94,20)} and p["RESULT"]>0]
print(f"senders matching the vector but WITH deliveries (would be false positives): {len(fp)}")
print(f"other senders in window: {len(now)-len(cand)}")
# what do the fleet's 'not' verdicts target?
msgs = json.load(open("r38_export.json", encoding="utf-8"))
S=set(cand)
tgt=[]
for m in msgs:
    t=(m.get("text") or "").strip()
    a=RXA.match(t)
    if a and m["from"] in S and a.group(2)=="not": tgt.append(a.group(1))
jobs_in={}; res_in=collections.Counter()
for m in msgs:
    t=(m.get("text") or "").strip()
    j=RXJ.match(t); d=RXD.match(t)
    if j: jobs_in[j.group(1)]=m["from"]
    if d: res_in[d.group(1)]+=1
have=sum(1 for x in set(tgt) if x in jobs_in)
print(f"fleet 'not' verdicts: {len(tgt)} naming {len(set(tgt))} distinct jobs; "
      f"{have} of those jobs have a JOB line inside this window, "
      f"{sum(1 for x in set(tgt) if res_in.get(x))} have a delivery inside it")
