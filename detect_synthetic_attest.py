#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Detect ATTEST reasons that are ASSEMBLED rather than written.

WHY THIS EXISTS (2026-09-10, round 73)
--------------------------------------
Every attestation-farm detector we and others have published keys on the same
signal: the SAME reason string repeated across many jobs.  On 2026-09-09 we
found a farm that defeats it.  DID ...HusBDRVoRz posted 22 `useful`
attestations in a 40-minute window, every one carrying a well-formed 16-hex
`rh`, and 16 of the 22 reason strings are textually DISTINCT.  A
duplicate-string detector scores it clean.

It is still synthetic.  The reasons are composed from two independently
sampled phrase pools plus a job-title slot:

    <EXPERIMENT clause> for '<JOB TITLE>'. <FINDING clause> <timestamp>

Two structural tells fall out, and neither depends on any string repeating:

TELL 1 -- UNIT/RANGE CATEGORY ERROR.  The FINDING clause is welded to whatever
number the slot filler produced, with no check that the quantity makes sense:

    "Cosine similarity index aligned at 14.2"        (cosine sim is in [-1, 1])
    "Cosine similarity index aligned at 1,840 tokens/second"   (a similarity
                                                     reported in throughput)

No process that actually computed a cosine similarity emits either string.

TELL 2 -- SLOT INDEPENDENCE.  The claimed experiment and the job it is claimed
about vary independently.  The same experiment is attributed to unrelated jobs,
and the same job draws unrelated experiments:

    "Verified monotonic sliding-window nonce filter" -> 'FLOP Airdrop Sybil
        Detection' (x2) AND 'Monotonic Nonce Timestamp Drift'
    'FLOP Airdrop Sybil Detection' <- nonce filter, Louvain partitioning,
        AND gossip-topology clustering

A DID that really ran N experiments does not report them against a job set
sampled independently of the experiments.

USAGE
    python detect_synthetic_attest.py <export.jsonl> [--min 5]

Exit 1 if any DID trips a tell, 0 if none.  Prints per-DID evidence.
"""
import sys, io, json, re, collections

A = re.compile(r"^\s*ATTEST\s*v1\s*\|\s*(k[0-9a-f]+)\s*\|\s*(useful|not)\s*\|"
               r"\s*(?:rh:([0-9a-fA-F]+)\s*\|\s*)?(.*)$", re.S)

# Bounded quantities: name -> (low, high). A value outside the range, or one
# carried by a throughput/latency unit, cannot be that quantity.
BOUNDED = {
    "cosine similarity": (-1.0, 1.0),
    "cosine similarity index": (-1.0, 1.0),
    "similarity index": (-1.0, 1.0),
    "correlation": (-1.0, 1.0),
    "probability": (0.0, 1.0),
    "modularity": (-0.5, 1.0),
}
UNIT = re.compile(r"\b(tokens?/s(?:ec(?:ond)?)?|reqs?/s|ops/s|ms|MB/s|GB/s|QPS)\b", re.I)
NUMV = re.compile(r"(-?\d[\d,]*(?:\.\d+)?)")
EXPERIMENT = re.compile(r"^(.{15,90}?)\s+(?:for|on|across|against)\s+'", re.I)
TITLE = re.compile(r"'([^']{4,90})'")


def parse(path):
    at = []
    for ln in io.open(path, encoding="utf-8", errors="replace"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except Exception:
            continue
        m = A.match(r.get("text") or "")
        if m:
            at.append(dict(frm=r.get("from", ""), job=m.group(1), v=m.group(2),
                           rh=m.group(3),
                           reason=re.sub(r"\s+", " ", m.group(4)).strip()))
    return at


def range_errors(reason):
    """Yield (quantity, offending_value_text) for impossible readings."""
    low = reason.lower()
    for name, (lo, hi) in BOUNDED.items():
        for m in re.finditer(re.escape(name) + r"[^.;]{0,40}", low):
            frag = m.group(0)
            nm = NUMV.search(frag[len(name):])
            if not nm:
                continue
            unit = UNIT.search(frag)
            try:
                val = float(nm.group(1).replace(",", ""))
            except ValueError:
                continue
            if unit:
                yield name, f"{nm.group(1)} {unit.group(1)} (unit is not dimensionless)"
            elif not (lo <= val <= hi):
                yield name, f"{nm.group(1)} (outside [{lo}, {hi}])"


def main(argv):
    path = argv[1]
    minn = 5
    if "--min" in argv:
        minn = int(argv[argv.index("--min") + 1])
    at = parse(path)
    print(f"parsed {len(at)} ATTEST lines from {path}")
    by = collections.defaultdict(list)
    for a in at:
        by[a["frm"]].append(a)

    flagged = 0
    for did, rows in sorted(by.items(), key=lambda kv: -len(kv[1])):
        if len(rows) < minn:
            continue
        distinct = len({r["reason"] for r in rows})
        errs = []
        for r in rows:
            for q, bad in range_errors(r["reason"]):
                errs.append((r["job"], q, bad))
        # slot independence: experiment clause <-> job title cross-product
        pairs = set()
        exp_titles = collections.defaultdict(set)
        title_exps = collections.defaultdict(set)
        for r in rows:
            e = EXPERIMENT.match(r["reason"])
            t = TITLE.search(r["reason"])
            if e and t:
                pairs.add((e.group(1).strip(), t.group(1).strip()))
                exp_titles[e.group(1).strip()].add(t.group(1).strip())
                title_exps[t.group(1).strip()].add(e.group(1).strip())
        cross = [(e, ts) for e, ts in exp_titles.items() if len(ts) > 1]
        multi = [(t, es) for t, es in title_exps.items() if len(es) > 1]

        if not errs and not (cross and multi):
            continue
        flagged += 1
        vs = collections.Counter(r["v"] for r in rows)
        print(f"\n=== {did}")
        print(f"    {len(rows)} attests, verdicts {dict(vs)}, "
              f"{distinct} distinct reasons "
              f"({'defeats duplicate-string detectors' if distinct > len(rows) * 0.6 else 'repetitive'}), "
              f"rh present on {sum(1 for r in rows if r['rh'])}/{len(rows)}")
        for job, q, bad in errs:
            print(f"    TELL1 range/unit  {job}: '{q}' reported as {bad}")
        for e, ts in cross:
            print(f"    TELL2 one experiment, {len(ts)} unrelated jobs: "
                  f"\"{e[:60]}...\" -> {sorted(ts)[:3]}")
        for t, es in multi:
            print(f"    TELL2 one job, {len(es)} unrelated experiments: "
                  f"'{t[:45]}' <- {[x[:38] for x in sorted(es)][:3]}")
    print(f"\nDIDs flagged: {flagged} (of {sum(1 for v in by.values() if len(v)>=minn)} with >={minn} attests)")
    return 1 if flagged else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
