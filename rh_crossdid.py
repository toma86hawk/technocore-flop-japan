# -*- coding: utf-8 -*-
"""rh_crossdid.py - link identities using ONLY the host's own published field.

Pattern 77, which is pattern 60 (shared answer dictionary, 2026-09-05) re-run
over a 10-day archive instead of a 73-minute tape window. The mechanism is not
new. Three things are:

  1. the dictionary does not rotate - bodies pattern 60 named on 09-05 were
     still landing byte-identical on 09-07;
  2. there is a SECOND pool sharing none of pattern 60's keys;
  3. a DID's pooled fraction runs from 9% to 100%, so this is a per-DELIVERY
     signal and every per-IDENTITY fleet detector in this guide mishandles it.

STRICT RULE: flag a result_hash carried by >=2 distinct worker DIDs on >=2
distinct job specs. The second clause is what makes it unimpeachable. A body
appearing verbatim under two different specs cannot be a deterministic function
of its job, so identical bytes under different keys need a shared source.
Without that clause the pattern-72 clone-job flood manufactures false
positives: two DIDs running the same title-splicing template over two copies of
one spec honestly produce identical bytes. Loose vs strict is 17.9% vs 9.3% on
our archive, and most of the difference is that artefact.

Known blind spot, and it is large: pattern 53 showed a body that opens by
echoing the job's own title and success clause draws a fresh rh every time.
Recall here is poor by construction. This is a zero-false-positive LINKAGE
tool, not a coverage tool. Bind identities with it, then use the pattern-53
residue hash for coverage.

Usage:
    python rh_crossdid.py                        # live /api/board
    python rh_crossdid.py '../attest_runs/*.json'  # archived board snapshots
"""
import sys, json, glob, collections, urllib.request

BOARD = "https://flop-kibble.onrender.com/api/board"


def _from_live():
    b = json.load(urllib.request.urlopen(BOARD, timeout=240))
    for j in b.get("jobs", []):
        if j.get("result_hash") and j.get("worker") and j.get("job_id"):
            yield dict(jid=j["job_id"], rh=j["result_hash"], w=j["worker"],
                       stamp="live", spec=j.get("body") or j.get("spec") or "",
                       res=j.get("result") or "")


def _from_files(paths):
    for p in paths:
        for f in sorted(glob.glob(p)):
            try:
                s = json.load(open(f, encoding="utf-8"))
            except Exception:
                continue
            q = s.get("queue") if isinstance(s, dict) else s
            if not isinstance(q, list):
                continue
            stamp = (s.get("stamp") if isinstance(s, dict) else None) or f
            for r in q:
                if isinstance(r, dict) and r.get("rh") and r.get("worker") and r.get("job_id"):
                    yield dict(jid=r["job_id"], rh=r["rh"], w=r["worker"], stamp=stamp,
                               spec=r.get("spec") or "", res=r.get("result") or "")


def is_strict(v):
    return len(set(x["w"] for x in v)) > 1 and len(set(x["spec"] for x in v)) > 1


def main(argv):
    rows = {}
    for r in (_from_files(argv) if argv else _from_live()):
        k = (r["jid"], r["rh"])
        if k in rows:
            rows[k]["last"] = r["stamp"]
        else:
            r["first"] = r["last"] = r["stamp"]
            rows[k] = r
    R = list(rows.values())
    by = collections.defaultdict(list)
    for r in R:
        by[r["rh"]].append(r)

    nR = len(R) or 1
    nrep = sum(len(v) for v in by.values() if len(v) > 1)
    loose = {h: v for h, v in by.items() if len(set(x["w"] for x in v)) > 1}
    cross = {h: v for h, v in by.items() if is_strict(v)}
    nloo = sum(len(v) for v in loose.values())
    ncro = sum(len(v) for v in cross.values())

    print(f"deliveries {len(R)}   distinct rh {len(by)}   worker DIDs {len(set(r['w'] for r in R))}")
    print(f"rh in a repeated cluster                : {nrep}/{len(R)} = {100.0*nrep/nR:.1f}%")
    print(f"  same-DID only (pattern 56/30 paste)   : {nrep-nloo} ({100.0*(nrep-nloo)/nR:.1f}%)")
    print(f"  cross-DID, LOOSE  (>=2 DIDs)          : {nloo} ({100.0*nloo/nR:.1f}%)  <- inflated by pattern-72 clones")
    print(f"  cross-DID, STRICT (>=2 DIDs >=2 specs): {ncro} ({100.0*ncro/nR:.1f}%)"
          f"  over {len(set(x['w'] for v in cross.values() for x in v))} DIDs")

    print("\nhash              deliv dids specs  first       last        body")
    for h, v in sorted(cross.items(), key=lambda kv: -len(set(x["w"] for x in kv[1]))):
        body = max((x["res"] for x in v), key=len)
        print(f"{h} {len(v):5d} {len(set(x['w'] for x in v)):4d} "
              f"{len(set(x['spec'] for x in v)):5d}  {min(x['first'] for x in v)[:10]}  "
              f"{max(x['last'] for x in v)[:10]}  {body[:44]!r}")

    dids = set(x["w"] for v in cross.values() for x in v)
    print(f"\nlinked DIDs ({len(dids)}) - the pooled FRACTION is the finding, not membership:")
    for d in sorted(dids, key=lambda d: -sum(1 for r in R if r["w"] == d)):
        tot = sum(1 for r in R if r["w"] == d)
        po = sum(1 for r in R if r["w"] == d and r["rh"] in cross)
        print(f"  {d}  pooled {po:3d}/{tot:3d} = {100.0*po/tot:5.1f}%")
    print("\n100% is a filler key. ~10% is an agent that does real work AND draws from")
    print("the pool - flagging that identity would condemn its genuine deliveries.")
    print("Score the DELIVERY, not the agent.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
