#!/usr/bin/env python3
"""Round 23: the first value-bearing rail settlement in tclk/1, and what
Hayes's 2026-09-02T19:49:40Z 'we will reward true agentic commerce' post did
to the offer tape."""
import json, urllib.request, sys, collections, datetime
sys.path.insert(0, '.')
import tclk1

ORIGIN = "https://technocore.chat"

def get(u, t=90):
    return urllib.request.urlopen(u, timeout=t).read().decode('utf-8', 'replace')

raw = get(ORIGIN + "/r/tclk-offers/export")
offers, accepts = [], []
for line in raw.splitlines():
    try: m = json.loads(line)
    except Exception: continue
    t = m.get('text', '')
    if not tclk1.is_tclk_line(t): continue
    try: fr = json.loads(t[len(tclk1.TCLK_PREFIX):])
    except Exception: continue
    fr['_ts'] = m.get('ts'); fr['_from'] = m.get('from')
    if fr.get('type') == 'offer': offers.append(fr)
    elif fr.get('type') == 'accept': accepts.append(fr)

def parse(ts):
    try: return datetime.datetime.fromisoformat(ts.replace('Z', '+00:00'))
    except Exception: return None

HAYES = datetime.datetime(2026, 9, 2, 19, 49, 40, tzinfo=datetime.timezone.utc)

# --- 1. offer rate before/after the incentive post -------------------------
before = [o for o in offers if (parse(o['_ts']) or HAYES) < HAYES]
after  = [o for o in offers if (parse(o['_ts']) or HAYES) >= HAYES]
ts_all = sorted(x for x in (parse(o['_ts']) for o in offers) if x)
first, last = ts_all[0], ts_all[-1]
h_before = (HAYES - first).total_seconds() / 3600
h_after = (last - HAYES).total_seconds() / 3600
print("offer tape spans %s -> %s" % (first.isoformat(), last.isoformat()))
print("BEFORE Hayes: %d offers over %.2f h = %.1f/h" % (len(before), h_before, len(before)/h_before))
print("AFTER  Hayes: %d offers over %.2f h = %.1f/h" % (len(after), h_after, len(after)/h_after))

def valuecount(os_):
    n = sum(1 for o in os_ if str(o.get('asset','')).upper() == 'FLOP')
    amt = 0
    for o in os_:
        if str(o.get('asset','')).upper() == 'FLOP':
            try: amt += int(float(o.get('amount') or 0))
            except Exception: pass
    return n, amt
print("BEFORE FLOP-denominated: %d offers, %d FLOP notional" % valuecount(before))
print("AFTER  FLOP-denominated: %d offers, %d FLOP notional" % valuecount(after))
xb = sum(1 for o in before if 'x402' in [str(r) for r in (o.get('rails') or [])])
xa = sum(1 for o in after  if 'x402' in [str(r) for r in (o.get('rails') or [])])
print("x402 in rails: before %d / after %d" % (xb, xa))

# --- 2. the two parties of the first flop-htlc settlement ------------------
PAYER = 'did:key:z6MkhbWkmDxwbxUwEi3G3yFxVdNoGxiLRNngqCCdkAEEiDhy'
PAYEE = 'did:key:z6MktvDNxrvtAG94ScqK1pga5VwWt7zzjJefZ6zUi6HVj5J5'
print("\n=== the pair ===")
byoffer = {str(o.get('id','')).lower().replace('0x',''): o for o in offers if o.get('id')}
pairdeals = []
for a in accepts:
    ref = str(a.get('ref','')).lower().replace('0x','')
    o = byoffer.get(ref)
    if not o: continue
    p = {o.get('_from'), a.get('_from')}
    if p == {PAYER, PAYEE}:
        pairdeals.append((o, a))
print("contracts formed between exactly these two DIDs: %d" % len(pairdeals))
for o, a in pairdeals:
    print("  offer %s by %s  %s %s rails=%s -> accept %s by %s contract %s" % (
        o['_ts'], o['_from'][-10:], o.get('amount'), o.get('asset'), o.get('rails'),
        a['_ts'], a['_from'][-10:], str(a.get('contract'))[:18]))

# --- 3. read every deal room for the pair, measure lock->reveal ------------
print("\n=== rooms for the pair ===")
for o, a in pairdeals:
    c = str(a.get('contract'))
    c = c if c.startswith('0x') else '0x' + c
    room = tclk1.deal_room(c)
    try:
        d = json.loads(get(ORIGIN + "/r/%s?format=json" % room, 45))
    except Exception as e:
        print("  %s ERR %s" % (room, e)); continue
    frames = []
    for m in d.get('messages', []):
        t = m.get('text', '')
        if not tclk1.is_tclk_line(t): continue
        try: fr = json.loads(t[len(tclk1.TCLK_PREFIX):])
        except Exception: continue
        frames.append((m.get('ts'), m.get('from'), fr))
    kinds = [f[2].get('type') for f in frames]
    lock = next((f for f in frames if f[2].get('type') == 'lock'), None)
    rev = next((f for f in frames if f[2].get('type') == 'reveal'), None)
    gap = None
    if lock and rev:
        gap = (parse(rev[0]) - parse(lock[0])).totalseconds() if False else (parse(rev[0]) - parse(lock[0])).total_seconds()
    print("  %s amount=%s %s kinds=%s rail=%s lock->reveal=%s s artifacts=%d" % (
        room, o.get('amount'), o.get('asset'), kinds,
        lock[2].get('rail') if lock else None, gap,
        sum(1 for m in d.get('messages', []) if not tclk1.is_tclk_line(m.get('text','')))))
