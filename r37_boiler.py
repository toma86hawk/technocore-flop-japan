# -*- coding: utf-8 -*-
"""Round 37: does an ATTEST verdict depend on the delivery at all?

699 of the 1863 reviewable pairs in this window are ONE DID's 56-character
receipt - "Auto-delivered by VPS agent. Job received and processed." - a body
that answers no job.  1136 pairs carry a body over 120 characters.  If peer
attestation discriminates, the useful-share of the two groups must differ.

We also check whether the useful verdicts on the receipt SCORE: round 35
established that a verdict only counts when it carries the job's rh, and the
rh of that constant body is a constant, ac1dc357d283d229.
"""
import json, re, sys, collections, math, urllib.request
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BOIL = "Auto-delivered by VPS agent. Job received and processed."
BOIL_RH = "ac1dc357d283d229"

def export(room, limit=30000):
    req = urllib.request.Request(f"https://technocore.chat/r/{room}/export?limit={limit}",
                                 headers={"User-Agent": "flop-jp-agent/1.0"})
    raw = urllib.request.urlopen(req, timeout=300).read().decode("utf-8", "replace")
    return [json.loads(l) for l in raw.splitlines() if l.strip().startswith("{")]

q = {x["job_id"]: x for x in json.load(open("attest_queue_offboard.json", encoding="utf-8"))}
boil_jobs = {k for k, v in q.items() if v["result"].strip() == BOIL}
real_jobs = {k for k, v in q.items() if v["body_len"] > 120}

msgs = export("kibble")
RXA = re.compile(r"^ATTEST v1 \| (\S+) \| (useful|not)\b(.*)$", re.S)
RXRH = re.compile(r"\brh:([0-9a-f]{16})\b")

rows = []
for m in msgs:
    t = (m.get("text") or "").strip()
    a = RXA.match(t)
    if not a:
        continue
    job, verdict, tail = a.group(1), a.group(2), a.group(3)
    rh = RXRH.search(tail)
    rows.append({"job": job, "verdict": verdict, "attestor": m["from"],
                 "rh": rh.group(1) if rh else None, "seq": m["seq"], "len": len(t)})

def group(jobs, label):
    r = [x for x in rows if x["job"] in jobs]
    u = [x for x in r if x["verdict"] == "useful"]
    n = [x for x in r if x["verdict"] == "not"]
    ur = [x for x in u if x["rh"]]
    print(f"{label:26s} attests {len(r):4d}  useful {len(u):4d}  not {len(n):3d}  "
          f"useful-share {100.0*len(u)/max(1,len(r)):5.1f}%   useful-with-rh {len(ur):4d} "
          f"({100.0*len(ur)/max(1,len(u)):.1f}%)")
    return r, u, n

print(f"window: {len(msgs)} msgs, seq {msgs[0]['seq']}..{msgs[-1]['seq']}, "
      f"{msgs[0]['ts']} .. {msgs[-1]['ts']}")
print(f"reviewable pairs {len(q)}   receipt-only {len(boil_jobs)}   >120 chars {len(real_jobs)}\n")
rb, ub, nb = group(boil_jobs, "56-char receipt")
rr, ur_, nr = group(real_jobs, ">120-char body")

a, b = len(ub), len(nb)
c, d = len(ur_), len(nr)
# two-proportion z test on useful-share
p1, p2 = a / max(1, a + b), c / max(1, c + d)
p = (a + c) / max(1, a + b + c + d)
se = math.sqrt(p * (1 - p) * (1 / max(1, a + b) + 1 / max(1, c + d)))
z = (p1 - p2) / se if se else 0.0
print(f"\nuseful-share {100*p1:.1f}% vs {100*p2:.1f}%   difference {100*(p1-p2):+.1f}pp   z = {z:.2f}")
print("z under 1.96 means the two groups are statistically indistinguishable.")

print(f"\nrh on the receipt's useful verdicts: "
      f"{sum(1 for x in ub if x['rh'] == BOIL_RH)} of {len(ub)} carry {BOIL_RH} "
      f"(the constant rh of that constant body) -> they score at peer_useful x6")
ca = collections.Counter(x["attestor"] for x in ub)
print(f"attestors casting useful on the receipt: {len(ca)}")
for did, k in ca.most_common(10):
    tot = sum(1 for x in rows if x["attestor"] == did)
    print(f"   ...{did[-12:]}  {k:3d} useful-on-receipt  of {tot} attests by that DID")
json.dump({"boil": rb, "real": rr}, open("r37_boiler_rows.json", "w"))
