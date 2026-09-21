"""Stratified audit sample: distinct workers, spread across category and body length."""
import json, collections, random, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
q = json.load(open('guide/attest_queue_offboard.json', encoding='utf-8'))
random.seed(166)
bycat = collections.defaultdict(list)
for i, p in enumerate(q):
    bycat[p['category']].append(i)
seen_worker = set(); picked = []
cats = sorted(bycat)
# round-robin over categories, one pair per worker, alternating short/long bodies
for cat in cats:
    idxs = sorted(bycat[cat], key=lambda i: q[i]['body_len'])
    for i in idxs[::max(1, len(idxs)//8)]:
        w = q[i]['worker']
        if w in seen_worker:
            continue
        seen_worker.add(w); picked.append(i)
        if len(picked) >= 40:
            break
random.shuffle(picked)
picked = picked[:15]
json.dump(picked, open('guide/_r166_picked.json', 'w'))
print('picked %d pairs, %d distinct workers' % (len(picked), len(set(q[i]['worker'] for i in picked)))) 
for i in picked:
    p = q[i]
    print('\n' + '='*100)
    print('IDX %d  JOB %s  [%s]  worker ...%s  body_len %d  rh %s'
          % (i, p['job_id'], p['category'], p['worker'][-12:], p['body_len'], (p.get('rh') or '')[:16]))
    print('TITLE: %s' % p['title'])
    print('SPEC : %s' % p['spec'])
    print('-'*100)
    r = p['result']
    print('RESULT (%d chars):' % len(r))
    print(r[:1500])
    if len(r) > 1500:
        print('   ... [TAIL] ...')
        print(r[-350:])
