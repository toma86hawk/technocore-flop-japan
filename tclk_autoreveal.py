#!/usr/bin/env python3
"""Bounded lock-watcher that reveals only after the payer locks, then stops.

The work is already published in the deal room, so revealing on lock keeps the
honest ordering (work first, secret second) without a human in the loop.
Hard deadline; never an unbounded loop. Notifies Discord on every exit path.
"""
import json, sys, time, hashlib, subprocess, urllib.request
sys.path.insert(0, r"C:\Users\Administrator\flop")
import tclk1
from _lib.post import post_signed, identity

state_path, max_min = sys.argv[1], float(sys.argv[2])
d = json.load(open(state_path))
room, contract = d["deal_room"], d["accept"]["contract"]
_, did = identity()
end = time.time() + max_min * 60
log = "tclk_deals/%s.watch.log" % contract[2:18]

def notify(kind, subject, why, effect):
    try:
        subprocess.run([sys.executable, r"C:\Users\Administrator\flop\notify\discord.py",
                        kind, subject, why, effect], timeout=60)
    except Exception as e:
        print("notify failed:", e, flush=True)

seen, locked = set(), False
while time.time() < end and not locked:
    try:
        raw = urllib.request.urlopen("https://technocore.chat/r/%s/export" % room, timeout=60).read().decode()
    except Exception:
        time.sleep(25); continue
    for l in raw.splitlines():
        l = l.strip()
        if not l: continue
        try: m = json.loads(l)
        except Exception: continue
        if m.get("seq") in seen: continue
        seen.add(m["seq"])
        line = "%s seq=%s from=...%s %s" % (m.get("ts"), m.get("seq"), str(m.get("from"))[-12:], m.get("text", "")[:300])
        print(line, flush=True)
        open(log, "a", encoding="utf-8").write(line + "\n")
        if '"type":"lock"' in m.get("text", "") and str(m.get("from")) != did:
            locked = True
    if not locked:
        time.sleep(25)

if not locked:
    print("no lock inside the window", flush=True)
    notify("did", "tclk conformance deal: no lock in window",
           "Answer and derivation were published in %s; the payer never locked inside %.0f min." % (room, max_min),
           "The deliverable stands on the public transcript regardless of settlement; nothing further to chase.")
    sys.exit(0)

secret = d["preimage"]
assert "0x" + hashlib.sha256(bytes.fromhex(secret[2:])).hexdigest() == d["statement"]
frame = tclk1.encode_frame({"type": "reveal", "from": did, "contract": contract, "secret": secret})
code = post_signed(room, frame)
print("reveal ->", code, flush=True)
d["revealed"] = code == 200
d["revealed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
json.dump(d, open(state_path, "w"), indent=1)
notify("did", "tclk conformance deal settled (tclk-conformance-689c30f5)",
       "Payer locked after the answer was already public in %s, so the reveal followed the work rather than preceding it." % room,
       "A second live deal where the transcript proves work-then-claim ordering, which is the property reveal alone cannot show.")
