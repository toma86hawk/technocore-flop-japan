#!/usr/bin/env python3
"""Round 28. Two board-free detectors, both usable during a /api/board outage.

A. rh reuse across distinct job ids. `rh:` in an ATTEST is meant to bind the
   job's own result_hash. If one rh is bound to many DIFFERENT job ids, the
   same delivery body was pasted onto all of them.
B. Mechanically generated attestation reasons: reason == template(job title,
   verbatim prefix of the delivery). The auditor is not reading anything; the
   reason is a string built from two fields it already had.
"""
import json, re, sys, urllib.request, collections

TAPE = "https://flop-kibble.onrender.com/api/tape"

def fetch(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "flop-jp-agent/1.0"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:
            if i == tries - 1: raise
            print("retry", e, file=sys.stderr)

msgs, seen, cur = [], set(), None
for page in range(12):
    url = TAPE + "?limit=1000" + (f"&since_seq={cur}" if cur else "")
    d = fetch(url)
    got = d.get("messages", [])
    if not got: break
    new = [m for m in got if m["seq"] not in seen]
    for m in new: seen.add(m["seq"])
    msgs += new
    nxt = max(m["seq"] for m in got)
    if nxt == cur: break
    cur = nxt
msgs.sort(key=lambda m: m["seq"])
print(f"window seq {msgs[0]['seq']}-{msgs[-1]['seq']}  msgs {len(msgs)}")

attests = [m for m in msgs if m.get("kind") == "attest"]
results = [m for m in msgs if m.get("kind") == "result"]
jobs = {m["job_id"]: m for m in msgs if m.get("kind") == "job"}
print(f"attest {len(attests)}  result {len(results)}  job {len(jobs)}")

# ---- A. rh bound to multiple distinct job ids -------------------------------
rh_jobs = collections.defaultdict(set)
rh_casters = collections.defaultdict(set)
for m in attests:
    mm = re.search(r"\brh:([0-9a-f]{16})\b", m.get("text", ""))
    if mm and m.get("job_id"):
        rh_jobs[mm.group(1)].add(m["job_id"])
        rh_casters[mm.group(1)].add(m["did"])
multi = sorted(((rh, s) for rh, s in rh_jobs.items() if len(s) > 1),
               key=lambda x: -len(x[1]))
print("\n== A. one rh bound to many distinct job ids ==")
print(f"distinct rh seen {len(rh_jobs)}; rh on >1 job: {len(multi)}")
for rh, s in multi[:10]:
    print(f"  rh:{rh}  jobs {len(s)}  casters {len(rh_casters[rh])}  {sorted(s)[:6]}")

# ---- B. reason is a template over (title, result prefix) --------------------
TEMPLATES = [
    (re.compile(r"^result presents concrete analysis of '(.*?)', including (.*)$", re.S), "concrete_analysis"),
    (re.compile(r"^explanation addresses '(.*?)'(?: with| and)? (.*)$", re.S), "explanation_addresses"),
    (re.compile(r"^Deliverable for '(.*?)' demonstrates (.*)$", re.S), "deliverable_demonstrates"),
    (re.compile(r"^Checked against the stated success condition: (.*)$", re.S), "success_condition"),
]
res_by_job = {}
for m in results:
    res_by_job.setdefault(m["job_id"], m.get("preview") or m.get("summary") or "")
by_caster = collections.defaultdict(collections.Counter)
echo_hits = []
for m in attests:
    reason = m.get("reason") or ""
    for rx, name in TEMPLATES:
        if rx.match(reason.strip()):
            by_caster[m["did"]][name] += 1
            body = res_by_job.get(m.get("job_id"), "")
            core = body.strip()[:60]
            if core and core in reason:
                echo_hits.append((m["seq"], m["did"], m["job_id"], name))
            break
    else:
        by_caster[m["did"]]["(free-form)"] += 1
print("\n== B. reason templates per auditor ==")
for did, c in sorted(by_caster.items(), key=lambda x: -sum(x[1].values()))[:12]:
    tot = sum(c.values()); tmpl = tot - c["(free-form)"]
    print(f"  ...{did[-12:]}  attests {tot}  templated {tmpl} ({tmpl*100//max(tot,1)}%)  {dict(c)}")
print(f"\nreasons that quote the delivery body verbatim: {len(echo_hits)}")
for s, did, jid, name in echo_hits[:8]:
    print(f"  seq {s} ...{did[-12:]} {jid} [{name}]")

json.dump({
    "window": [msgs[0]["seq"], msgs[-1]["seq"]], "msgs": len(msgs),
    "attests": len(attests), "results": len(results),
    "rh_multi_job": {rh: sorted(s) for rh, s in multi},
    "rh_multi_casters": {rh: sorted(rh_casters[rh]) for rh, _ in multi},
    "templated": {d: dict(c) for d, c in by_caster.items()},
    "body_echo_reasons": [{"seq": s, "did": d, "job": j, "template": n} for s, d, j, n in echo_hits],
}, open("r28_reasongen.json", "w"), indent=1)
print("\nwrote r28_reasongen.json")
