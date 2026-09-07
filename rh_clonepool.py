#!/usr/bin/env python3
"""rh_clonepool.py - measure the CLONE-JOB x SHARED-BODY class.

Round 54 (rh_crossdid.py) required a shared result_hash to span >=2 DIDs AND
>=2 distinct specs, precisely to exclude the case where two agents run the same
honest template against duplicate copies of one spec (pattern 72 clone jobs).
This tool measures that excluded class and shows most of it is not honest.

Discriminator: content-word recall of the spec inside the body.  A body that
is a genuine answer to its spec reuses the spec's content words; a pooled
paragraph parachuted onto an unrelated spec does not.

Input : attest_queue_offboard.json (job_id,title,spec,worker,result,rh)
Output: counts + the offending (rh -> DIDs, titles) groups.
"""
import json, io, re, sys, collections

STOP = set("""a an the and or of to in on for with by as at from is are be was were this that
these those it its into using use used via per than then so such which what when how why
your you we our their there here if not no all any more most other some each both same
answer success validator provide explain describe include list state write give must should
job task deliver delivery result work step steps".split()""".split())

def words(s):
    return [w for w in re.findall(r"[a-z0-9]+", (s or "").lower())
            if len(w) > 3 and w not in STOP]

def recall(spec, body):
    sw = set(words(spec)); bw = set(words(body))
    return len(sw & bw) / len(sw) if sw else 0.0

def main(path="attest_queue_offboard.json", thresh=0.15):
    q = json.load(io.open(path, encoding="utf-8"))
    by = collections.defaultdict(list)
    for e in q:
        if e.get("rh"):
            by[e["rh"]].append(e)

    groups = []
    for rh, es in by.items():
        dids   = {e["worker"] for e in es}
        specs  = {(e.get("spec") or "").strip() for e in es}
        titles = {(e.get("title") or "").strip() for e in es}
        if len(dids) < 2:
            continue
        r = max(recall(e.get("spec"), e.get("result")) for e in es)
        groups.append(dict(rh=rh, n=len(es), dids=len(dids), specs=len(specs),
                           titles=len(titles), recall=round(r, 3),
                           sample_title=es[0]["title"][:90],
                           body=(es[0]["result"] or "")[:110]))

    cross_spec  = [g for g in groups if g["specs"] >= 2]           # round-54 rule
    one_spec    = [g for g in groups if g["specs"] == 1]           # round-54 EXCLUDED
    one_spec_mt = [g for g in one_spec if g["titles"] >= 2]        # clone-job shaped
    offtopic    = [g for g in one_spec_mt if g["recall"] < thresh] # not honest template

    tot = len(q)
    def dl(gs): return sum(g["n"] for g in gs)
    print("pairs in queue            :", tot)
    print("rh groups spanning >=2 DID:", len(groups), "deliveries", dl(groups))
    print("  cross-spec (r54 rule)   :", len(cross_spec), "deliveries", dl(cross_spec),
          "%.1f%%" % (100*dl(cross_spec)/tot))
    print("  single-spec (r54 EXCL.) :", len(one_spec), "deliveries", dl(one_spec))
    print("    of which >=2 titles   :", len(one_spec_mt), "deliveries", dl(one_spec_mt),
          "%.1f%%" % (100*dl(one_spec_mt)/tot))
    print("    ... and recall <%.2f  : %d groups, %d deliveries, %.1f%%"
          % (thresh, len(offtopic), dl(offtopic), 100*dl(offtopic)/tot))
    print("\ntop single-spec/multi-title groups by DID count:")
    for g in sorted(one_spec_mt, key=lambda g: -g["dids"])[:12]:
        print("  rh=%s n=%-3d dids=%-3d titles=%-3d recall=%.2f | %s | %s"
              % (g["rh"], g["n"], g["dids"], g["titles"], g["recall"],
                 g["sample_title"], g["body"][:70]))
    json.dump(dict(cross_spec=cross_spec, one_spec_multi_title=one_spec_mt,
                   offtopic=offtopic),
              io.open("rh_clonepool_out.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main(*sys.argv[1:])
