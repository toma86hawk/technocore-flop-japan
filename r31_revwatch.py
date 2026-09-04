"""r31: the 12h reversion prediction. Round 30 predicted a terminal-state
reversion in the 2026-09-04 12:1x JST window. The 12:17 sample showed none.
Poll every 4 min until 13:40 JST to see whether it fires late, then stop.
Deadline-bounded, per AGENT.md."""
import json, time, urllib.request, datetime, os

OUT = "r31_revwatch.jsonl"
DEADLINE = time.time() + 83*60
KEYS = ["jobs","open","claimed","delivered","attested","rejected","agents"]
prev = None
hit = None
while time.time() < DEADLINE:
    try:
        with urllib.request.urlopen("https://flop-kibble.onrender.com/api/stats", timeout=40) as r:
            s = json.loads(r.read().decode())["stats"]
    except Exception as e:
        time.sleep(240); continue
    now = datetime.datetime.now().isoformat(timespec="seconds")
    cur = {k: s.get(k,0) for k in KEYS}
    rec = {"at": now, **cur}
    if prev:
        d = {k: cur[k]-prev[k] for k in KEYS}
        rec["delta"] = d
        if d["delivered"] < 0 or d["attested"] < 0 or d["rejected"] < 0:
            rec["reversion"] = True
            hit = rec
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    prev = cur
    if hit: break
    time.sleep(240)
json.dump({"fired": bool(hit), "hit": hit, "ended": datetime.datetime.now().isoformat(timespec="seconds")},
          open("r31_revwatch_result.json","w",encoding="utf-8"), indent=1)
print("FIRED" if hit else "NO REVERSION in window")
