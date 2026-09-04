import json, urllib.request
from datetime import datetime
ST = json.load(open("tclk_rail_state.json"))
NP = ST["nonpaper_locks"]
def room(r):
    req = urllib.request.Request(f"https://technocore.chat/r/{r}/export",
        headers={"User-Agent":"flop-jp-agent/1.0"})
    raw = urllib.request.urlopen(req, timeout=90).read().decode("utf-8","replace")
    out=[]
    for ln in raw.splitlines():
        ln=ln.strip()
        if ln:
            try: out.append(json.loads(ln))
            except Exception: pass
    return out
def frame(t):
    t=str(t)
    if t.startswith("tclk1 "):
        try: return json.loads(t[6:])
        except Exception: return None
    return None
def p(s): return datetime.fromisoformat(s.replace("Z","+00:00")) if s else None
rows=[]
for L in NP:
    try: ms = room(L["room"])
    except Exception as e:
        print(L["room"], "ERR", repr(e)[:60]); continue
    dids=set(); seq={}; work=0
    for m in ms:
        dids.add(m.get("from"))
        fr=frame(m.get("text"))
        if fr and fr.get("type"):
            seq.setdefault(fr["type"], m.get("ts"))
        else:
            work+=1
    lk, rv, rc = seq.get("lock"), seq.get("reveal"), seq.get("receipt")
    dt = (p(rv)-p(lk)).total_seconds() if lk and rv else None
    rows.append({"room":L["room"],"rail":L["rail"],"msgs":len(ms),"dids":sorted(dids),
                 "n_dids":len(dids),"lock":lk,"reveal":rv,"receipt":rc,
                 "lock_to_reveal_s":dt,"nontclk_msgs":work,"types":list(seq)})
    print(f'{L["room"]:<26} {L["rail"]:<10} msgs={len(ms)} dids={len(dids)} '
          f'lock->reveal={dt}s types={list(seq)} work_msgs={work}')
json.dump(rows, open("nonpaper_reveal.json","w"), indent=1)
ok=[r for r in rows if r["lock_to_reveal_s"] is not None]
print()
print("non-paper deals measured:", len(rows))
print("single-DID rooms (payer==payee, no counterparty):",
      sum(1 for r in rows if r["n_dids"]==1), "/", len(rows))
print("rooms with any non-tclk1 message (evidence of work):",
      sum(1 for r in rows if r["nontclk_msgs"]>0), "/", len(rows))
if ok:
    v=sorted(r["lock_to_reveal_s"] for r in ok)
    print("lock->reveal seconds:", v)
    print("median", v[len(v)//2], "max", v[-1])
