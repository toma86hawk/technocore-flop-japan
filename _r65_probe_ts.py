#!/usr/bin/env python3
"""Round 65: did the official `probe v1` experiment lose its signal over time?

Round 64 (read 2026-09-08T21:22 JST) and round 65 (read 2026-09-09T00:18 JST)
each folded the public rooms. Rather than compare two POOLED rates over two
different retained-ring windows -- which would confound "answers went up" with
"old probes aged out" -- this merges both snapshots by probe id and buckets the
per-probe answered/not by the probe's OWN post time.
"""
import json, collections
from datetime import datetime, timezone

def load_r64():
    d = json.load(open('_r64_probe.json', encoding='utf-8'))
    # r64 file is meta-only; res maps id -> {arm, ts, n, uniq, hits}
    out = {}
    for pid, r in d['res'].items():
        out[pid] = dict(arm=r['arm'], ts=r['ts'],
                        answered=(r.get('uniq') or r.get('n') or 0) > 0,
                        room='meta', src='r64')
    return out

def load_r65():
    d = json.load(open('probe_fold.json', encoding='utf-8'))
    out = {}
    for blk in d:
        room = blk['room']
        tsmap = {p['id']: p['ts'] for p in blk['probes']}
        for pid, r in blk['res'].items():
            hits = r.get('hits') or []
            out[pid] = dict(arm=r['arm'], ts=tsmap.get(pid), room=room,
                            answered=len(hits) > 0, src='r65')
    return out

r64, r65 = load_r64(), load_r65()
both = set(r64) & set(r65)
print("probes: r64=%d  r65=%d  overlap=%d  new-in-r65=%d  aged-out=%d"
      % (len(r64), len(r65), len(both), len(set(r65)-set(r64)), len(set(r64)-set(r65))))

# 1. consistency check on the overlap: a closed 120s window must not change
flip = [p for p in both if r64[p]['answered'] != r65[p]['answered']]
print("overlap disagreements (should be ~0, window is long closed): %d %s"
      % (len(flip), sorted(flip)[:8]))

# 2. merge, preferring r65 (fresher read of the same closed window)
merged = dict(r64); merged.update(r65)
rows = [dict(id=p, **v) for p, v in merged.items() if v.get('ts')]
for r in rows:
    r['dt'] = datetime.fromisoformat(r['ts'].replace('Z', '+00:00'))
rows.sort(key=lambda r: r['dt'])
print("merged probes: %d  span %s .. %s"
      % (len(rows), rows[0]['ts'][:19], rows[-1]['ts'][:19]))

# 3. hourly answer rate per arm, on the merged set
print("\nanswer rate per arm by probe post-hour (UTC), merged snapshots")
print("%-14s %5s  %-13s %-13s %-13s %-13s" % ("hour", "n", "null", "ask", "offer", "addressed"))
by_h = collections.defaultdict(lambda: collections.defaultdict(list))
for r in rows:
    by_h[r['dt'].strftime('%m-%d %HZ')][r['arm']].append(r['answered'])
for h in sorted(by_h):
    cells = []
    for a in ('null', 'ask', 'offer', 'addressed'):
        v = by_h[h][a]
        cells.append("%2d/%-2d %5.1f%%" % (sum(v), len(v), 100.0*sum(v)/len(v)) if v else "     -       ")
    print("%-14s %5d  %s %s %s %s" % (h, sum(len(x) for x in by_h[h].values()), *cells))

# 4. the headline the experiment reports: ask - null gap, over time
print("\nask-minus-null gap by hour (the effect the experiment is built to detect)")
for h in sorted(by_h):
    n, a = by_h[h]['null'], by_h[h]['ask']
    if n and a:
        rn, ra = 100.0*sum(n)/len(n), 100.0*sum(a)/len(a)
        print("  %s  null %5.1f%% (n=%d)   ask %5.1f%% (n=%d)   gap %+6.1fpt"
              % (h, rn, len(n), ra, len(a), ra-rn))
json.dump(rows, open('_r65_probe_ts.json','w'), default=str, indent=1)
