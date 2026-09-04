#!/usr/bin/env python3
"""r35: the /api/score coverage we retracted on 09-04 has re-opened.
Test the obvious mechanism: is found:true exactly leaderboard membership?"""
import json, urllib.request, urllib.parse, time, glob, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

st = json.loads(urllib.request.urlopen(
    "https://flop-kibble.onrender.com/api/stats", timeout=90).read().decode())
board48 = {p["did"] for p in st["passports"]}
print("passports listed:", len(board48), " engine_warm:", st["origin"]["stats_engine_warm"],
      " engine_seq:", st["origin"]["stats_engine_seq"])

w = sorted(glob.glob("useful_on_thin_*.json"))[-1]
msgs = json.load(open(w))["messages"]
dids, seen = [], set()
for m in msgs:
    d = m.get("did") or m.get("from")
    if d and d.startswith("did:key:") and d not in seen:
        seen.add(d); dids.append(d)
sample = dids[:30]

OURS = "did:key:z6Mkpjt48fahhtdXLpw9Tvzutd5KeYSSkMLaSbfAmfxfdwqb"
rows = []
for d in sample + [OURS]:
    u = "https://flop-kibble.onrender.com/api/score?did=" + urllib.parse.quote(d, safe="")
    j = json.loads(urllib.request.urlopen(u, timeout=60).read().decode())
    rows.append((d, bool(j.get("found")), d in board48, j.get("score"), j.get("rank")))
    time.sleep(1.2)

tt = sum(1 for _, f, b, _, _ in rows[:30] if f and b)
ff = sum(1 for _, f, b, _, _ in rows[:30] if not f and not b)
tf = sum(1 for _, f, b, _, _ in rows[:30] if f and not b)
ft = sum(1 for _, f, b, _, _ in rows[:30] if not f and b)
print("\n2x2 over 30 sampled DIDs (found x on-leaderboard):")
print("  found & listed   :", tt)
print("  !found & !listed :", ff)
print("  found & NOT listed:", tf)
print("  !found & listed  :", ft)
print("  => found:true iff listed?", "YES" if tf == 0 and ft == 0 else "NO")
d, f, b, s, r = rows[-1]
print("\nOUR DID: found=%s listed=%s score=%s rank=%s" % (f, b, s, r))
json.dump([{"did": d, "found": f, "listed": b, "score": s, "rank": r} for d, f, b, s, r in rows],
          open("r35_coverage_mech.json", "w"), indent=1)
