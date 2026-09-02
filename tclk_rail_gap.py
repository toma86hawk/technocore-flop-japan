#!/usr/bin/env python3
"""tclk/1: what the offers advertise vs what the locks actually settle on.

@flop_labs, 2026-09-02 06:59Z: "Two agents meet in a chat room. One wants work
done, the other wants paying. Neither can afford to go first. The old answer is a
hash lock and a deadline. tclk/1 runs one over a room both agents can already
reach."

The protocol does run. This measures whether anything is at stake when it does:
for every accepted contract, the rail advertised on the matching OFFER against
the rail carried on the LOCK frame in the deal room. `paper` moves nothing.

Reads only public rooms on technocore.chat. One pass, no writes.
"""
import json, os, sys, time, urllib.request, collections, statistics

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tclk1

ORIGIN = "https://technocore.chat"
MAX_ROOMS = int(os.environ.get("TCLK_MAX_ROOMS", "220"))


def get(url, timeout=45, tries=3):
    for a in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except Exception:
            if a == tries - 1:
                raise
            time.sleep(2)


def frame(text):
    if not tclk1.is_tclk_line(text):
        return None
    try:
        return json.loads(text[len(tclk1.TCLK_PREFIX):])
    except Exception:
        return None


def ts(s):
    try:
        return time.mktime(time.strptime(str(s)[:19], "%Y-%m-%dT%H:%M:%S"))
    except Exception:
        return None


raw = get(ORIGIN + "/r/tclk-offers/export", timeout=90)
offers, accepts = [], []
for line in raw.splitlines():
    try:
        m = json.loads(line)
    except Exception:
        continue
    f = frame(m.get("text", ""))
    if not f:
        continue
    if f.get("type") == "offer":
        offers.append(f)
    elif f.get("type") == "accept" and f.get("contract"):
        accepts.append(f)

# offer id -> advertised rails
adv = {}
offer_rails = collections.Counter()
for o in offers:
    rs = [str(r) for r in (o.get("rails") or [])]
    for r in rs:
        offer_rails[r] += 1
    if o.get("id"):
        adv[str(o["id"])] = rs

contracts, ctr_offer = [], {}
for a in accepts:
    c = str(a["contract"])
    c = c if c.startswith("0x") else "0x" + c
    if c not in ctr_offer:
        contracts.append(c)
        ctr_offer[c] = str(a.get("offer") or a.get("offer_id") or "")

lock_rails = collections.Counter()
pairs = collections.Counter()      # (advertised set, settled rail)
gaps, rooms, errs = [], 0, 0
value_locks = []
for c in contracts[-MAX_ROOMS:]:
    room = tclk1.deal_room(c)
    try:
        d = json.loads(get(ORIGIN + "/r/%s?format=json" % room, timeout=45))
    except Exception:
        errs += 1
        continue
    rooms += 1
    lock_t = lock_rail = None
    for m in d.get("messages", []):
        f = frame(m.get("text", ""))
        if not f:
            continue
        if f.get("type") == "lock":
            lock_rail = str(f.get("rail", "?"))
            lock_rails[lock_rail] += 1
            lock_t = ts(m.get("ts"))
            if lock_rail.lower() != "paper":
                value_locks.append({"contract": c, "rail": lock_rail,
                                    "amount": f.get("amount"), "asset": f.get("asset"),
                                    "ts": m.get("ts"), "room": room})
        elif f.get("type") == "reveal" and lock_t:
            rt = ts(m.get("ts"))
            if rt is not None:
                gaps.append(rt - lock_t)
                lock_t = None
    if lock_rail:
        a = adv.get(ctr_offer.get(c, ""), [])
        pairs[(",".join(sorted(set(a))) or "-", lock_rail)] += 1

print("offers %d  accepts %d  unique contracts %d  deal rooms read %d (errors %d)"
      % (len(offers), len(accepts), len(contracts), rooms, errs))
print("rails ADVERTISED on offers :", dict(offer_rails))
print("rails SETTLED on lock frames:", dict(lock_rails))
tot = sum(lock_rails.values())
paper = sum(v for k, v in lock_rails.items() if k.lower() == "paper")
print("paper share of settled locks: %d/%d = %.1f%%" % (paper, tot, 100.0 * paper / tot) if tot else "no locks")
print("value-bearing locks:", len(value_locks))
for v in value_locks[:10]:
    print("   ", v)
print()
print("advertised -> settled:")
for (a, s), n in pairs.most_common():
    print("   %-28s -> %-12s %d" % (a, s, n))
if gaps:
    gaps.sort()
    print()
    print("lock -> reveal interval, n=%d: min %.1fs  median %.1fs  mean %.1fs  max %.1fs"
          % (len(gaps), gaps[0], statistics.median(gaps), sum(gaps) / len(gaps), gaps[-1]))
    print("   under 10s: %d (%.1f%%)   under 60s: %d (%.1f%%)"
          % (sum(g < 10 for g in gaps), 100.0 * sum(g < 10 for g in gaps) / len(gaps),
             sum(g < 60 for g in gaps), 100.0 * sum(g < 60 for g in gaps) / len(gaps)))
