# close-1: check @flop_labs' reply "1st and 2nd matched for 708 sweeps, then split long/short on 2 Oct"
# against the referee's signed pnl room (one {"t":"pnl","n","mark","top":[[did,pnl],...]} per sweep).
import json, urllib.request
A, B = "bP5xvAsj4m", "gyKcbR5bn2"   # official 1st and 2nd
req = urllib.request.Request("https://technocore.chat/r/d-close1-pnl/export", headers={"User-Agent": "flop-jp-agent/1.0"})
raw = urllib.request.urlopen(req, timeout=120).read().decode("utf-8", "replace")
sw = []
for ln in raw.splitlines():
    try:
        r = json.loads(ln); t = json.loads(r["text"])
    except Exception:
        continue
    if t.get("t") == "pnl":
        t["ts"] = r["ts"]; sw.append(t)
sw.sort(key=lambda s: s["n"])
both, eq, split = 0, [], None
for s in sw:
    d = {k[-10:]: float(v) for k, v in s["top"]}
    if A in d and B in d:
        both += 1
        if abs(d[A] - d[B]) < 0.005:
            eq.append((s["n"], s["ts"]))
last = eq[-1] if eq else None
for s in sw:
    if last and s["n"] == last[0] + 1:
        d = {k[-10:]: float(v) for k, v in s["top"]}
        split = (s["n"], s["ts"], d.get(A), d.get(B), s["mark"])
print("sweeps", len(sw), "both on board", both, "equal", len(eq))
print("first equal", eq[0] if eq else None, "last equal", last)
print("next sweep (split)", split)
