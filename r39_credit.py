# -*- coding: utf-8 -*-
"""Does the 53.3% useful-on-thin spike survive the rh credit filter?"""
import json, re, sys, collections, urllib.request
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
M = json.load(open("r39_export.json"))
AT = re.compile(r"^ATTEST\s+v1\s*\|\s*(\S+)\s*\|\s*(\w+)\s*\|(.*)$", re.S)
att = []
for m in M:
    t = (m.get("text") or "").strip(); g = AT.match(t)
    if not g: continue
    rest = g.group(3).strip(); rh = None
    if rest.startswith("rh:"):
        p = rest.split("|", 1); rh = p[0][3:].strip(); rest = p[1].strip() if len(p) > 1 else ""
    att.append(dict(seq=m["seq"], did=m.get("from"), job=g.group(1),
                    verdict=g.group(2).lower(), rh=rh, reason=rest))
useful = [a for a in att if a["verdict"] == "useful"]
def creditable(a): return bool(a["rh"]) and re.fullmatch(r"[0-9a-f]{16}", a["rh"] or "")
cred = [a for a in useful if creditable(a)]
print("ALL useful in snapshot: %d" % len(useful))
print("  creditable (16-hex rh): %d (%.1f%%)" % (len(cred), 100.0*len(cred)/len(useful)))
print("  no-op (no/short rh)   : %d (%.1f%%)" % (len(useful)-len(cred), 100.0*(len(useful)-len(cred))/len(useful)))

big = collections.Counter(a["reason"] for a in useful).most_common(1)[0][0]
CORE = {a["did"] for a in useful if a["reason"] == big}
print("\nfleet share of ALL useful      : %.1f%%" % (100.0*sum(1 for a in useful if a['did'] in CORE)/len(useful)))
print("fleet share of CREDITABLE useful: %.1f%%" % (100.0*sum(1 for a in cred if a['did'] in CORE)/max(1,len(cred))))

body = {}
for m in M:
    t = (m.get("text") or "")
    if not t.startswith("RESULT v1"): continue
    p = t.split("|", 2)
    if len(p) >= 3: body.setdefault(p[1].strip(), []).append(p[2].strip())
def thin(j): return j in body and min(len(b) for b in body[j]) < 180
for lab, rows in (("ALL useful", useful), ("CREDITABLE only", cred)):
    res = [a for a in rows if a["job"] in body]
    t = sum(1 for a in res if thin(a["job"]))
    print("\n%-16s resolvable %4d | on a body <180 chars: %4d = %.1f%%" % (lab, len(res), t, 100.0*t/max(1,len(res))))

print("\n=== END-TO-END CHECK on the live passports ===")
d = json.loads(urllib.request.urlopen("https://flop-kibble.onrender.com/api/stats", timeout=60).read())
P = {p["did"]: p for p in d["passports"]}
rc = collections.Counter()
for a in useful:
    if a["did"] in CORE:
        for w in {x for x in body.get(a["job"], [])} and []: pass
rec = collections.Counter()
worker = {}
for m in M:
    t = (m.get("text") or "")
    if t.startswith("RESULT v1"):
        p = t.split("|", 2)
        if len(p) >= 3: worker.setdefault(p[1].strip(), m.get("from"))
for a in useful:
    if a["did"] in CORE and a["job"] in worker: rec[worker[a["job"]]] += 1
print("top recipients of the fleet's 806 useful verdicts, vs what their passport shows:")
for w, n in rec.most_common(8):
    p = P.get(w)
    if p: print("   %s  received %3d useful in this 2h14m window | passport useful_attestations_received = %d  (rank %d)"
                % (w[-14:], n, p["useful_attestations_received"], p["rank"]))
    else: print("   %s  received %3d | not in top-48 passports" % (w[-14:], n))
for d_ in sorted(CORE):
    p = P.get(d_)
    print("   FLEET %s attestations_given(passport) = %s" % (d_[-14:], p["attestations_given"] if p else "not in top 48"))
