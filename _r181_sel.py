# -*- coding: utf-8 -*-
import json, random, collections, glob, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
q = json.load(open('guide/attest_queue_offboard.json', encoding='utf-8'))
prev = set()
for f in glob.glob('guide/_r1*_attest_log.json') + glob.glob('guide/_r1*_landed.json') + glob.glob('guide/_r1*_sel.json') + glob.glob('guide/_r1*_picked.json'):
    try:
        for x in json.load(open(f, encoding='utf-8')):
            if isinstance(x, dict):
                prev.add(x.get('job') or x.get('job_id'))
    except Exception:
        pass
prev.discard(None)
print('already handled by us:', len(prev))
cand = [p for p in q if p.get('job_id') not in prev and p.get('result') and p.get('rh')]
print('candidates', len(cand))
byw = collections.Counter(p.get('worker') for p in cand)
print('distinct workers', len(byw))
rnd = random.Random(181)
rnd.shuffle(cand)
sel, seen_w = [], collections.Counter()
for p in cand:
    if seen_w[p['worker']] >= 1:
        continue
    sel.append(p); seen_w[p['worker']] += 1
    if len(sel) >= 22:
        break
json.dump(sel, open('guide/_r181_sel.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('selected', len(sel))
