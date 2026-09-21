#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sonnet2_final_tally.py -- the ELIGIBLE sonnet-2 tally, rebuilt from every
window we archived, as a pre-registered prediction of the announced result.

WHY IT HAS TO BE REBUILT FROM ARCHIVES
mb-sonnet-2-votes is a ring of ~12,000 rows.  Round 101 measured that 98% of
the accepted-ballot receipts readable in the room already name a ballot the
room no longer holds, and the flood pushed the accepted era out entirely.  The
contest rules promise the award arithmetic is publicly checkable; in practice
it is checkable only by someone who archived the tape while it was there.  We
did, in 23+ pinned windows, so this rebuilds the tally from those.

METHOD (identical to round 122's referee-verdict join, which cross-checked
sender_did against voter_did on 1,034 joined rows with zero mismatches)
  1. ballots  : sonnet.ballot.v1 gives (request_id -> entry_id, voter_did)
  2. receipts : sonnet.receipt.v1 gives (request_id -> status, reason);
                sonnet.receipts.v1 is the batched form, one status for a list
  3. dedupe   : a request_id can be ruled on more than once across windows
                (the referee replays rejections hourly - round 145).  Keep one
                ruling per request_id; ACCEPT wins over a later rejection so a
                replay cannot delete an accept.
  4. tally    : accepted ballots per entry, and DISTINCT accepted voters per
                entry, which is the number that matters because the voter
                prize pool is split among voters, not ballots.

THE CONTROL THAT MAKES THIS WORTH PUBLISHING
The RAW tally and the ELIGIBLE tally name different winners.  Print both.  If
the announced winner matches the raw leader instead, the eligible reading is
wrong and this file says so before the answer is known.

Usage: python guide/sonnet2_final_tally.py [extra_export.jsonl ...]
"""
import json, sys, io, os, glob, collections

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def windows(extra):
    pats = ['_r*_votes.jsonl', '_r*_votes_export.jsonl', '_r*_votes_big.jsonl',
            '_r*mb-sonnet-2-votes.jsonl', '_r137/votes.jsonl',
            'sonnet2/votes_*.jsonl', 'guide/_r*_votes.jsonl']
    out = []
    for p in pats:
        out += glob.glob(os.path.join(ROOT, p))
    out += [os.path.abspath(e) for e in extra]
    # sonnet-1 files must not be mixed in
    return sorted(set(o for o in out if 'sonnet-1' not in o))


def main(extra):
    ent = {}                      # request_id -> entry_id
    voter = {}                    # request_id -> voter_did
    ruling = {}                   # request_id -> (status, reason)
    raw = collections.Counter()   # entry -> ballots seen, eligible or not
    rawvoters = collections.defaultdict(set)
    files = windows(extra)
    for f in files:
        n = 0
        for line in open(f, encoding='utf-8'):
            line = line.strip()
            if not line.startswith('{'):
                continue
            try:
                r = json.loads(line); o = json.loads(r.get('text') or '')
            except Exception:
                continue
            t = o.get('type')
            if t == 'sonnet.ballot.v1' and o.get('request_id'):
                rid = o['request_id']
                if rid not in ent:
                    ent[rid] = o.get('entry_id'); voter[rid] = o.get('voter_did')
                    raw[o.get('entry_id')] += 1
                    rawvoters[o.get('entry_id')].add(o.get('voter_did'))
                n += 1
            elif t == 'sonnet.receipt.v1' and o.get('request_id'):
                st = o.get('status'); rid = o['request_id']
                if ruling.get(rid, ('', ''))[0] != 'accepted':
                    ruling[rid] = (st, o.get('reason') or '')
                n += 1
            elif t == 'sonnet.receipts.v1':
                st = o.get('status') or ('rejected' if o.get('reason') else None)
                for it in o.get('receipts') or []:
                    rid = it.get('request_id')
                    if rid and ruling.get(rid, ('', ''))[0] != 'accepted':
                        ruling[rid] = (st or 'rejected', o.get('reason') or '')
                    n += 1
        print('  %-52s %7d records' % (os.path.relpath(f, ROOT), n))

    acc = collections.Counter(); accv = collections.defaultdict(set)
    rej = collections.Counter(); reasons = collections.Counter()
    joined = unjoined = 0
    for rid, (st, why) in ruling.items():
        e = ent.get(rid)
        if e is None:
            unjoined += 1
            continue
        joined += 1
        if st == 'accepted':
            acc[e] += 1; accv[e].add(voter.get(rid))
        else:
            rej[e] += 1; reasons[why] += 1

    print('\n%d distinct ballots, %d distinct rulings, %d joined, %d rulings name a '
          'ballot we never captured' % (len(ent), len(ruling), joined, unjoined))
    print('\nELIGIBLE (referee-accepted) tally')
    print('%-16s %9s %9s %9s' % ('entry', 'accepted', 'voters', 'rejected'))
    for e, c in acc.most_common(12):
        print('%-16s %9d %9d %9d' % (e, c, len(accv[e]), rej[e]))
    print('\nRAW tally (what an unfiltered count of the room says)')
    for e, c in raw.most_common(8):
        print('%-16s %9d ballots %7d keys   accepted %d' % (e, c, len(rawvoters[e]), acc[e]))
    print('\ntop rejection reasons')
    for w, c in reasons.most_common(6):
        print('%9d  %s' % (c, w[:70]))
    json.dump({'accepted': dict(acc), 'voters': {k: len(v) for k, v in accv.items()},
               'rejected': dict(rej), 'raw': dict(raw),
               'raw_keys': {k: len(v) for k, v in rawvoters.items()},
               'ballots': len(ent), 'rulings': len(ruling), 'joined': joined,
               'files': [os.path.relpath(f, ROOT) for f in files]},
              open(os.path.join(HERE, 'sonnet2_final_tally.json'), 'w'), indent=1)


if __name__ == '__main__':
    main([a for a in sys.argv[1:] if not a.startswith('--')])
