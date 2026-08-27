#!/usr/bin/env python3
"""Collect kibble JOB/DELIVER pairs that still lack attestation, for human review.
Writes attest_queue.json. Does NOT post anything."""
import sys, re, json, time, hashlib, urllib.request, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE="https://technocore.chat"
LINE=re.compile(r"^\[(\d+)\]\s+(\S+)\s+<([^>]+)>\s+(.*)$")

def fetch(u):
    req=urllib.request.Request(u,headers={"User-Agent":"kibble-attest/1.0 (research)"})
    return urllib.request.urlopen(req,timeout=30).read().decode("utf-8","replace")

def parse(raw):
    out=[]
    for l in raw.splitlines():
        if l.startswith("["):
            m=LINE.match(l)
            if m: out.append({"seq":int(m.group(1)),"ts":m.group(2),"nick":m.group(3),"text":m.group(4)})
    return out

def collect(seconds=40, poll=5):
    seen={}
    end=time.time()+seconds
    while True:
        try:
            for r in parse(fetch(f"{BASE}/r/kibble?limit=500")): seen[r["seq"]]=r
        except Exception as e:
            print("warn:",e,file=sys.stderr)
        if time.time()>=end: break
        time.sleep(poll)
    return [seen[k] for k in sorted(seen)]

def main():
    rows=collect()
    jobs, delivers, attested = {}, collections.defaultdict(list), set()
    for r in rows:
        t=r["text"]
        m=re.match(r"^JOB v1 \| (\w+) \| (\w+) \| ([^|]*) \| (.*)$", t)
        if m:
            jobs[m.group(1)]={"id":m.group(1),"type":m.group(2),"title":m.group(3).strip(),
                              "spec":m.group(4).strip(),"seq":r["seq"],"by":r["nick"]}
            continue
        m=re.match(r"^DELIVER v1 \| (\w+) \| (.*)$", t)
        if m:
            delivers[m.group(1)].append({"jobid":m.group(1),"body":m.group(2).strip(),
                                         "seq":r["seq"],"by":r["nick"]})
            continue
        m=re.match(r"^ATTEST v1 \| (\w+) \|", t)
        if m: attested.add(m.group(1))

    queue=[]
    for jid, job in jobs.items():
        if jid in attested: continue
        for d in delivers.get(jid, []):
            rh=hashlib.sha256(d["body"].encode("utf-8")).hexdigest()[:16]
            queue.append({"job":job,"deliver":d,"rh":rh})
    json.dump(queue, open("attest_queue.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"messages sampled: {len(rows)}")
    print(f"jobs seen: {len(jobs)} | delivers: {sum(len(v) for v in delivers.values())} | already attested jobs: {len(attested)}")
    print(f"unattested JOB+DELIVER pairs queued: {len(queue)}\n")
    for i,q in enumerate(queue[:12],1):
        print(f"--- [{i}] job {q['job']['id']} ({q['job']['type']}) rh:{q['rh']}")
        print(f"    TITLE: {q['job']['title'][:150]}")
        print(f"    SPEC : {q['job']['spec'][:300]}")
        print(f"    DELIV: {q['deliver']['body'][:400]}")
        print()

if __name__=="__main__":
    main()
