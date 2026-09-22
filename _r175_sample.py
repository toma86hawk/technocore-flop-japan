# -*- coding: utf-8 -*-
import json, urllib.request, time
DID="did:key:z6Mkpjt48fahhtdXLpw9Tvzutd5KeYSSkMLaSbfAmfxfdwqb"
B="https://flop-kibble.onrender.com"
def get(u,t=45):
    r=urllib.request.urlopen(u,timeout=t); return json.loads(r.read().decode('utf-8'))
sc=get(B+"/api/score?did="+urllib.parse.quote(DID))
print(json.dumps(sc,ensure_ascii=False)[:1500])
