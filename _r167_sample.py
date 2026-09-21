"""Round 167 stratified audit sample: distinct workers, spread over category and body length."""
import json, collections, random, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
q = json.load(open('guide/attest_queue_offboard.json', encoding='utf-8'))
random.seed(167)
bycat = collections.defaultdict(list)
for i, p in enumerate(q):
    bycat[p['category']].append(i)
seen_worker = set(); picked = []
for cat in sorted(bycat):
    idxs = sorted(bycat[cat], key=lambda i: q[i]['body_len'])
    step = max(1, len(idxs)//10)
    for i in idxs[::step]:
        w = q[i]['worker']
        if w in seen_worker:
            continue
        seen_worker.add(w); picked.append(i)
random.shuffle(picked)
picked = picked[:15]
json.dump(picked, open('guide/_r167_picked.json', 'w'))
print('picked %d pairs, %d distinct workers' % (len(picked), len(set(q[i]['worker'] for i in picked))))
for i in picked:
    p = q[i]
    print('\n' + '='*100)
    print('IDX %d  JOB %s  [%s]  worker ...%s  body_len %d  rh %s  useful_n %s not_n %s'
          % (i, p['job_id'], p['category'], p['worker'][-12:], p['body_len'],
             (p.get('rh') or '')[:16], p.get('useful_n'), p.get('not_n')))
    print('TITLE: %s' % p['title'])
    print('SPEC : %s' % p['spec'])
    print('-'*100)
    r = p['result']
    print('RESULT (%d chars):' % len(r))
    print(r[:1600])
    if len(r) > 1600:
        print('   ... [TAIL] ...')
        print(r[-350:])
