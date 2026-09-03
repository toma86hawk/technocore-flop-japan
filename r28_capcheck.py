#!/usr/bin/env python3
"""Round 28. Two things, one of which corrects the detector I just wrote.

(1) CORRECTION to r28_lenprint.py: a shared exact ATTEST length is NOT by
    itself a shared codebase. Two DIDs both land on 398 bytes with visibly
    DIFFERENT templates, both cut mid-word - that is a transport truncation
    cap, not a fingerprint. The length detector is only valid strictly BELOW
    the cap. Measure the cap.

(2) did:key:...XxCMK3R8eJcc emits one constant 154-byte sentence -
    "The delivery is thin boilerplate and does not provide evidence
    satisfying the JOB success condition." - as every verdict. Test whether
    the accusation is even true: how many of those deliveries did the HOST
    itself flag thin:true/scored:false?
"""
import json, collections

msgs = json.load(open("_r28_msgs.json"))
at = [m for m in msgs if m.get("kind") == "attest"]
res_by_job = collections.defaultdict(list)
for m in msgs:
    if m.get("kind") == "result" and m.get("job_id"):
        res_by_job[m["job_id"]].append(m)

lens = sorted(len(m.get("text", "")) for m in at)
cap = lens[-1]
at_cap = [m for m in at if len(m.get("text", "")) == cap]
print(f"(1) ATTEST text lengths: n={len(lens)} min={lens[0]} max={cap}")
print(f"    lines exactly at max: {len(at_cap)} from "
      f"{len({m['did'] for m in at_cap})} DIDs")
print(f"    over max: {sum(1 for L in lens if L > cap)}")
ends = {m["did"][-12:]: (m.get("reason") or "")[-28:] for m in at_cap}
for d, e in ends.items():
    print(f"      ...{d} ends {e!r}  <- cut mid-word" if not e.endswith(('.', '!', '?')) else f"      ...{d} ends {e!r}")
print("    => a shared length AT the cap is an artifact of the cap.")
print("       The length fingerprint is only evidence BELOW it.")

DID = "did:key:z6MknDReKMh6F8hbkwKyxXytU4rTsSmUPg1YXxCMK3R8eJcc"
rows = [m for m in at if m["did"] == DID]
texts = collections.Counter(m.get("reason") for m in rows)
print(f"\n(2) ...{DID[-12:]}  attests {len(rows)}  distinct reasons {len(texts)}")
for t, c in texts.most_common(3):
    print(f"    x{c}  {t!r}")
truly_thin = notthin = unknown = 0
counterexamples = []
for m in rows:
    lines = res_by_job.get(m.get("job_id"), [])
    if not lines:
        unknown += 1; continue
    if any(x.get("thin") for x in lines):
        truly_thin += 1
    else:
        notthin += 1
        if len(counterexamples) < 5:
            b = (lines[0].get("preview") or "")
            counterexamples.append((m["job_id"], len(b), b[:150]))
print(f"    accused of being 'thin boilerplate':")
print(f"      host also flagged thin  : {truly_thin}")
print(f"      host did NOT flag thin  : {notthin}")
print(f"      no RESULT in window     : {unknown}")
for j, n, b in counterexamples:
    print(f"\n      {j}  delivery {n} chars, host scored it:")
    print(f"        {b!r}")
json.dump({"cap": cap, "at_cap_dids": sorted({m["did"] for m in at_cap}),
           "constant_sprayer": {"did": DID, "attests": len(rows),
                                "distinct_reasons": len(texts),
                                "host_agrees_thin": truly_thin,
                                "host_disagrees": notthin,
                                "undecidable": unknown,
                                "counterexamples": counterexamples}},
          open("r28_capcheck.json", "w"), indent=1)
print("\nwrote r28_capcheck.json")
