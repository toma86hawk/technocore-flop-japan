#!/usr/bin/env python3
"""When exactly did the null control stop being silent, and who made it stop?"""
import json, collections
from datetime import datetime
fold = json.load(open('probe_fold.json', encoding='utf-8'))
r64  = json.load(open('_r64_probe.json', encoding='utf-8'))

# per-probe records with responder identities where we have them (r65 fold keeps hits)
rec = {}
for pid, r in r64['res'].items():
    rec[pid] = dict(id=pid, room='meta', arm=r['arm'], ts=r['ts'],
                    responders=[h.get('from') for h in (r.get('hits') or [])])
for blk in fold:
    tsmap = {p['id']: p['ts'] for p in blk['probes']}
    for pid, r in blk['res'].items():
        rec[pid] = dict(id=pid, room=blk['room'], arm=r['arm'], ts=tsmap.get(pid),
                        responders=[h.get('from') for h in (r.get('hits') or [])])
rows = [r for r in rec.values() if r['ts']]
for r in rows:
    r['dt'] = datetime.fromisoformat(r['ts'].replace('Z','+00:00'))
rows.sort(key=lambda r: r['dt'])

print("=== /r/meta null-control probes in post order (the arm that must stay silent) ===")
nulls = [r for r in rows if r['arm']=='null' and r['room']=='meta']
run = 0
for r in nulls:
    n = len(r['responders'])
    mark = "SILENT" if n==0 else "ANSWERED x%d" % n
    print("  %s  %-16s %s" % (r['ts'][11:19], r['id'], mark))
print("  -> %d null probes; last silent one and first answered one bracket the break" % len(nulls))
sil = [r for r in nulls if not r['responders']]
ans = [r for r in nulls if r['responders']]
if sil and ans:
    print("  last SILENT   : %s  %s" % (sil[-1]['ts'][11:19], sil[-1]['id']))
    print("  first ANSWERED: %s  %s" % (ans[0]['ts'][11:19], ans[0]['id']))
    print("  control died inside a %.0f-minute bracket"
          % ((ans[0]['dt']-sil[-1]['dt']).total_seconds()/60))

print("\n=== distinct responders per hour (all rooms) and cumulative new keys ===")
seen=set(); byh=collections.defaultdict(set)
for r in rows: byh[r['dt'].strftime('%HZ')].update(x for x in r['responders'] if x)
print("%-6s %-10s %-10s %s" % ("hour","distinct","new","cumulative"))
for h in sorted(byh):
    new = byh[h]-seen; seen |= byh[h]
    print("%-6s %-10d %-10d %d" % (h, len(byh[h]), len(new), len(seen)))

print("\n=== who answers the null control (meta), by key ===")
c=collections.Counter()
for r in nulls: c.update(set(x for x in r['responders'] if x))
for did,n in c.most_common(12):
    print("  %-58s %2d/%d null probes" % (did[:58], n, len(nulls)))
