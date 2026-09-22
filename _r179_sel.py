# -*- coding: utf-8 -*-
import json, random, collections, glob, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
q = json.load(open('guide/attest_queue_offboard.json', encoding='utf-8'))
prev = set()
for f in glob.glob('guide/_r1*_attest_log.json'):
    try:
        for x in json.load(open(f, encoding='utf-8')):
            prev.add(x.get('job'))
    except Exception:
        pass
print('already attested by us:', len(prev))
cand = [p for p in q if p.get('job_id') not in prev and p.get('result') and p.get('rh')]
print('candidates', len(cand))
print('categories', collections.Counter(p.get('category') for p in cand).most_common())
byw = collections.Counter(p.get('worker') for p in cand)
print('distinct workers', len(byw), 'top', byw.most_common(5))
rnd = random.Random(179)
rnd.shuffle(cand)
sel, seen_w = [], collections.Counter()
for p in cand:
    if seen_w[p['worker']] >= 1:
        continue
    sel.append(p); seen_w[p['worker']] += 1
    if len(sel) >= 26:
        break
json.dump(sel, open('guide/_r179_sel.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('selected', len(sel))
for p in sel:
    print('---', p['job_id'], p.get('category'), 'rh=', p.get('rh'),
          'len', p.get('body_len'), 'competing', p.get('competing_results'))
