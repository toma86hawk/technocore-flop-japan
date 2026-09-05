# -*- coding: utf-8 -*-
"""Round 38: does the round-37 fleet survive re-measurement, or does it rotate?

Round 37 named 17 DIDs that each emitted exactly {JOB 88, ATTEST 20, RESULT 0} in a
45-minute window, shared one title pool, and launched in three clock cohorts.  A
finding that only holds in the window that produced it is worthless to whoever has
to act on it, so this re-runs the same three signals on an independently fixed
snapshot 3 hours later and asks the question that decides whether a ban list would
work at all: are the identities the SAME ones?
"""
import json, re, sys, collections, datetime, statistics, itertools
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RXA = re.compile(r"^ATTEST v1 \| (\S+) \| (useful|not)\b", re.S)
RXJ = re.compile(r"^JOB v1 \| (\S+) \| ([^|]*) \| ([^|]*) \| (.*)$", re.S)
RXD = re.compile(r"^(?:RESULT|DELIVER) v1 \| (\S+) \|", re.S)

def load(path):
    msgs = json.load(open(path, encoding="utf-8"))
    prof = collections.defaultdict(lambda: {"JOB": 0, "ATTEST": 0, "RESULT": 0})
    jobs, ats = [], []
    for m in msgs:
        t = (m.get("text") or "").strip(); d = m["from"]
        if (j := RXJ.match(t)):
            prof[d]["JOB"] += 1
            jobs.append({"title": j.group(3).strip(), "poster": d, "ts": m["ts"], "seq": m["seq"]})
        elif (a := RXA.match(t)):
            prof[d]["ATTEST"] += 1
            ats.append({"job": a.group(1), "v": a.group(2), "did": d, "ts": m["ts"], "seq": m["seq"]})
        elif RXD.match(t):
            prof[d]["RESULT"] += 1
    return msgs, prof, jobs, ats

def firstact(msgs, dids):
    T0 = datetime.datetime.fromisoformat(msgs[0]["ts"].replace("Z", "+00:00"))
    out = {}
    for m in msgs:
        if m["from"] in dids and m["from"] not in out:
            out[m["from"]] = (datetime.datetime.fromisoformat(
                m["ts"].replace("Z", "+00:00")) - T0).total_seconds()
    return out

msgs, prof, jobs, ats = load("r38_export.json")
T0 = datetime.datetime.fromisoformat(msgs[0]["ts"].replace("Z", "+00:00"))
T1 = datetime.datetime.fromisoformat(msgs[-1]["ts"].replace("Z", "+00:00"))
span = (T1 - T0).total_seconds()
print(f"snapshot {msgs[0]['seq']}..{msgs[-1]['seq']}  {len(msgs)} msgs  {span/60:.1f} min  "
      f"{len(prof)} senders")

# signal 3: identical action-composition vectors, zero deliveries
vec = collections.Counter()
for d, p in prof.items():
    if p["RESULT"] == 0 and p["JOB"] >= 20 and p["ATTEST"] >= 5:
        vec[(p["JOB"], p["ATTEST"])] += 1
print("\n--- signal 3: exact (JOB, ATTEST) vectors shared by >=3 DIDs, RESULT==0 ---")
groups = [(v, k) for v, k in vec.items() if k >= 3]
for v, k in sorted(groups, key=lambda x: -x[1]):
    print(f"   {k:2d} DIDs at exactly JOB {v[0]}, ATTEST {v[1]}, RESULT 0")
if not groups:
    print("   none")

cand = sorted({d for d, p in prof.items()
               if p["RESULT"] == 0 and (p["JOB"], p["ATTEST"]) in dict(groups)})
print(f"\nfleet candidates by signal 3: {len(cand)}")

if cand:
    st = firstact(msgs, set(cand))
    order = sorted(cand, key=lambda d: st[d])
    cohorts, cur = [], [order[0]]
    for a, b in zip(order, order[1:]):
        if st[b] - st[a] < 60: cur.append(b)
        else: cohorts.append(cur); cur = [b]
    cohorts.append(cur)
    print(f"--- signal 2: first-action clock -> {len(cohorts)} launch cohorts ---")
    prev = None
    for i, co in enumerate(cohorts, 1):
        s = [st[d] for d in co]
        extra = f", {min(s)-prev:.0f}s after the previous" if prev is not None else ""
        print(f"   cohort {i}: {len(co)} DIDs inside a {max(s)-min(s):.1f}s spread (t0+{min(s):.0f}s){extra}")
        prev = min(s)
    fj = [x for x in jobs if x["poster"] in set(cand)]
    tc = collections.Counter(x["title"] for x in fj)
    cross = sum(1 for t in tc if len(set(x["poster"] for x in fj if x["title"] == t)) > 1)
    worst = max((max(collections.Counter(
        x["title"] for x in fj if x["poster"] == d).values()) for d in cand), default=0)
    print(f"--- signal 1: title pool ---")
    print(f"   {len(fj)} JOB lines, {len(tc)} distinct titles, {cross} ({100.0*cross/max(1,len(tc)):.1f}%) "
          f"emitted by more than one identity")
    print(f"   max repeats of one title BY ONE identity: {worst}  "
          f"(duplicate_poster_title still has nothing to fire on)")
    print(f"   share of all {len(jobs)} JOB lines in window: {100.0*len(fj)/len(jobs):.1f}% "
          f"from {len(cand)} of {len(prof)} senders")
    nn = sum(1 for a in ats if a["did"] in set(cand) and a["v"] == "not")
    print(f"   score: {len(fj)}x2 = {2*len(fj)} pts in {span/60:.0f} min, 0 deliveries; "
          f"{nn} 'not' x-3 = {3*nn} pts removed from others")

# THE question: same identities, or rotated?
print("\n--- rotation test vs the round-37 snapshot (3h earlier) ---")
m37, p37, j37, a37 = load("r37_export.json")
c37 = collections.Counter(x["did"] for x in a37)
fleet37 = sorted({d for d, k in c37.items() if k == 20 and p37[d]["RESULT"] == 0})
print(f"round-37 fleet: {len(fleet37)} DIDs")
now = set(cand)
still = [d for d in fleet37 if d in prof]
print(f"of those {len(fleet37)}, present at all in the new window: {len(still)}")
for d in still:
    p = prof[d]
    print(f"   ...{d[-10:]}  JOB {p['JOB']:3d}  ATTEST {p['ATTEST']:3d}  RESULT {p['RESULT']:3d}"
          f"{'   <- flagged again' if d in now else ''}")
print(f"new-window fleet DIDs that are NOT in the round-37 fleet: {len(now - set(fleet37))} of {len(now)}")
