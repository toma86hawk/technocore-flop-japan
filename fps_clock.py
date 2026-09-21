"""What clock does the host's agent fingerprint pass advance on?

r84 opened the watch (agent_fps_n pinned at 3719 while agents climbed);
r156 recorded it as RESOLVED because the number started moving again.
It was never EXPLAINED.  The pass has now been running for ~30 h with
enough snapshots to ask which quantity it is proportional to.

Candidates, each measured as a RATE per interval; the winning clock is the
one whose per-interval rate is most nearly CONSTANT (lowest coefficient of
variation).  A clock that only looks good because one interval is 13 min
long is not a clock, so intervals under 30 min are dropped.

Window starts at the RESUMPTION (first snapshot with tape_head_seq off the
9100924 pin), not at the first snapshot on disk -- a window that spans the
stall would report the stall, not the running pass.
"""
import json, io, glob, os, datetime, statistics

PIN = 9100924
MIN_DT_H = 0.5

def rows():
    out = []
    for f in set(glob.glob('_r*_stats*.json') + glob.glob('api_stats_*.json')
                 + glob.glob('agent/stats_*.json')):
        try:
            d = json.load(io.open(f, encoding='utf-8'))
        except Exception:
            continue
        o = d.get('origin') or {}
        s = d.get('stats') or {}
        if o.get('agent_fps_n') is None or o.get('tape_head_seq') is None:
            continue
        out.append(dict(t=os.path.getmtime(f), f=os.path.basename(f),
                        fps=o['agent_fps_n'], head=o['tape_head_seq'],
                        parsed=s.get('parsed'), jobs=s.get('jobs'),
                        uniq=o.get('unique_agents')))
    out.sort(key=lambda r: r['t'])
    # de-duplicate identical (fps, head) readings taken minutes apart
    ded = []
    for r in out:
        if ded and ded[-1]['fps'] == r['fps'] and ded[-1]['head'] == r['head']:
            continue
        ded.append(r)
    return ded

def main():
    rs = rows()
    live = [r for r in rs if r['head'] != PIN]
    if len(live) < 3:
        print('not enough post-resumption snapshots'); return
    start = live[0]
    print('resumption window starts %s (head %d off the %d pin)'
          % (datetime.datetime.utcfromtimestamp(start['t']).strftime('%m-%d %H:%MZ'),
             start['head'], PIN))
    print('%d snapshots, fps %d -> %d\n' % (len(live), live[0]['fps'], live[-1]['fps']))

    cands = {'wall hours': lambda a, b: (b['t'] - a['t']) / 3600.0,
             'tape rows (head)': lambda a, b: (b['head'] - a['head']) / 1000.0,
             'parsed rows': lambda a, b: ((b['parsed'] or 0) - (a['parsed'] or 0)) / 1000.0,
             'jobs': lambda a, b: ((b['jobs'] or 0) - (a['jobs'] or 0)) / 1.0}

    print('%-18s %5s %8s %8s %8s %6s' % ('clock', 'n', 'mean', 'sd', 'min..max', 'CV'))
    best = None
    for name, denom in cands.items():
        rates = []
        for a, b in zip(live, live[1:]):
            dt_h = (b['t'] - a['t']) / 3600.0
            if dt_h < MIN_DT_H:
                continue
            d = denom(a, b)
            if d <= 0:
                continue
            rates.append((b['fps'] - a['fps']) / d)
        if len(rates) < 3:
            print('%-18s %5d  (too few usable intervals)' % (name, len(rates)))
            continue
        m = statistics.mean(rates); sd = statistics.stdev(rates)
        cv = sd / m if m else float('inf')
        print('%-18s %5d %8.3f %8.3f %6.2f..%-6.2f %6.2f'
              % (name, len(rates), m, sd, min(rates), max(rates), cv))
        if best is None or cv < best[1]:
            best = (name, cv)

    print()
    if best and best[1] < 0.25:
        print('VERDICT: the pass tracks %s (CV %.2f).' % (best[0], best[1]))
    else:
        print('VERDICT: NO clock fits. Best is %s at CV %.2f, which is not a '
              'constant rate.\n  The pass advances in bursts; it is not '
              'proportional to wall time, tape rows, parsed rows or jobs.'
              % (best[0], best[1]))
    print('\nper-interval detail (dropped intervals shorter than %.0f min):' % (MIN_DT_H * 60))
    print('%-14s %-14s %6s %6s %9s %9s %9s'
          % ('from', 'to', 'dfps', 'dt_h', 'fps/h', 'dhead', 'fps/krow'))
    for a, b in zip(live, live[1:]):
        dt = (b['t'] - a['t']) / 3600.0
        if dt < MIN_DT_H:
            continue
        dh = b['head'] - a['head']
        print('%-14s %-14s %6d %6.2f %9.2f %9d %9.3f'
              % (datetime.datetime.utcfromtimestamp(a['t']).strftime('%m-%d %H:%MZ'),
                 datetime.datetime.utcfromtimestamp(b['t']).strftime('%m-%d %H:%MZ'),
                 b['fps'] - a['fps'], dt, (b['fps'] - a['fps']) / dt, dh,
                 (b['fps'] - a['fps']) / (dh / 1000.0) if dh else 0))

if __name__ == '__main__':
    main()
