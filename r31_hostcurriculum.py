"""r31: the host started teaching the rules. Is anyone answering?

Host-timer jobs are new: 0 across 23 board snapshots from 2026-08-28 to
2026-09-03T18:02, first at 2026-09-03T21:06, then 10 and 8 in the two newest.
They are short, honest, rules-of-the-road jobs with explicit Success clauses.

This classifies how each one was actually answered. A deliverable counts as
machine boilerplate when it opens with one of the known splice/template stems
catalogued in rounds 28-30, or when its result_hash is shared with other jobs
in the same window (a constant paste). Both tests are mechanical.
"""
import json, io, collections, sys, re
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

Q = json.load(io.open("attest_queue.json", encoding="utf-8"))
STEMS = ("Deliverable for [", "Explanation:", "Review:", "Build deliverable:",
         "Research findings:", "Coordination deliverable:", "Coordination completed.")

rh_count = collections.Counter(p["rh"] for p in Q)
host = [p for p in Q if "host timer" in ((p.get("spec") or "") + (p.get("title") or ""))]
print(f"host-timer pairs in this window: {len(host)} of {len(Q)}\n")

boiler = 0
for p in host:
    r = (p.get("result") or "").strip()
    stem = next((s for s in STEMS if r.startswith(s)), None)
    shared = rh_count[p["rh"]] > 1
    tag = []
    if stem: tag.append(f"template-stem({stem.strip()})")
    if shared: tag.append(f"constant-paste(rh on {rh_count[p['rh']]} jobs)")
    if tag: boiler += 1
    print(f"{p['job_id']}  {'BOILERPLATE' if tag else 'genuine attempt'}  {', '.join(tag)}")
    print(f"   title: {p['title'][:80]}")
    print(f"   worker ...{p['worker'][-14:]}  rh {p['rh']}")
print(f"\n=> {boiler}/{len(host)} = {100.0*boiler/max(1,len(host)):.1f}% of the host's own "
      f"rule-teaching jobs were answered with machine boilerplate")

print("\n--- constant pastes across the whole window ---")
for rh, n in rh_count.most_common():
    if n < 2: break
    ps = [p for p in Q if p["rh"] == rh]
    dids = {p["worker"] for p in ps}
    print(f"rh {rh}  {n} jobs  {len(dids)} DID(s) ...{list(dids)[0][-14:]}")
    print(f"   body: {(ps[0].get('result') or '')[:110]}")
    print(f"   jobs: {' '.join(p['job_id'] for p in ps)}")
tot = sum(n for rh, n in rh_count.items() if n > 1)
print(f"\n{tot}/{len(Q)} = {100.0*tot/len(Q):.1f}% of reviewable pairs are constant pastes")
