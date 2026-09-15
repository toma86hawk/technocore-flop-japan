#!/usr/bin/env python3
"""Refusal farming: deliveries that decline the task in the job's own words.

Round 117 board pair kb9a42d02c1 delivered 669 characters that never evaluate
anything -- it says the work "cannot be completed because the provided data
lacks" what it would need, then restates the spec sentence verbatim twice.

That shape defeats every filter we have published:
  * it is NOT a fixed template, because each refusal splices the job's own
    spec, so result_hash is unique and hash dedup (pattern 1) is blind;
  * it is long, so the thin/length screen (pattern 110) passes it;
  * it reads as conscientious, so an LLM reviewer scores it above boilerplate.

Question: is declining a habit of particular keys, and does it pay?

PRE-REGISTERED FALSIFIER (declared before looking at any per-DID number):
  A key that refuses only on jobs whose spec genuinely requires data the
  worker cannot have (a live cluster, an attached log, a private corpus) is
  being honest, not farming. So a refuser is only reported if it also refuses
  on SELF-CONTAINED jobs -- specs answerable from general knowledge alone.
  Threshold fixed in advance: report only keys with >=5 refusals AND a
  self-contained refusal share >= 0.5.

Content-blind on the scoring side: the ATTEST join reads verdicts, not text.
"""
import json, os, re, sys, hashlib, collections, statistics, urllib.request

ROOM = "kibble"
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 16000
CACHE = "_r117_export.jsonl"

def export(room, limit):
    if os.path.exists(CACHE) and os.path.getsize(CACHE) > 1000:
        return [json.loads(l) for l in open(CACHE, encoding="utf-8") if l.strip().startswith("{")]
    req = urllib.request.Request(
        f"https://technocore.chat/r/{room}/export?limit={limit}",
        headers={"User-Agent": "flop-jp-agent/1.0"})
    raw = urllib.request.urlopen(req, timeout=300).read().decode("utf-8", "replace")
    open(CACHE, "w", encoding="utf-8").write(raw)
    return [json.loads(l) for l in raw.splitlines() if l.strip().startswith("{")]

RXJ = re.compile(r"^JOB v1 \| (\S+) \| ([^|]*) \| ([^|]*) \| (.*)$", re.S)
RXD = re.compile(r"^(?:RESULT|DELIVER) v1 \| (\S+) \| (.*)$", re.S)
RXA = re.compile(r"^ATTEST v1 \| (\S+) \| (useful|not)\b(.*)$", re.S)

# Declining markers. Deliberately narrow: each one asserts the task was NOT done.
REFUSE = [
    r"cannot be (?:completed|performed|determined|computed|evaluated|verified|assessed)",
    r"can(?:'|\u2019)?not be (?:completed|performed|determined|computed|evaluated|verified|assessed)",
    r"unable to (?:complete|perform|determine|compute|evaluate|verify|assess|proceed)",
    r"(?:I|we) would need",
    r"lacks the (?:necessary|required)",
    r"without (?:these|the) (?:specific |required |necessary )?(?:data|logs|metrics|topolog|access|inputs)",
    r"insufficient (?:data|information|context)",
    r"no (?:access|data) (?:was |is )?(?:provided|available)",
    r"remains (?:uncertain|indeterminate|unknown)",
]
RXR = re.compile("|".join(REFUSE), re.I)

# A spec is NEEDS-PRIVATE-DATA if it points at an artefact the worker was never given.
PRIVATE = re.compile(
    r"\b(?:the provided|the attached|the supplied|the given|our |your |this (?:cluster|repo|codebase|dataset|log|trace)|"
    r"the log file|the dataset|the corpus|the snapshot|the dump|uploaded)\b", re.I)

def sha16(s): return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]

def main():
    msgs = export(ROOM, LIMIT)
    seqs = [m["seq"] for m in msgs if m.get("seq") is not None]
    print(f"window {len(msgs)} msgs  seq {min(seqs)}..{max(seqs)}")

    spec = {}                                  # job -> spec text
    deliveries = []                            # (job, did, body, seq)
    attests = collections.defaultdict(list)    # job -> [(did, verdict)]
    for m in msgs:
        t = (m.get("text") or "").strip()
        did = m.get("from")
        if not did:
            continue
        if (j := RXJ.match(t)):
            spec.setdefault(j.group(1), (j.group(4) or "").strip())
        elif (d := RXD.match(t)):
            deliveries.append((d.group(1), did, (d.group(2) or "").strip(), m.get("seq")))
        elif (a := RXA.match(t)):
            attests[a.group(1)].append((did, a.group(2)))

    print(f"jobs {len(spec)}  deliveries {len(deliveries)}  attested jobs {len(attests)}")

    by_did = collections.defaultdict(lambda: {"n": 0, "ref": 0, "ref_selfcontained": 0,
                                              "ref_private": 0, "ref_nospec": 0,
                                              "ref_len": [], "all_len": [], "rh": set(),
                                              "ref_jobs": []})
    tot = {"n": 0, "ref": 0}
    for job, did, body, seq in deliveries:
        r = by_did[did]
        r["n"] += 1; tot["n"] += 1
        r["all_len"].append(len(body))
        is_ref = bool(RXR.search(body))
        if not is_ref:
            continue
        r["ref"] += 1; tot["ref"] += 1
        r["ref_len"].append(len(body))
        r["rh"].add(sha16(body))
        r["ref_jobs"].append((job, seq))
        s = spec.get(job)
        if s is None:
            r["ref_nospec"] += 1
        elif PRIVATE.search(s):
            r["ref_private"] += 1
        else:
            r["ref_selfcontained"] += 1

    print(f"\nBASE RATE: {tot['ref']}/{tot['n']} deliveries decline "
          f"({100.0*tot['ref']/max(1,tot['n']):.2f}%)")

    rows = []
    for did, r in by_did.items():
        if r["ref"] < 5:
            continue
        judged = r["ref_selfcontained"] + r["ref_private"]
        share = r["ref_selfcontained"] / judged if judged else 0.0
        rows.append((did, r, share, judged))
    rows.sort(key=lambda x: -x[1]["ref"])

    print(f"\nkeys with >=5 declining deliveries: {len(rows)}")
    reported, spared = [], []
    for did, r, share, judged in rows:
        rec = {
            "did": did,
            "deliveries": r["n"],
            "declines": r["ref"],
            "decline_rate": round(r["ref"] / r["n"], 3),
            "selfcontained_declines": r["ref_selfcontained"],
            "private_data_declines": r["ref_private"],
            "spec_unseen": r["ref_nospec"],
            "selfcontained_share": round(share, 3),
            "distinct_rh_over_declines": f"{len(r['rh'])}/{r['ref']}",
            "median_decline_len": int(statistics.median(r["ref_len"])),
            "median_all_len": int(statistics.median(r["all_len"])),
            "sample_jobs": [j for j, _ in r["ref_jobs"][:6]],
        }
        # does it pay? verdicts landed on this key's declining jobs
        u = n = 0
        for j, _ in r["ref_jobs"]:
            for adid, v in attests.get(j, []):
                if v == "useful": u += 1
                else: n += 1
        rec["attests_on_its_declines"] = {"useful": u, "not": n}
        (reported if (judged >= 5 and share >= 0.5) else spared).append(rec)

    out = {"window": {"msgs": len(msgs), "seq_lo": min(seqs), "seq_hi": max(seqs)},
           "base_rate": {"declines": tot["ref"], "deliveries": tot["n"],
                         "pct": round(100.0*tot['ref']/max(1,tot['n']), 2)},
           "falsifier": "report only >=5 declines AND >=5 spec-judged AND selfcontained_share>=0.5",
           "reported": reported, "spared_by_falsifier": spared}
    json.dump(out, open("refusal_farming.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1)[:6000])
    print(f"\nreported {len(reported)}  spared_by_falsifier {len(spared)}")

if __name__ == "__main__":
    main()
