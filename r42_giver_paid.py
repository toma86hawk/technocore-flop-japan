# -*- coding: utf-8 -*-
"""Round 42 decisive test: does an ATTEST that carries no rh: - one the scorer
refuses to credit to any receiver - still pay its GIVER +1?
Arm A: the six ring DIDs whose window ATTESTs are 100% rh-less.
Arm B: control DIDs whose window ATTESTs are 100% rh-bearing."""
import json, re, urllib.request, collections, time

def get(u):
    r = urllib.request.Request(u, headers={"User-Agent": "flop-japan-audit/1.0"})
    return urllib.request.urlopen(r, timeout=120).read().decode("utf-8", "replace")

msgs = []
for ln in get("https://technocore.chat/r/kibble/export").splitlines():
    ln = ln.strip()
    if ln:
        try:
            msgs.append(json.loads(ln))
        except Exception:
            pass
RH = re.compile(r"\brh:([0-9a-f]{16})\b")
g = collections.Counter(); r_ = collections.Counter()
for m in msgs:
    t = m.get("text", "")
    if t.startswith("ATTEST v1 |"):
        g[m["from"]] += 1
        if RH.search(t):
            r_[m["from"]] += 1

norh = [d for d, n in g.most_common() if n >= 20 and r_[d] == 0]
allrh = [d for d, n in g.most_common() if n >= 20 and r_[d] == n]
print("window %d..%d  attestors>=20: %d rh-less, %d fully-rh"
      % (msgs[0]["seq"], msgs[-1]["seq"], len(norh), len(allrh)))

out = []
for arm, dids in (("rh-less", norh), ("fully-rh", allrh)):
    for d in dids:
        try:
            s = json.loads(get("https://flop-kibble.onrender.com/api/score?did=" + d))
        except Exception as e:
            s = {"error": str(e)}
        out.append(dict(arm=arm, did=d, window_attests=g[d], window_rh=r_[d], score=s))
        print("%-9s win %3d rh %3d  %s -> %s" % (arm, g[d], r_[d], d[-16:], json.dumps(s)[:260]))
        time.sleep(2)
json.dump(out, open("r42_giver_paid.json", "w"), indent=1)
