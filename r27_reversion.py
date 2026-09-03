"""r27: does the kibble job-state partition ever move BACKWARDS?

/api/stats exposes a partition: jobs == open + claimed + delivered + attested + rejected.
A job is only supposed to move forward (open -> claimed -> delivered -> attested/rejected).
So delivered/attested/rejected must be monotonically non-decreasing.
This walks every snapshot we hold and prints the deltas.
"""
import json, glob, os, sys

FILES = ["stats_r17.json","stats_r18.json","stats_r19.json","stats_r20.json",
         "stats_r21.json","stats_r23.json","stats_r25.json","stats_r26.json",
         "stats_r27.json"]
KEYS = ["jobs","open","claimed","delivered","attested","rejected"]

rows=[]
for f in FILES:
    if not os.path.exists(f): continue
    s=json.load(open(f))["stats"]
    rows.append((f,{k:s.get(k,0) for k in KEYS}))

print("partition identity check (jobs == open+claimed+delivered+attested+rejected):")
for f,s in rows:
    tot=s["open"]+s["claimed"]+s["delivered"]+s["attested"]+s["rejected"]
    print(f"  {f:16s} jobs={s['jobs']:6d} sum={tot:6d} {'OK' if tot==s['jobs'] else 'MISMATCH'}")

print()
print("step deltas (terminal states should never be negative):")
hdr="  {:16s}".format("step")+"".join(f"{k:>10s}" for k in KEYS)
print(hdr)
for (f0,a),(f1,b) in zip(rows,rows[1:]):
    d={k:b[k]-a[k] for k in KEYS}
    flag=" <== REVERSION" if (d["delivered"]<0 or d["attested"]<0 or d["rejected"]<0) else ""
    print("  {:16s}".format(f1)+"".join(f"{d[k]:+10d}" for k in KEYS)+flag)

print()
last=rows[-1][1]; prev=rows[-2][1]
d={k:last[k]-prev[k] for k in KEYS}
left = -(min(0,d["delivered"])+min(0,d["attested"])+min(0,d["rejected"]))
print(f"latest step: {left} jobs left terminal states;"
      f" open {d['open']:+d} while jobs only {d['jobs']:+d}")
print(f"  => at least {d['open']-d['jobs']} previously-non-open jobs are open again"
      f" (open grew {d['open']-d['jobs']} more than the whole board did)")
