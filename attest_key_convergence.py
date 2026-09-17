"""Do two attestor keys judging the SAME job converge on the same words?

Found 2026-09-18 round 139, while reporting that the round-133 skeleton-delta
falsifier had fired.  One job (k8146ba0218) drew 26 unanimous `not` verdicts
from 14 distinct keys inside 24 minutes, and all 14 wrote a paraphrase of one
sentence frame with per-key synonym substitution.  Two readings:

  (A) a bloc sharing a generator, or
  (B) one base model, one job, one obviously bad delivery -> one set of words.

THIS TOOL DOES NOT SEPARATE THEM, and that is why it is published.  A measured
non-separation is worth more than a pattern claim the data does not carry.

THE CONTROL THAT DOES NOT WORK.  Compare within-job reason pairs against
RANDOM CROSS-JOB pairs.  It fails: refusal mills emit one constant string over
hundreds of jobs, so random cross-job draws keep landing two copies of the same
boilerplate, the control's p99 is 1.000, and no treatment value can exceed it.
Recorded here so nobody rebuilds it.

THE CONTROL THAT PARTLY WORKS.  Hold the KEY PAIR fixed and vary the job:

  treatment  J(key A on job X, key B on job X)   both judging the same job
  control    J(key A on job X, key B on job Y)   same two keys, different jobs

A constant-string key now scores the same in both arms, so boilerplate cancels
instead of poisoning the control.  J is trigram Jaccard over the reason text.

MEASURED, kibble export seq 8077974-8093188 (15,215 msgs, 33.2 min):
  same job, two keys        n=349  median 0.091  mean 0.264  p99 1.000
  same two keys, diff jobs  n=304  median 0.000  mean 0.191  p99 1.000
  k8146ba0218               n= 91  median 0.151

So a real job-driven wording effect exists at the median, it is SMALL, and
k8146ba0218 is elevated without being an outlier.  Both arms saturate at
p99 1.000 because Jaccard maxes out on constant-string keys, so no threshold
test exists at this window size.  No bloc is claimed.

The finding that does survive: cross-key wording agreement is ordinary here.
Distinct reason strings from distinct keys are NOT evidence of distinct
judgement, and a detector keyed on shared EXACT strings (evasion pattern 59)
is blind in precisely that gap - 6 strings in this whole window are used
verbatim by more than one key.

Usage:  python guide/attest_key_convergence.py <kibble-export.jsonl>
"""

import json, sys, re, itertools, random, zlib
from collections import defaultdict
sys.path.insert(0,'guide')
from attest_skeleton_census import load, RXA, RX_RH

FOCUS = sys.argv[2] if len(sys.argv)>2 else 'k8146ba0218'
msgs = load(sys.argv[1] if len(sys.argv)>1 else '_r139_kib.jsonl')
by = defaultdict(dict)
for m in msgs:
    t=(m.get("text") or "").strip()
    if (a:=RXA.match(t)):
        by[a.group(1)].setdefault(m["from"], RX_RH.sub("",a.group(3).strip()))
def tri(s):
    w=re.findall(r"[a-z]+", s.lower()); return set(zip(w,w[1:],w[2:]))
def jac(a,b):
    A,B=tri(a),tri(b); return len(A&B)/len(A|B) if A|B else 0.0

keyjobs=defaultdict(dict)
for j,km in by.items():
    for k,r in km.items(): keyjobs[k][j]=r

treat, ctrl = [], []
for j,km in by.items():
    if len(km)<2: continue
    for k1,k2 in itertools.combinations(sorted(km),2):
        treat.append((jac(km[k1],km[k2]), j, k1, k2))
        o1=[x for x in keyjobs[k1] if x!=j]; o2=[x for x in keyjobs[k2] if x!=j]
        if o1 and o2:
            # NOT hash(): Python salts str hashing per process (PYTHONHASHSEED),
            # so seeding from it made the control arm drift run to run
            # (mean 0.188 vs 0.192 on two runs of the same file). crc32 is stable.
            random.seed(zlib.crc32((j+'|'+k1+'|'+k2).encode()))
            ctrl.append(jac(keyjobs[k1][random.choice(o1)], keyjobs[k2][random.choice(o2)]))
def stat(xs,name):
    xs=sorted(xs); n=len(xs)
    print(f"{name:26s} n={n:5d} median {xs[n//2]:.3f}  mean {sum(xs)/n:.3f}  p90 {xs[int(.9*n)]:.3f}  p99 {xs[int(.99*n)]:.3f}")
    return xs
t=stat([x[0] for x in treat], "SAME job, 2 keys")
c=stat(ctrl, "SAME 2 keys, diff jobs")
p99=c[int(.99*len(c))]
hi=[x for x in treat if x[0]>p99]
print(f"\nsame-job pairs above the key-matched p99 ({p99:.3f}): {len(hi)} / {len(treat)} = {100*len(hi)/len(treat):.1f}%")
from collections import Counter
print("jobs carrying them:", Counter(x[1] for x in hi).most_common(8))
tg=[x for x in treat if x[1]==FOCUS]
tgs=sorted(x[0] for x in tg)
print(f"\nk8146ba0218: {len(tg)} key-pairs  median {tgs[len(tgs)//2]:.3f}  mean {sum(tgs)/len(tgs):.3f}"
      f"  above p99: {sum(1 for x in tgs if x>p99)}")
