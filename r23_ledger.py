#!/usr/bin/env python3
"""Round 23: advertised value vs settled value on tclk/1."""
import json, urllib.request, sys, collections, datetime
sys.path.insert(0, '.')
import tclk1
ORIGIN = "https://technocore.chat"
raw = urllib.request.urlopen(ORIGIN + "/r/tclk-offers/export", timeout=90).read().decode('utf-8','replace')
offers = []
for line in raw.splitlines():
    try: m = json.loads(line)
    except Exception: continue
    t = m.get('text','')
    if not tclk1.is_tclk_line(t): continue
    try: fr = json.loads(t[len(tclk1.TCLK_PREFIX):])
    except Exception: continue
    fr['_ts']=m.get('ts')
    if fr.get('type')=='offer': offers.append(fr)

rails = collections.Counter()
for o in offers:
    for r in (o.get('rails') or []):
        rails[str(r)] += 1
print("offers %d" % len(offers))
print("advertised rails: %s" % dict(rails))

notional = collections.Counter(); n_by_asset = collections.Counter()
for o in offers:
    a = str(o.get('asset') or '(none)').upper()
    n_by_asset[a] += 1
    try: notional[a] += int(float(o.get('amount') or 0))
    except Exception: pass
print("assets: %s" % dict(n_by_asset))
print("notional advertised: %s" % dict(notional))

st = json.load(open('tclk_rail_state.json', encoding='utf-8'))
locks = st['seen_locks']
lock_rails = collections.Counter(v.get('rail','?') for v in locks.values())
print("\nOBSERVED LOCKS: %d, rails %s" % (len(locks), dict(lock_rails)))
nonpaper = st['nonpaper_locks']
print("non-paper locks: %d -> %s" % (len(nonpaper), json.dumps(nonpaper, ensure_ascii=False)))
adv = rails.get('flop-htlc', 0)
print("\nflop-htlc: advertised on %d offers, used on %d of %d observed locks (%.2f%%)"
      % (adv, lock_rails.get('flop-htlc',0), len(locks), 100.0*lock_rails.get('flop-htlc',0)/len(locks)))
print("x402:      advertised on %d offers, used on %d locks" % (rails.get('x402',0), lock_rails.get('x402',0)))

# hourly ramp, plain
def parse(t):
    return datetime.datetime.fromisoformat(t.replace('Z','+00:00'))
h = collections.Counter(o['_ts'][:13] for o in offers)
print("\nhourly OFFER count:")
for k in sorted(h): print("  %sZ %d" % (k, h[k]))
