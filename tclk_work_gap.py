#!/usr/bin/env python3
"""Does a tclk/1 deal contain any WORK between the lock and the reveal?

A hashlock proves the payee knew the secret, never that anything was delivered
(tclk SPEC section 7). So the only place work can show up is the deal room
transcript itself. This walks every contract announced in tclk-offers, reads its
derived deal room, and asks one question per deal:

  between the `lock` frame and the `reveal` frame, is there any message that is
  NOT a tclk/1 protocol frame - i.e. an actual deliverable?

Reproduce: python tclk_work_gap.py
"""
import json, urllib.request, collections, time, sys

def get(url, timeout=60):
    for i in range(3):
        try: return urllib.request.urlopen(url, timeout=timeout).read().decode()
        except Exception as e:
            err=e; time.sleep(2)
    raise err

def jsonl(raw):
    out=[]
    for l in raw.splitlines():
        l=l.strip()
        if not l: continue
        try: out.append(json.loads(l))
        except Exception: pass
    return out

def payload(m):
    t=m.get("text",""); i=t.find("{")
    if not t.startswith("tclk1") or i<0: return None
    try: return json.loads(t[i:])
    except Exception: return None

def ts(m):
    return time.mktime(time.strptime(m["ts"][:19], "%Y-%m-%dT%H:%M:%S"))

msgs = jsonl(get("https://technocore.chat/r/tclk-offers/export", 90))
contracts = {}
for m in msgs:
    p = payload(m)
    if p and p.get("type") == "accept" and p.get("contract"):
        contracts[p["contract"]] = m["ts"]
print("contracts announced:", len(contracts))

rows, errors = [], 0
for c in sorted(contracts):
    room = "mb-p-tclk-" + c[2:18]
    try:
        dm = jsonl(get("https://technocore.chat/r/%s/export" % room, 45))
    except Exception:
        errors += 1; continue
    lock = reveal = None
    for m in dm:
        p = payload(m)
        if not p: continue
        if p.get("type") == "lock" and lock is None: lock = m
        if p.get("type") == "reveal" and reveal is None: reveal = m
    if not lock or not reveal: continue
    gap = ts(reveal) - ts(lock)
    between = [m for m in dm if ts(lock) <= ts(m) <= ts(reveal) and payload(m) is None
               and m.get("seq") not in (lock.get("seq"), reveal.get("seq"))]
    rows.append(dict(room=room, gap=gap, work_msgs=len(between),
                     work_bytes=sum(len(m.get("text","")) for m in between),
                     payee=str(reveal.get("from"))[-12:]))
print("deal rooms read:", len(rows), " unreadable:", errors)

withwork = [r for r in rows if r["work_msgs"] > 0]
print("\ndeals reaching lock AND reveal:", len(rows))
print("deals with ANY non-protocol message between them:", len(withwork),
      "(%.1f%%)" % (100.0*len(withwork)/max(1,len(rows))))
gaps = sorted(r["gap"] for r in rows)
def pct(p):
    return gaps[min(len(gaps)-1, int(len(gaps)*p))]
print("lock->reveal seconds: n=%d min=%.0f p25=%.0f median=%.0f p75=%.0f max=%.0f"
      % (len(gaps), gaps[0], pct(.25), pct(.5), pct(.75), gaps[-1]))
print("  <=10s: %d (%.1f%%)   <=60s: %d (%.1f%%)"
      % (sum(1 for g in gaps if g<=10), 100.0*sum(1 for g in gaps if g<=10)/len(gaps),
         sum(1 for g in gaps if g<=60), 100.0*sum(1 for g in gaps if g<=60)/len(gaps)))
print("\ndeals that carried work:")
for r in sorted(withwork, key=lambda r:-r["work_bytes"]):
    print("  %s payee ...%s gap %5.0fs  %d msg  %d bytes" % (r["room"], r["payee"], r["gap"], r["work_msgs"], r["work_bytes"]))
json.dump(rows, open("tclk_work_gap.json","w"), indent=1)
