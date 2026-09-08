#!/usr/bin/env python3
"""The non-request JOBs and the filler RESULTs are built from ONE phrase pool.
Test it on the pool's two most distinctive slots:
  slot A: the task sentence  ("Executed Louvain graph community clustering ...")
  slot B: the method phrase  ("Derived utilizing homomorphic encryption ...")
If job specs and delivery bodies draw slot values from the same set, and the
DIDs on the two sides are disjoint, then one generator is writing both the
demand and the supply side of this board."""
import json, re, sys, glob, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ALL = {}
for f in sorted(glob.glob("useful_on_thin_*.json")):
    try: d = json.load(open(f, encoding="utf-8"))
    except Exception: continue
    for m in d.get("messages", []):
        if m.get("seq") is not None: ALL[m["seq"]] = m
msgs = list(ALL.values())
def did(m): return m.get("did") or m.get("from") or ""
def txt(m): return (m.get("text") or "")

OPENER = re.compile(r"\b(Benchmark executed|Validation confirmed|Verification passed|"
                    r"Inspection cleared|Computation finalized|Analysis complete|"
                    r"Evaluation finished|Processing terminated successfully|Assessment concluded)\.")
METHOD = re.compile(r"\bDerived ([a-z][^.]{10,120})\.")
TASK   = re.compile(r"\b((?:Executed|Measured|Performed|Simulated|Applied|Mapped|Synthesized|"
                    r"Deconstructed|Analyzed|Computed|Traced) [^.]{15,140})\.")
STAMP  = re.compile(r"\[Proof(?:Hash)?:\s*[0-9a-f]{8}")

jobs    = [m for m in msgs if m.get("kind") == "job"]
results = [m for m in msgs if m.get("kind") == "result"]
attests = [m for m in msgs if m.get("kind") == "attest"]
chat    = [m for m in msgs if m.get("kind") == "chat"]
print("corpus: jobs %d results %d attests %d chat %d" % (len(jobs), len(results), len(attests), len(chat)))

def slots(group, rx):
    vals, dids, lines = collections.Counter(), collections.defaultdict(set), 0
    for m in group:
        hits = rx.findall(txt(m))
        if hits: lines += 1
        for h in hits:
            vals[h.strip()] += 1
            dids[h.strip()].add(did(m))
    return vals, dids, lines

for name, rx in (("OPENER", OPENER), ("METHOD (Derived ...)", METHOD), ("TASK sentence", TASK)):
    jv, jd, jl = slots(jobs, rx)
    rv, rd, rl = slots(results, rx)
    cv, cd, cl = slots(chat, rx)
    shared = set(jv) & set(rv)
    print("\n=== %s ===" % name)
    print("  distinct values: jobs %d (on %d job lines) | results %d (on %d result lines) | chat %d"
          % (len(jv), jl, len(rv), rl, len(cv)))
    print("  SHARED values job<->result: %d  (%.0f%% of the job-side vocabulary)"
          % (len(shared), 100.0*len(shared)/max(1,len(jv))))
    jdids = set().union(*[jd[s] for s in shared]) if shared else set()
    rdids = set().union(*[rd[s] for s in shared]) if shared else set()
    print("  DIDs using shared values: job side %d | result side %d | overlap %d"
          % (len(jdids), len(rdids), len(jdids & rdids)))
    for s in sorted(shared, key=lambda s: -(jv[s]+rv[s]))[:6]:
        print("     jobs=%-3d results=%-3d  %s" % (jv[s], rv[s], s[:120]))

js = [m for m in jobs if STAMP.search(txt(m))]
rs = [m for m in results if STAMP.search(txt(m))]
print("\n[Proof: 8hex] stamp: jobs %d/%d (%.1f%%) | results %d/%d (%.1f%%)"
      % (len(js), len(jobs), 100.0*len(js)/max(1,len(jobs)),
         len(rs), len(results), 100.0*len(rs)/max(1,len(results))))
print("stamp DIDs: job side %d | result side %d | overlap %d"
      % (len({did(m) for m in js}), len({did(m) for m in rs}),
         len({did(m) for m in js} & {did(m) for m in rs})))
