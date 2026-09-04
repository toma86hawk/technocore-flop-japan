# -*- coding: utf-8 -*-
"""Round 37c: the 17 DIDs that each cast exactly 20 verdicts do not share a
template - 16 distinct opening sentences among 17 - so no text-similarity
detector reaches them.  They share a clock.  This measures the clock, and
tests the strongest version of the claim: do cohort members judge the SAME jobs?"""
import json, re, sys, collections, datetime, statistics, itertools
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RXA = re.compile(r"^ATTEST v1 \| (\S+) \| (useful|not)\b(.*)$", re.S)

def load(path):
    msgs = json.load(open(path, encoding="utf-8"))
    at = []
    for m in msgs:
        t = (m.get("text") or "").strip()
        a = RXA.match(t)
        if a:
            at.append({"job": a.group(1), "v": a.group(2), "did": m["from"],
                       "ts": datetime.datetime.fromisoformat(m["ts"].replace("Z", "+00:00")),
                       "seq": m["seq"], "text": t})
    return msgs, at

msgs, at = load("r37_export.json")
T0 = datetime.datetime.fromisoformat(msgs[0]["ts"].replace("Z", "+00:00"))
c = collections.Counter(x["did"] for x in at)
fleet = [d for d, k in c.items() if k == 20]
starts = {}
for d in fleet:
    r = sorted([x for x in at if x["did"] == d], key=lambda x: x["seq"])
    starts[d] = (r[0]["ts"] - T0).total_seconds()
order = sorted(fleet, key=lambda d: starts[d])
cohorts, cur = [], [order[0]]
for a, b in zip(order, order[1:]):
    (cur.append(b) if starts[b] - starts[a] < 60 else (cohorts.append(cur), cur := [b]))
cohorts.append(cur)
print(f"{len(fleet)} DIDs x exactly 20 verdicts -> {len(cohorts)} launch cohorts\n")
prev = None
for i, co in enumerate(cohorts, 1):
    s = [starts[d] for d in co]
    print(f"cohort {i}: {len(co)} DIDs, first verdict within a {max(s)-min(s):.1f}s spread "
          f"(t0+{min(s):.0f}s)" + (f", {min(s)-prev:.0f}s after the previous cohort" if prev else ""))
    prev = min(s)
    tgt = {d: set(x["job"] for x in at if x["did"] == d) for d in co}
    inter = [len(tgt[a] & tgt[b]) for a, b in itertools.combinations(co, 2)]
    union = set().union(*tgt.values())
    print(f"          shared job targets between members: max {max(inter)} of 20, "
          f"mean {statistics.mean(inter):.1f}; union {len(union)} distinct jobs of {20*len(co)} verdicts")
    for d in sorted(co, key=lambda d: starts[d]):
        r = sorted([x for x in at if x["did"] == d], key=lambda x: x["seq"])
        print(f"            ...{d[-10:]} +{starts[d]:7.1f}s  "
              f"{r[0]['ts'].strftime('%H:%M:%S')}..{r[-1]['ts'].strftime('%H:%M:%S')}  "
              f"u{sum(1 for x in r if x['v']=='useful')}/20")

print("\n--- same 17 DIDs in the round-28 snapshot (2026-09-04 03:46 JST, ~18h earlier) ---")
try:
    m2, a2 = load("_r28_export.json")
    c2 = collections.Counter(x["did"] for x in a2)
    span2 = (datetime.datetime.fromisoformat(m2[-1]["ts"].replace("Z", "+00:00"))
             - datetime.datetime.fromisoformat(m2[0]["ts"].replace("Z", "+00:00"))).total_seconds()
    print(f"snapshot {m2[0]['seq']}..{m2[-1]['seq']}  {span2/60:.1f} min  ATTEST {len(a2)}")
    hit = [(d, c2[d]) for d in fleet if c2.get(d)]
    print(f"of the 17, present 18h earlier: {len(hit)}")
    for d, k in sorted(hit, key=lambda x: -x[1]):
        r = sorted([x for x in a2 if x["did"] == d], key=lambda x: x["seq"])
        gaps = [(r[i+1]["ts"]-r[i]["ts"]).total_seconds() for i in range(len(r)-1)]
        print(f"   ...{d[-10:]}  {k:3d} verdicts  burst {(r[-1]['ts']-r[0]['ts']).total_seconds():6.1f}s  "
              f"med-gap {statistics.median(gaps) if gaps else 0:5.1f}s")
    print(f"\nverdict-count histogram in that snapshot: "
          f"{collections.Counter(c2.values()).most_common(10)}")
except FileNotFoundError:
    print("no round-28 snapshot on disk")
