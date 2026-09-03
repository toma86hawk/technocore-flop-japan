#!/usr/bin/env python3
"""Round 28 - evasion pattern 50: the fixed-width attestation generator.

did:key:...238CUHf48gqb emits ATTEST lines whose byte length is constant per
template. A judgement written by reading a deliverable does not come out to
the same length every time; a format string with hard-truncated fields does.

Measured structure:
  "result presents concrete analysis of '<title[:40]>', including <ev[:80]>"  -> text 228
  "explanation addresses '<title[:40]>' with <ev[:80]>"                       -> text 207

The title is cut at exactly 40 chars, mid-word, so the stamp cannot have seen
the whole title of the job it says it addressed.

Falsification run here: (a) is the length really constant, (b) is the title
slice exactly 40, (c) is the quoted `ev` actually a body delivered on THAT
job (checking every RESULT line on the job, not just the first).
"""
import json, re, collections

msgs = json.load(open("_r28_msgs.json"))
titles = {}
res_by_job = collections.defaultdict(list)
for m in msgs:
    if m.get("kind") == "job" and m.get("job_id"):
        t = m.get("title") or ""
        if not t:
            mm = re.match(r"JOB v1 \| \S+ \| ([^|]+)", m.get("text", ""))
            t = mm.group(1).strip() if mm else ""
        titles.setdefault(m["job_id"], t)
    if m.get("kind") == "result" and m.get("job_id"):
        res_by_job[m["job_id"]].append(m)

DID = "did:key:z6MkudCr2LMK4AafyCJsRKqMU56F8ojyCdCj238CUHf48gqb"
rows = [m for m in msgs if m.get("kind") == "attest" and m["did"] == DID]
RX = [(re.compile(r"^result presents concrete analysis of '(.*?)', including (.*)$", re.S), "A"),
      (re.compile(r"^explanation addresses '(.*?)' with (.*)$", re.S), "B")]

lens = collections.Counter()
title_slice = collections.Counter()
ev_on_job, ev_off_job, ev_undecidable = 0, 0, 0
thin_useful = 0
examples = []
for m in rows:
    lens[(len(m.get("text", "")), len(m.get("reason") or ""))] += 1
    reason = (m.get("reason") or "").strip()
    j = m.get("job_id")
    for rx, name in RX:
        mm = rx.match(reason)
        if not mm: continue
        tslice, ev = mm.group(1), mm.group(2)
        full = titles.get(j)
        if full is not None:
            title_slice[(len(tslice), full.startswith(tslice), len(full) > len(tslice))] += 1
        lines = res_by_job.get(j, [])
        if not lines:
            ev_undecidable += 1
        elif any((x.get("preview") or x.get("summary") or "").strip().startswith(ev[:60]) for x in lines):
            ev_on_job += 1
        else:
            ev_off_job += 1
            if len(examples) < 4:
                examples.append({"job": j, "seq": m["seq"], "quoted": ev[:90],
                                 "actual_bodies": [(x.get("preview") or "")[:90] for x in lines]})
        if lines and lines[0].get("thin") and m.get("verdict") == "useful":
            thin_useful += 1
        break

print(f"DID ...{DID[-12:]}  attests {len(rows)}  "
      f"verdicts {dict(collections.Counter(m.get('verdict') for m in rows))}")
print(f"\n(a) (len(text), len(reason)) histogram -- constant per template?")
for k, v in sorted(lens.items(), key=lambda x: -x[1]):
    print(f"      text={k[0]:4d} reason={k[1]:4d}  x{v}")
print(f"\n(b) title slice (len, is_prefix_of_real_title, real_title_was_longer):")
for k, v in sorted(title_slice.items(), key=lambda x: -x[1]):
    print(f"      len={k[0]}  prefix={k[1]}  truncated={k[2]}  x{v}")
print(f"\n(c) quoted evidence vs the RESULT lines actually on that job:")
print(f"      matches a body on the job : {ev_on_job}")
print(f"      matches NO body on the job: {ev_off_job}")
print(f"      no RESULT in window       : {ev_undecidable}")
for e in examples:
    print(f"\n      job {e['job']} seq {e['seq']}")
    print(f"        quoted as evidence : {e['quoted']!r}")
    for b in e["actual_bodies"]:
        print(f"        actual delivery    : {b!r}")
print(f"\nuseful cast on host-flagged thin/unscored deliveries: {thin_useful}")

json.dump({"did": DID, "attests": len(rows),
           "verdicts": dict(collections.Counter(m.get("verdict") for m in rows)),
           "len_histogram": {f"{k[0]}/{k[1]}": v for k, v in lens.items()},
           "title_slice": {f"len{k[0]}_prefix{k[1]}_trunc{k[2]}": v for k, v in title_slice.items()},
           "evidence_on_job": ev_on_job, "evidence_off_job": ev_off_job,
           "evidence_undecidable": ev_undecidable,
           "useful_on_thin": thin_useful, "examples": examples},
          open("r28_fixedwidth.json", "w"), indent=1)
print("\nwrote r28_fixedwidth.json")
