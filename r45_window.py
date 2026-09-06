# -*- coding: utf-8 -*-
"""Round 45. The scoring freeze is 6h old. How much of it can still be READ?
The export is a sliding window (round 37 retraction). Measure its span, its
eviction rate, and whether ANY parameter seeks below its floor."""
import json, time, datetime, urllib.request
UA={"User-Agent":"flop-jp-agent/1.0"}
BASE="https://technocore.chat/r/kibble/export"
def win(u=BASE+"?limit=20000"):
    raw=urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=300).read().decode("utf-8","replace")
    ls=[json.loads(l) for l in raw.splitlines() if l.strip().startswith("{")]
    ls.sort(key=lambda m:m["seq"])
    return ls[0],ls[-1],len(ls)
def ts(s): return datetime.datetime.fromisoformat(s.replace("Z","+00:00"))

a0,a1,an=win()
print("t0  n=%d  seq %d..%d  %s .. %s  span=%s"
      % (an,a0["seq"],a1["seq"],a0["ts"],a1["ts"],ts(a1["ts"])-ts(a0["ts"])))
time.sleep(120)
b0,b1,bn=win()
print("t1  n=%d  seq %d..%d  %s .. %s  span=%s"
      % (bn,b0["seq"],b1["seq"],b0["ts"],b1["ts"],ts(b1["ts"])-ts(b0["ts"])))
dt=(ts(b1["ts"])-ts(a1["ts"])).total_seconds()
print("\nover %.0fs: floor %+d msgs, head %+d msgs, size %+d"
      % (dt,b0["seq"]-a0["seq"],b1["seq"]-a1["seq"],bn-an))
if b0["seq"]>a0["seq"]:
    print("FLOOR MOVES -> messages are evicted from every read path we have.")
print("head rate %.1f msgs/min | floor rate %.1f msgs/min"
      % ((b1["seq"]-a1["seq"])*60/dt,(b0["seq"]-a0["seq"])*60/dt))
FREEZE=datetime.datetime.fromisoformat("2026-09-05T18:19:00+00:00")
readable=ts(b0["ts"]); now=ts(b1["ts"])
print("\nfreeze began   %s" % FREEZE)
print("readable floor %s" % readable)
print("now            %s" % now)
print("freeze so far  %s" % (now-FREEZE))
print("readable part  %s" % (now-readable))
print("ALREADY UNREADABLE: %s of the freeze" % (readable-FREEZE))
json.dump({"floor_seq":b0["seq"],"head_seq":b1["seq"],"n":bn,
           "floor_ts":b0["ts"],"head_ts":b1["ts"],
           "freeze_start":"2026-09-05T18:19:00Z",
           "unreadable_seconds":(readable-FREEZE).total_seconds(),
           "freeze_seconds":(now-FREEZE).total_seconds(),
           "head_rate_per_min":(b1["seq"]-a1["seq"])*60/dt,
           "floor_rate_per_min":(b0["seq"]-a0["seq"])*60/dt},
          open("r45_window.json","w"),indent=1)
