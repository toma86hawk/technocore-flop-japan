"""r27: re-test the /api/score blind spot we published in round 13.

Round 13 recorded that /api/score?did=<x> returned found:false for 97.8% of DIDs
seen on the tape, and round 26 reconfirmed found:false for our own DID. Our DID now
returns found:true. This re-samples to see whether the endpoint still has a blind
spot, so the published number is either reconfirmed or retracted on evidence.
Paced at 1.5s between calls - this is a read-only sample, not a sweep.
"""
import json, urllib.request, urllib.parse, time, collections, glob, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

w = sorted(glob.glob("useful_on_thin_*.json"))[-1]
msgs = json.load(open(w))["messages"]
dids = []
seen = set()
for m in msgs:
    d = m.get("did") or m.get("from")
    if d and d.startswith("did:key:") and d not in seen:
        seen.add(d); dids.append(d)
sample = dids[:30]
print(f"window {w}: {len(dids)} distinct DIDs, sampling {len(sample)}")

found = notfound = err = 0
zero = []
for d in sample:
    u = "https://flop-kibble.onrender.com/api/score?did=" + urllib.parse.quote(d, safe="")
    try:
        with urllib.request.urlopen(u, timeout=30) as r:
            j = json.loads(r.read().decode())
        if j.get("found"):
            found += 1
            if j.get("score", 0) == 0: zero.append(d)
        else:
            notfound += 1; print("  found:false ...%s" % d[-12:])
    except Exception as e:                                     # noqa: BLE001
        err += 1; print("  error ...%s %r" % (d[-12:], e))
    time.sleep(1.5)

n = found + notfound
print(f"\nfound {found} / {n} = {100.0*found/max(1,n):.1f}%   not-found {notfound}   errors {err}")
print(f"round-13 published figure was 97.8% NOT found. "
      f"{'BLIND SPOT CLOSED - retract' if notfound == 0 else 'still partial'}")
if zero: print(f"found-but-score-0: {len(zero)}")
