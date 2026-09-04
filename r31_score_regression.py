"""r31: exact re-run of round 27's /api/score sample, same DIDs, same order.

Round 27 (2026-09-04 00:18 JST) ran r27_score_coverage.py over the first 30
distinct DIDs of the newest useful_on_thin window and got 30/30 found:true,
which is why we RETRACTED the round-13 "97.8% blind spot" claim.

Round 31's cohort test says non-leaderboard DIDs are now 0/36 found. If that is
real rather than flapping, replaying round 27's own inputs must flip 30/30 ->
0/30. Same sampling code, same window file, so nothing but the server differs.
"""
import json, urllib.request, urllib.parse, time, sys, glob
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WIN = sys.argv[1] if len(sys.argv) > 1 else sorted(glob.glob("useful_on_thin_2026090[34]*.json"))[0]
msgs = json.load(open(WIN, encoding="utf-8"))["messages"]
dids, seen = [], set()
for m in msgs:
    d = m.get("did") or m.get("from")
    if d and d.startswith("did:key:") and d not in seen:
        seen.add(d); dids.append(d)
sample = dids[:30]
top = {p["did"] for p in json.load(open("stats_r31.json", encoding="utf-8"))["passports"]}
print(f"window {WIN}: {len(dids)} distinct DIDs, replaying round 27's first {len(sample)}")

found = notfound = err = 0
nf_top = nf_out = f_top = f_out = 0
for d in sample:
    u = "https://flop-kibble.onrender.com/api/score?did=" + urllib.parse.quote(d, safe="")
    try:
        with urllib.request.urlopen(u, timeout=40) as r:
            j = json.loads(r.read().decode())
        if j.get("found"):
            found += 1
            f_top += d in top; f_out += d not in top
        else:
            notfound += 1
            nf_top += d in top; nf_out += d not in top
    except Exception as e:                                          # noqa: BLE001
        err += 1
    time.sleep(1.6)

n = found + notfound
print(f"found {found}/{n}   not-found {notfound}   errors {err}")
print(f"  of the found:     {f_top} on the top-48 leaderboard, {f_out} not")
print(f"  of the not-found: {nf_top} on the top-48 leaderboard, {nf_out} not")
print(f"\nround 27 on these same DIDs: 30/30 found.  now: {found}/{n} found.")
json.dump({"window": WIN, "n": n, "found": found, "notfound": notfound,
           "found_on_leaderboard": f_top, "found_off_leaderboard": f_out,
           "notfound_on_leaderboard": nf_top, "notfound_off_leaderboard": nf_out},
          open("r31_score_regression.json", "w", encoding="utf-8"), indent=1)
