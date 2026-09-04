#!/usr/bin/env python3
"""Round 35: settle the long-open question `useful_without_rh`.
Natural experiment: in one export window, group attestors by whether their
ATTEST lines carry rh:, then read each one's /api/score attestations_given."""
import json, collections, urllib.request, time, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

msgs = json.load(open("r35_export.json"))
att = [m for m in msgs if (m.get("text") or "").startswith("ATTEST v1")]
by = collections.defaultdict(lambda: {"n": 0, "rh": 0, "useful": 0})
for m in att:
    d = m["from"]; by[d]["n"] += 1
    if "rh:" in m["text"]: by[d]["rh"] += 1
    if "| useful" in m["text"]: by[d]["useful"] += 1

cands = sorted(by.items(), key=lambda kv: -kv[1]["n"])[:14]
print("%-16s %5s %5s %6s | %7s %7s %6s" % ("did-tail", "att", "w/rh", "usef", "found", "given", "score"))
out = []
for d, s in cands:
    try:
        u = "https://flop-kibble.onrender.com/api/score?did=" + d
        j = json.loads(urllib.request.urlopen(u, timeout=60).read().decode())
    except Exception as e:
        print("ERR", d[-14:], e); continue
    given = j.get("breakdown", {}).get("terms", {}).get("attestations_given", {}).get("count")
    row = dict(did=d, att=s["n"], with_rh=s["rh"], useful=s["useful"],
               found=j.get("found"), given=given, score=j.get("score"),
               drops=len(j.get("drops") or []))
    out.append(row)
    print("%-16s %5d %5d %6d | %7s %7s %6s" % (d[-14:], s["n"], s["rh"], s["useful"],
                                               j.get("found"), given, j.get("score")))
    time.sleep(1.0)
json.dump(out, open("r35_rh_required.json", "w"), indent=1)
