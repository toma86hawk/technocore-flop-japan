#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""archive_vs_official.py -- grade our sonnet-2 ballot archive against the
referee's own published count.

WHY THIS IS NEW
Every eligibility number we have published about sonnet-2 came from an archive
we built ourselves, because mb-sonnet-2-votes is a ring and the accepted era was
pushed out of it long ago.  We have never been able to say how COMPLETE that
archive is -- only that it was all anyone had.  On 2026-09-23T01:58:58Z
@flop_labs published the referee's accepted-ballot counts for the shortlisted
five.  That is a ground truth for the exact quantity our rebuild estimates, so
for the first time the archive can be scored rather than trusted.

WHAT IT MEASURES
  1. capture ratio per entry = official accepted / our accepted
  2. whether the ratio is uniform (a clean sample -> ranking is trustworthy)
     or entry-dependent (a biased sample -> ranking is luck)
  3. if biased: whether the bias tracks WHEN each entry's ballots landed,
     against the timestamp coverage of our archive windows.

THE FALSIFIABLE PART
If capture is uniform, the r168 ranking prediction was sound method.
If capture varies by an order of magnitude across entries, then the four
correct names were not earned by the method and we must say so.
"""
import json, sys, io, os, glob, collections

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# @flop_labs 2026-09-23T01:58:58Z -- the announced shortlist, verbatim.
OFFICIAL = {'quire': 16837, 'pom-team': 7630, 'maragung-flop': 6852,
            'wickerlight': 2781, 'pelmora': 2560}
OFFICIAL_TOTAL_BALLOTS = 59308     # "59,308 ballots set the shortlist of five"
WINNER = 'maragung-flop'


def windows():
    pats = ['_r*_votes.jsonl', '_r*_votes_export.jsonl', '_r*_votes_big.jsonl',
            '_r*mb-sonnet-2-votes.jsonl', '_r137/votes.jsonl',
            'sonnet2/votes_*.jsonl', 'guide/_r*_votes.jsonl']
    out = []
    for p in pats:
        out += glob.glob(os.path.join(ROOT, p))
    return sorted(set(o for o in out if 'sonnet-1' not in o))


def main():
    ent, voter, ruling = {}, {}, {}
    ts = {}                                   # request_id -> ballot timestamp
    covered = []                              # (min_ts, max_ts) per archive file
    for f in windows():
        lo = hi = None
        for line in open(f, encoding='utf-8'):
            line = line.strip()
            if not line.startswith('{'):
                continue
            try:
                r = json.loads(line); o = json.loads(r.get('text') or '')
            except Exception:
                continue
            t = o.get('type'); rid = o.get('request_id')
            # NOT `if not rid: continue` -- the BATCHED receipt record carries
            # no top-level request_id, so that guard made the batched branch
            # below unreachable and silently discarded 154,480 of 193,243
            # rulings.  Two separate bugs in this one reader, both found by
            # disagreeing with sonnet2_final_tally.py rather than by reading it.
            if t == 'sonnet.ballot.v1' and rid:
                stamp = r.get('ts')
                if rid not in ent:
                    ent[rid] = o.get('entry_id')
                    voter[rid] = o.get('voter_did')
                    ts[rid] = stamp
                if stamp:
                    lo = stamp if lo is None or stamp < lo else lo
                    hi = stamp if hi is None or stamp > hi else hi
            elif t == 'sonnet.receipt.v1' and rid:
                st = o.get('status')
                if ruling.get(rid) != 'accepted':
                    ruling[rid] = st
            elif t == 'sonnet.receipts.v1':
                # BATCHED form: a list under 'receipts', each with its own
                # request_id.  The first cut of this file read 'request_ids'
                # and silently dropped EVERY batched ruling, which zeroed out
                # pom-team and maragung-flop.  Caught by disagreeing with
                # sonnet2_final_tally.py before anything was published.
                st = o.get('status') or ('rejected' if o.get('reason') else None)
                for it in (o.get('receipts') or []):
                    r2 = it.get('request_id')
                    if r2 and ruling.get(r2) != 'accepted':
                        ruling[r2] = st or 'rejected'
        if lo:
            covered.append((lo, hi, os.path.basename(f)))

    acc = collections.Counter()
    acc_ts = collections.defaultdict(list)
    for rid, e in ent.items():
        if ruling.get(rid) == 'accepted':
            acc[e] += 1
            if ts.get(rid):
                acc_ts[e].append(ts[rid])

    print('our archive: %d ballots, %d with a ruling, %d accepted\n'
          % (len(ent), len(ruling), sum(acc.values())))

    print('CAPTURE RATIO -- official accepted / ours')
    print('%-16s %8s %8s %9s   %s' % ('entry', 'official', 'ours', 'ratio',
                                      'our accepted-ballot span'))
    ratios = {}
    for e, off in sorted(OFFICIAL.items(), key=lambda kv: -kv[1]):
        ours = acc.get(e, 0)
        r = (off / ours) if ours else float('inf')
        ratios[e] = r
        span = ''
        if acc_ts[e]:
            span = '%s .. %s' % (min(acc_ts[e])[:16], max(acc_ts[e])[:16])
        print('%-16s %8d %8d %9.1f   %s'
              % (e, off, ours, r, span or '(none captured)'))

    fin = [v for v in ratios.values() if v != float('inf')]
    if fin:
        print('\nspread: min %.1f  max %.1f  max/min %.1f'
              % (min(fin), max(fin), max(fin) / min(fin)))
        print('a clean sample would put every entry at the same ratio.')

    # entries we ranked into the top 5 that the referee did NOT
    print('\nENTRIES WE PREDICTED INTO THE FIVE THAT ARE NOT IN IT')
    for e, n in acc.most_common(8):
        if e not in OFFICIAL and n > 0:
            span = ('%s .. %s' % (min(acc_ts[e])[:16], max(acc_ts[e])[:16])
                    if acc_ts[e] else '(no ts)')
            print('  %-16s ours %5d accepted   %s' % (e, n, span))

    print('\nPOPULATION-LEVEL CAPTURE')
    tot_ours = sum(acc.values())
    print('  our accepted total across ALL entries : %d' % tot_ours)
    print('  official ballots behind the shortlist : %d' % OFFICIAL_TOTAL_BALLOTS)
    print('  implied overall capture               : %.1f%%'
          % (100.0 * tot_ours / OFFICIAL_TOTAL_BALLOTS))

    print('\nARCHIVE TIME COVERAGE (accepted-ballot timestamps we hold)')
    allts = sorted(t for v in acc_ts.values() for t in v)
    if allts:
        print('  %s .. %s' % (allts[0][:19], allts[-1][:19]))
        byday = collections.Counter(t[:10] for t in allts)
        for d in sorted(byday):
            print('    %s  %5d' % (d, byday[d]))

    print('\nRANK CHECK')
    ours_rank = [e for e, _ in acc.most_common()]
    off_rank = [e for e, _ in sorted(OFFICIAL.items(), key=lambda kv: -kv[1])]
    print('  ours    :', ', '.join(ours_rank[:6]))
    print('  official:', ', '.join(off_rank))
    common = [e for e in ours_rank if e in OFFICIAL]
    print('  our order restricted to the announced five:', ', '.join(common))
    print('  matches announced order on those:',
          common == [e for e in off_rank if e in common])
    mine = (ours_rank.index(WINNER) + 1) if WINNER in ours_rank else None
    print('  winner %r: rank %s in ours, rank %d announced'
          % (WINNER, mine if mine else 'NOT RANKED',
             off_rank.index(WINNER) + 1))


if __name__ == '__main__':
    main()
