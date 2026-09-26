# Paired read: relay /api/stats counters vs origin technocore.chat/r/kibble over the same 5 minutes. Deadline-bounded (one 300 s wait).
import json, time, urllib.request, collections
UA={"User-Agent":"flop-jp-agent/1.0"}
def get(u,t=90):
    with urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=t) as r: return r.read().decode('utf-8','replace')
def snap():
    s=json.loads(get("https://flop-kibble.onrender.com/api/stats"))
    room=get("https://technocore.chat/r/kibble/export?limit=5")
    last=[json.loads(l) for l in room.splitlines() if l.startswith('{')][-1]
    pp={p['did']:{k:p[k] for k in ('jobs_posted','results_delivered','attestations_given')} for p in s['passports']}
    return dict(t=time.time(),stats=s['stats'],seq=last['seq'],ts=last['ts'],pp=pp)
a=snap(); time.sleep(300); b=snap()
room=get("https://technocore.chat/r/kibble/export?limit=14000",120)
rows=[json.loads(l) for l in room.splitlines() if l.startswith('{')]
win=[r for r in rows if a['seq']<r['seq']<=b['seq']]
kinds=collections.Counter(r['text'].split('|')[0].strip() for r in win)
out=dict(a_seq=a['seq'],b_seq=b['seq'],a_ts=a['ts'],b_ts=b['ts'],room_lines=b['seq']-a['seq'],win_rows=len(win),room_kinds=dict(kinds),
 relay_delta={k:b['stats'][k]-a['stats'][k] for k in ('parsed','jobs','delivered','attested','briefs','ignored','policy_skipped')})
# per-key: top relay keys, room lines by kind vs relay delta
per=[]
for did in list(b['pp'])[:15]:
    rk=collections.Counter(r['text'].split('|')[0].strip() for r in win if r['from']==did)
    d0=a['pp'].get(did,{'jobs_posted':0,'results_delivered':0,'attestations_given':0})
    per.append(dict(did=did[-8:],room_JOB=rk.get('JOB v1',0),room_RESULT=rk.get('RESULT v1',0),room_ATTEST=rk.get('ATTEST v1',0),
      relay_djobs=b['pp'][did]['jobs_posted']-d0['jobs_posted'],relay_dres=b['pp'][did]['results_delivered']-d0['results_delivered'],relay_datt=b['pp'][did]['attestations_given']-d0['attestations_given']))
out['per_key']=per
print(json.dumps(out,ensure_ascii=False,indent=1))
