#!/usr/bin/env python3
"""Same time series, but held to ONE room, so a changing room mix cannot explain it.
Round 64 showed the null-control leak differs per room (meta 8.3% / technocore 25.0% /
kibble 44.4%), so pooling rooms across hours would confound saturation with room mix."""
import json, collections
from datetime import datetime
rows = json.load(open('_r65_probe_ts.json', encoding='utf-8'))
for r in rows:
    r['dt'] = datetime.fromisoformat(r['ts'].replace('Z', '+00:00'))

print("room x hour coverage (n probes)")
grid = collections.Counter((r['dt'].strftime('%HZ'), r['room']) for r in rows)
hours = sorted({h for h, _ in grid}); rooms = sorted({rm for _, rm in grid})
print("%-6s %s" % ("hour", " ".join("%-11s" % rm for rm in rooms)))
for h in hours:
    print("%-6s %s" % (h, " ".join("%-11d" % grid[(h, rm)] for rm in rooms)))

for room in rooms:
    sub = [r for r in rows if r['room'] == room]
    if len(sub) < 15:
        print("\n=== /r/%s : %d probes, too few for an hourly cut ===" % (room, len(sub)))
        continue
    print("\n=== /r/%s only (%d probes) ===" % (room, len(sub)))
    print("%-6s %5s  %-13s %-13s %-13s %-13s %s" % ("hour","n","null","ask","offer","addressed","ask-null"))
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in sub:
        by[r['dt'].strftime('%HZ')][r['arm']].append(r['answered'])
    for h in sorted(by):
        cells, rates = [], {}
        for a in ('null','ask','offer','addressed'):
            v = by[h][a]
            if v:
                rates[a] = 100.0*sum(v)/len(v)
                cells.append("%2d/%-2d %5.1f%%" % (sum(v), len(v), rates[a]))
            else:
                cells.append("     -       ")
        gap = ("%+6.1fpt" % (rates['ask']-rates['null'])) if 'ask' in rates and 'null' in rates else "   -"
        print("%-6s %5d  %s %s %s %s %s"
              % (h, sum(len(x) for x in by[h].values()), *cells, gap))
