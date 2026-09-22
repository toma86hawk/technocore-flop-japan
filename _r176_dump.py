# -*- coding: utf-8 -*-
import json,sys
sel=json.load(open('guide/_r176_sel.json',encoding='utf-8'))
a=int(sys.argv[1]); b=int(sys.argv[2])
for p in sel[a:b]:
    print('='*70)
    print('JOB',p['job_id'],'|',p.get('category'),'| rh',p.get('result_hash') or p.get('rh'))
    print('WORKER',(p.get('worker') or '')[-12:])
    print('TITLE:',p.get('title'))
    print('SPEC:',p.get('spec'))
    print('--- RESULT (%d chars) ---'%len(p.get('result','')))
    print(p.get('result',''))
