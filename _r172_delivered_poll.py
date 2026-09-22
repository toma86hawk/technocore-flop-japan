# -*- coding: utf-8 -*-
"""Bounded poller: is /api/stats `delivered` monotone? Deadline-limited, self-stopping."""
import json, time, urllib.request
UA={"User-Agent":"flop-jp-agent/1.0"}
U="https://flop-kibble.onrender.com/api/stats"
DEADLINE=time.time()+70*60
out=[]
while time.time()<DEADLINE:
    try:
        s=json.loads(urllib.request.urlopen(urllib.request.Request(U,headers=UA),timeout=60).read())["stats"]
        out.append({"t":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
                    **{k:s.get(k) for k in ("delivered","rejected","claimed","attested","open","jobs","parsed","briefs")}})
        json.dump(out,open("guide/_r172_delivered_poll.json","w"),indent=1)
    except Exception as e:
        out.append({"t":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),"err":repr(e)})
    time.sleep(300)
drops=[(a["t"],b["t"],a.get("delivered"),b.get("delivered")) for a,b in zip(out,out[1:])
       if isinstance(a.get("delivered"),int) and isinstance(b.get("delivered"),int) and b["delivered"]<a["delivered"]]
json.dump({"samples":out,"drops":drops},open("guide/_r172_delivered_poll.json","w"),indent=1)
print("samples",len(out),"drops",len(drops))
for d in drops: print(d)
