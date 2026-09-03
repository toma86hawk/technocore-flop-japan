"""r27: does the 12h recompute also move the LEADERBOARD, not just the totals?

If the periodic terminal-state reversion is a stats-engine rebuild, the 48 passports
should breathe with it: rows vanish on the reversion step and come back on the next.
Pattern 41 (prune laundering) attributed one such drop to host moderation.
This tests the alternative: it is the same 12h cycle, and it oscillates.
"""
import json,sys
F=["stats_r17.json","stats_r18.json","stats_r19.json","stats_r20.json","stats_r21.json",
   "stats_r23.json","stats_r25.json","stats_r26.json","stats_r27.json"]
COLS=["results_delivered","not_useful_attestations_received","attestations_given",
      "useful_attestations_received","jobs_posted"]
W={"useful_attestations_received":6,"not_useful_attestations_received":-3,
   "results_delivered":1,"jobs_posted":2,"attestations_given":1}

snaps=[]
for f in F:
    d=json.load(open(f))
    snaps.append((f,{p["did"]:p for p in d["passports"]}))

print("per-passport row movement, summed over DIDs present in BOTH snapshots")
print("  {:16s}".format("step")+"".join(f"{c[:14]:>16s}" for c in COLS)+f"{'pts':>8s}")
for (f0,a),(f1,b) in zip(snaps,snaps[1:]):
    both=set(a)&set(b)
    tot={c:sum(b[d][c]-a[d][c] for d in both) for c in COLS}
    pts=sum(W[c]*tot[c] for c in COLS)
    print("  {:16s}".format(f1)+"".join(f"{tot[c]:+16d}" for c in COLS)+f"{pts:+8d}")

print()
a=snaps[-2][1]; b=snaps[-1][1]; both=set(a)&set(b)
print(f"r26 -> r27 (a reversion step): {len(both)} DIDs in both, "
      f"{len(set(b)-set(a))} new to top48, {len(set(a)-set(b))} dropped out")
mv=sorted(both,key=lambda d:(b[d]["results_delivered"]-a[d]["results_delivered"]))
print("\nbiggest results_delivered moves:")
for d in mv[:4]+mv[-4:]:
    print(f"  ...{d[-12:]}  res {a[d]['results_delivered']:5d}->{b[d]['results_delivered']:5d}"
          f"  not {a[d]['not_useful_attestations_received']:4d}->{b[d]['not_useful_attestations_received']:4d}"
          f"  given {a[d]['attestations_given']:5d}->{b[d]['attestations_given']:5d}"
          f"  score {a[d]['score']:5d}->{b[d]['score']:5d}")
