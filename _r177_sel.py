# -*- coding: utf-8 -*-
import json, random, hashlib, collections
q=json.load(open('guide/attest_queue_offboard.json',encoding='utf-8'))
prev=set()
import glob,os
for f in glob.glob('guide/_r1*_attest_log.json'):
    try:
        for x in json.load(open(f,encoding='utf-8')): prev.add(x.get('job'))
    except Exception: pass
print('already attested by us:',len(prev))
cand=[p for p in q if p.get('job_id') not in prev and p.get('result')]
print('candidates',len(cand))
# spread across workers and categories
bycat=collections.Counter(p.get('category') for p in cand)
print('categories',bycat.most_common())
byw=collections.Counter(p.get('worker') for p in cand)
print('distinct workers',len(byw),'top',byw.most_common(5))
rnd=random.Random(177)
rnd.shuffle(cand)
sel=[]; seen_w=collections.Counter()
for p in cand:
    if seen_w[p['worker']]>=1: continue
    sel.append(p); seen_w[p['worker']]+=1
    if len(sel)>=26: break
json.dump(sel,open('guide/_r177_sel.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
print('selected',len(sel))
for p in sel:
    print('---',p['job_id'],p.get('category'),'rh=',p.get('result_hash') or p.get('rh'),'resultlen',len(p.get('result','')))
