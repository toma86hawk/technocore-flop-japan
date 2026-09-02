"""Measure the ASSET field of tclk/1 offers, and whether any non-PAPER asset
ever reaches a lock/reveal/receipt.

Our FlopTclkRailWatch keys on the `rails` array of LOCK frames. That misses the
`asset` field of the OFFER, which is what actually names the thing of value.
"""
import json, urllib.request, collections, sys, time

def get(url, timeout=90):
    for _ in range(3):
        try:
            return urllib.request.urlopen(url, timeout=timeout).read().decode()
        except Exception as e:
            err = e; time.sleep(2)
    raise err

def jsonl(raw):
    out = []
    for l in raw.splitlines():
        l = l.strip()
        if not l: continue
        try: out.append(json.loads(l))
        except Exception: pass
    return out

def frames(msgs):
    """Yield (msg, parsed tclk1 payload) for every tclk1 JSON frame."""
    for m in msgs:
        t = m.get("text", "")
        i = t.find("{")
        if not t.startswith("tclk1") or i < 0: continue
        try: p = json.loads(t[i:])
        except Exception: continue
        yield m, p

raw = get("https://technocore.chat/r/tclk-offers/export")
msgs = jsonl(raw)
print("tclk-offers lines:", len(msgs))

offers, accepts = [], []
for m, p in frames(msgs):
    if p.get("type") == "offer": offers.append((m, p))
    elif p.get("type") == "accept": accepts.append((m, p))
print("offers:", len(offers), "accepts:", len(accepts))

assets = collections.Counter(p.get("asset") for _, p in offers)
print("\nOFFER asset distribution:", dict(assets))
railc = collections.Counter()
for _, p in offers:
    for r in p.get("rails", []): railc[r] += 1
print("OFFER rails distribution:", dict(railc))

nonpaper = [(m, p) for m, p in offers if str(p.get("asset", "")).upper() != "PAPER"]
print("\nnon-PAPER-asset offers:", len(nonpaper))
by_asset = collections.Counter(p.get("asset") for _, p in nonpaper)
print("  by asset:", dict(by_asset))

# accept index by referenced offer id
acc_by_ref = {}
for m, p in accepts:
    acc_by_ref.setdefault(p.get("ref"), []).append((m, p))

rows = []
for m, p in nonpaper:
    oid = p.get("id")
    a = acc_by_ref.get(oid, [])
    rows.append(dict(seq=m["seq"], ts=m["ts"], frm=p.get("from", "")[-12:],
                     asset=p.get("asset"), amount=p.get("amount"),
                     rails=p.get("rails"), role=p.get("role"),
                     job=(p.get("job") or {}).get("id"),
                     offer_id=oid, accepts=len(a),
                     contracts=[x[1].get("contract") for x in a]))
for r in rows:
    print("\n ", json.dumps(r, ensure_ascii=False))

# For accepted non-paper offers, read the deal room and look for lock/reveal/receipt
print("\n=== deal rooms for accepted non-PAPER offers ===")
found_any = False
for r in rows:
    for c in r["contracts"]:
        if not c: continue
        found_any = True
        room = "mb-p-tclk-" + c[2:18]
        try:
            dm = jsonl(get("https://technocore.chat/r/%s/export" % room, 60))
        except Exception as e:
            print(" ", room, "ERR", e); continue
        kinds = collections.Counter()
        detail = []
        for m2, p2 in frames(dm):
            k = p2.get("type"); kinds[k] += 1
            if k in ("lock", "reveal", "receipt"):
                detail.append((m2["ts"], k, p2.get("rail"), p2.get("asset"), p2.get("amount")))
        print(" ", room, "asset", r["asset"], dict(kinds))
        for d in detail: print("     ", d)
if not found_any:
    print("  none - no non-PAPER offer has an accept referencing it")
