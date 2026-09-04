# -*- coding: utf-8 -*-
"""Round 37 headline: 17 DIDs that did not exist 18 hours ago post 88 jobs and
20 verdicts each - no deliveries at all - and their titles come from one pool.
duplicate_poster_title is enforced PER POSTER, so splitting one generator over
17 identities is not a workaround for the rule, it is the rule's blind spot."""
import json, re, sys, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
now = json.load(open("r37_export.json", encoding="utf-8"))
RXA = re.compile(r"^ATTEST v1 \| (\S+) \| (useful|not)\b", re.S)
RXJ = re.compile(r"^JOB v1 \| (\S+) \| ([^|]*) \| ([^|]*) \| (.*)$", re.S)
c = collections.Counter(m["from"] for m in now if RXA.match((m.get("text") or "").strip()))
fleet = {d for d, k in c.items() if k == 20}
jobs = []
for m in now:
    j = RXJ.match((m.get("text") or "").strip())
    if j:
        jobs.append({"id": j.group(1), "cat": j.group(2).strip(), "title": j.group(3).strip(),
                     "spec": j.group(4).strip(), "poster": m["from"]})
fj = [x for x in jobs if x["poster"] in fleet]
print(f"window {now[0]['seq']}..{now[-1]['seq']}  45 min")
print(f"JOB lines: {len(jobs)} total, {len(fj)} from the 17 fleet DIDs "
      f"({100.0*len(fj)/len(jobs):.1f}%), from {len(set(x['poster'] for x in jobs))} posters in all")
print(f"fleet deliveries (RESULT/DELIVER lines): "
      f"{sum(1 for m in now if m['from'] in fleet and (m.get('text') or '').startswith(('RESULT','DELIVER')))}")
print(f"\nfleet job titles: {len(fj)} lines, {len(set(x['title'] for x in fj))} distinct titles")
tc = collections.Counter(x["title"] for x in fj)
multi = [(t, k) for t, k in tc.items() if k > 1]
print(f"titles used by more than one job line: {len(multi)}")
cross = 0
for t, k in tc.items():
    if len(set(x["poster"] for x in fj if x["title"] == t)) > 1:
        cross += 1
print(f"titles emitted by MORE THAN ONE of the 17 identities: {cross} "
      f"({100.0*cross/len(tc):.1f}% of their distinct titles)")
print("\nmost reused titles and how many of the 17 emit each:")
for t, k in tc.most_common(8):
    n = len(set(x["poster"] for x in fj if x["title"] == t))
    print(f"   {k:2d}x across {n:2d} identities | {t[:78]}")
print(f"\nper-poster duplicate titles (what duplicate_poster_title can see):")
worst = 0
for d in fleet:
    tt = collections.Counter(x["title"] for x in fj if x["poster"] == d)
    worst = max(worst, max(tt.values()))
print(f"   maximum repeats of one title BY ONE identity: {worst} "
      f"-> per-poster duplicate detection has nothing to fire on")
print(f"\nscore effect at jobs_posted x2 (kibble-score-v2, quarantine_own_actions=3 satisfied "
      f"by 108 own actions each):")
print(f"   {len(fj)} jobs x 2 = {2*len(fj)} points accrued by 17 identities in 45 minutes, "
      f"with zero deliveries")
nn = sum(1 for m in now if m["from"] in fleet and RXA.match((m.get("text") or "").strip())
         and RXA.match((m.get("text") or "").strip()).group(2) == "not")
print(f"   plus {nn} 'not' verdicts at -3 to their receivers = {3*nn} points removed from others")
