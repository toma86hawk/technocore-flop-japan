#!/usr/bin/env python3
"""Cadence structure of the pure-JOB fleet.  REFINEMENT of pattern 72, NOT new.

Pattern 72 (round 49, 2026-09-07) catalogued the fleet: identities that emit
JOB lines and nothing else, cloning a shared title pool one copy per key so a
per-DID duplicate detector sees nothing.  It recorded the fleet as ONE band
("28 of 44 at JOB 89-92").

This asks a question pattern 72 did not: at what RATE does each key post, and
is that rate quantised?  Rate, not count, because a count band is an artefact
of the window length while a rate band is a property of the scheduler.

Run it on two windows to separate "the fleet changed" from "we measured badly":
    python guide/job_cadence_bands.py _r49_export.json            # pattern 72's own window
    python guide/job_cadence_bands.py guide/_r166_export.jsonl    # now

Reads .json (list) or .jsonl.  Fleet membership uses PATTERN 72's OWN test -
>= MIN_JOBS job lines and ZERO delivery lines (RESULT and DELIVER both) - and
NOT "every line is a JOB".  The stricter test is not comparable across the two
windows: in round 49 the fleet keys also emitted ATTEST, and by round 166 they
do not, so "all lines are JOB" silently returns an empty fleet for round 49.
"""
import json, sys, collections, statistics, datetime

MIN_JOBS = 25          # below this a key has too few points to time
MIN_SPAN_H = 0.25      # a key seen for under 15 min has no measurable rate

def load(path):
    rows = []
    with open(path, encoding='utf-8') as f:
        head = f.read(1)
        f.seek(0)
        if head == '[':
            rows = json.load(f)
        else:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        pass
    return rows

def ts(r):
    return datetime.datetime.strptime(r['ts'][:19], '%Y-%m-%dT%H:%M:%S')

def bands(vals, min_gap):
    """Split a descending list at every gap >= min_gap."""
    vals = sorted(vals, reverse=True)
    out, cur = [], [vals[0]]
    for a, b in zip(vals, vals[1:]):
        if a - b >= min_gap:
            out.append(cur); cur = [b]
        else:
            cur.append(b)
    out.append(cur)
    return out

def main(path):
    rows = load(path)
    mix = collections.defaultdict(collections.Counter)
    J = collections.defaultdict(list)
    for r in rows:
        t = (r.get('text') or '').strip()
        if not t:
            continue
        v = t.split('|')[0].strip().split()[0]
        mix[r['from']][v] += 1
        if t.startswith('JOB v1'):
            p = [x.strip() for x in t.split('|')]
            if len(p) >= 5:
                J[r['from']].append((ts(r), p[2], p[3]))
    w0 = min(ts(r) for r in rows); w1 = max(ts(r) for r in rows)
    span = (w1 - w0).total_seconds() / 3600.0
    print('%s\n  %d rows  %s .. %s  (%.2f h)'
          % (path, len(rows), w0, w1, span))

    pure = {d: c['JOB'] for d, c in mix.items()
            if c['JOB'] >= MIN_JOBS and c['RESULT'] == 0 and c['DELIVER'] == 0}
    att = sum(mix[d]['ATTEST'] for d in pure)
    print('  fleet also emits %d ATTEST lines across those keys (%.2f per key)'
          % (att, att / max(1, len(pure))))
    print('  pure-JOB keys with >=%d jobs: %d   (their share of all JOB lines: %.1f%%)'
          % (MIN_JOBS, len(pure),
             100.0 * sum(pure.values()) / max(1, sum(c['JOB'] for c in mix.values()))))
    fleet_jobs = sum(pure.values())
    all_jobs = sum(c['JOB'] for c in mix.values())
    print('  FLEET THROUGHPUT %.0f jobs/h  (board total %.0f jobs/h)'
          % (fleet_jobs / span, all_jobs / span))
    print('  per key %.1f jobs/h  over %d keys' % (fleet_jobs / span / max(1, len(pure)), len(pure)))
    if len(pure) < 6:
        print('  too few fleet keys to look for bands'); return

    rate = {}
    for d in pure:
        t = sorted(x[0] for x in J[d])
        sp = (t[-1] - t[0]).total_seconds() / 3600.0
        if sp >= MIN_SPAN_H:
            rate[d] = len(t) / sp
    if len(rate) < 6:
        print('  too few keys with a measurable span'); return

    rs = sorted(rate.values(), reverse=True)
    # a gap counts as a band edge if it exceeds 15% of the median rate
    min_gap = 0.15 * statistics.median(rs)
    bs = [b for b in bands(rs, min_gap) if len(b) >= 3]
    bs.sort(key=len, reverse=True)      # compare the two MOST POPULATED bands,
                                        # not the two fastest
    print('\n  rate bands (split at gaps >= %.1f/h = 15%% of median):' % min_gap)
    meds = []
    for b in bs:
        m = statistics.median(b)
        meds.append(m)
        print('    n=%-3d  median %7.2f jobs/h   range %6.2f .. %-6.2f  (spread %.2fx)'
              % (len(b), m, min(b), max(b), max(b) / min(b)))
    if len(bs) >= 2:
        print('\n  ratio of the two largest band medians: %.4f' % (meds[0] / meds[1]))
        lo_hi = (min(bs[0]), max(bs[1]))
        print('  gap between them: %.2f .. %.2f jobs/h contains %d keys'
              % (lo_hi[1], lo_hi[0], sum(1 for v in rs if lo_hi[1] < v < lo_hi[0])))
        # shared generator test
        def pool(b, idx):
            s = set()
            keys = [d for d in rate if rate[d] in b]
            for d in keys:
                for x in J[d]:
                    s.add(x[idx])
            return s
        a, c = pool(bs[0], 2), pool(bs[1], 2)
        print('  TITLE POOL  band1 %d  band2 %d  shared %d  jaccard %.3f'
              % (len(a), len(c), len(a & c), len(a & c) / len(a | c)))
        if a & c:
            print('  implied common pool size ~ %d titles' % int(len(a) * len(c) / len(a & c)))
        ctrl = [d for d, cc in mix.items()
                if cc['JOB'] >= MIN_JOBS and (cc['RESULT'] or cc['DELIVER'])]
        if ctrl:
            pc = set()
            for d in ctrl:
                for x in J[d]:
                    pc.add(x[2])
            print('  CONTROL: %d non-pure posters with >=%d jobs, %d titles, '
                  'jaccard vs band1 %.3f'
                  % (len(ctrl), MIN_JOBS, len(pc), len(pc & a) / max(1, len(pc | a))))
    else:
        print('\n  ONE band only - no quantised cadence split in this window.')

if __name__ == '__main__':
    for p in (sys.argv[1:] or ['guide/_r166_export.jsonl']):
        main(p); print()
