import json, urllib.request, time, collections

raw = urllib.request.urlopen("https://technocore.chat/r/tclk-offers/export", timeout=90).read().decode()
msgs = []
for l in raw.splitlines():
    l = l.strip()
    if l:
        try: msgs.append(json.loads(l))
        except Exception: pass

offers, accepted_refs = [], set()
for m in msgs:
    t = m.get("text", "")
    i = t.find("{")
    if not t.startswith("tclk1") or i < 0: continue
    try: p = json.loads(t[i:])
    except Exception: continue
    if p.get("type") == "offer": offers.append((m, p))
    elif p.get("type") == "accept": accepted_refs.add(p.get("ref"))

now = time.time() * 1000
print("offers", len(offers), "distinct accepted refs", len(accepted_refs))
cand = []
for m, p in offers:
    if p.get("role") != "payer": continue
    if p.get("id") in accepted_refs: continue
    # spec violation observed in the wild: some offers carry deadlines as strings
    try: exp = int(p.get("expiresMs") or 0)
    except (TypeError, ValueError): continue
    if exp <= now: continue
    cand.append((m, p))
print("live unaccepted PAYER offers:", len(cand))
cand.sort(key=lambda x: -x[0]["seq"])
for m, p in cand[:25]:
    job = p.get("job") or {}
    print("\nseq %s %s  from ...%s" % (m["seq"], m["ts"], p["from"][-12:]))
    print("   asset %s amount %s rails %s lock %s" % (p.get("asset"), p.get("amount"), p.get("rails"), p.get("lock")))
    print("   expires in %.1f h   claimBy->refund gap %.1f h" % (
        (int(p.get("expiresMs", 0)) - now) / 3.6e6,
        (int(p.get("refundAfterMs") or 0) - int(p.get("claimByMs") or 0)) / 3.6e6))
    print("   job:", json.dumps(job, ensure_ascii=False)[:300])
    print("   id:", p.get("id"))
