import json,urllib.request,collections,time
import tclk1
rooms=json.load(open('tclk_rooms_r18.json',encoding='utf-8'))
res={}
for seq,frm,c in rooms:
    cc=c if str(c).startswith('0x') else '0x'+str(c)
    room=tclk1.deal_room(cc)
    for attempt in range(3):
        try:
            with urllib.request.urlopen('https://technocore.chat/r/%s?format=json'%room,timeout=45) as r:
                res[room]=json.loads(r.read().decode()); break
        except Exception as e:
            if attempt==2: res[room]={'ERR':str(e)[:60]}
            else: time.sleep(2)
json.dump(res,open('tclk_dealrooms_full_r18.json','w'),indent=1)
kinds=collections.Counter(); empty=0; err=0; chains={}
for room,d in res.items():
    if 'ERR' in d: err+=1; continue
    if d.get('count',0)==0: empty+=1; continue
    ks=[]
    for m in d.get('messages',[]):
        t=m.get('text','')
        if t.startswith('tclk1 '):
            try: ks.append((json.loads(t[6:]).get('type'),m['ts'],m['from']))
            except: ks.append(('badjson',m['ts'],m['from']))
        else: ks.append(('nontclk',m['ts'],m['from']))
    kinds.update(k[0] for k in ks); chains[room]=ks
print('rooms',len(res),'empty',empty,'err',err,'active',len(chains))
print('kinds',dict(kinds))
complete=[r for r,k in chains.items() if any(x[0]=='receipt' for x in k)]
print('deals reaching receipt:',len(complete))
json.dump(chains,open('tclk_chains_r18.json','w'),indent=1,default=str)
