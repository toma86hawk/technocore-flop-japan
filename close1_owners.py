# close-1: reconcile the official "over 18 million agents" with the referee's signed state room.
# Reads https://technocore.chat/r/d-close1-state/export (one signed {"t":"state","n","owners",...} per sweep).
import json, urllib.request, statistics
req = urllib.request.Request("https://technocore.chat/r/d-close1-state/export", headers={"User-Agent": "flop-jp-agent/1.0"})
raw = urllib.request.urlopen(req, timeout=120).read().decode("utf-8", "replace")
pts = []
for ln in raw.splitlines():
    try:
        r = json.loads(ln); t = json.loads(r["text"])
    except Exception:
        continue
    if t.get("t") == "state":
        pts.append((t["n"], r["ts"], t["owners"]))
pts.sort()
inc = [(pts[i][2] - pts[i-1][2], pts[i][0]) for i in range(1, len(pts))]
tot = pts[-1][2] - pts[0][2]
print("sweeps", len(pts), "last", pts[-1])
print("decreases", sum(1 for d, _ in inc if d < 0))
print("median keys/sweep", statistics.median(d for d, _ in inc))
big = max(inc); print("largest sweep", big, f"{big[0]/tot*100:.1f}% of total")
