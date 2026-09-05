# -*- coding: utf-8 -*-
import json, re, sys, collections, statistics
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
    att.append(dict(seq=m["seq"], did=m.get("from"), job=g.group(1), verdict=g.group(2).lower(),
                    rh=rh, reason=rest, ts=m.get("ts")))
useful = [a for a in att if a["verdict"] == "useful"]

# CORE = the 6 DIDs that all share the single largest reason string
big = collections.Counter(a["reason"] for a in useful).most_common(1)[0][0]
CORE = {a["did"] for a in useful if a["reason"] == big}
F  = [a for a in useful if a["did"] in CORE]
oth= [a for a in useful if a["did"] not in CORE]
print("CORE fleet: %d DIDs" % len(CORE))
for d in sorted(CORE): print("   ", d)
V = collections.Counter(a["reason"] for a in F)
print("\nuseful lines: %d / %d = %.1f%% of ALL useful in window" % (len(F), len(useful), 100.0*len(F)/len(useful)))
print("distinct jobs endorsed: %d" % len({a['job'] for a in F}))
print("distinct reason strings: %d   <-- the whole vocabulary" % len(V))
print("'not' verdicts cast by the fleet:", sum(1 for a in att if a["did"] in CORE and a["verdict"]=="not"), "of", sum(1 for a in att if a['did'] in CORE))

print("\n=== per-DID split of each of the %d strings ===" % len(V))
order = sorted(CORE)
for s, n in V.most_common():
    c = collections.Counter(a["did"] for a in F if a["reason"] == s)
    v = [c.get(d,0) for d in order]
    print("  x%-4d %-28s sd=%5.1f (mean %5.1f) | %s" % (n, str(v), statistics.pstdev(v), statistics.mean(v), s[:58]))

print("\n=== rh presence: does the board CREDIT these? ===")
print("  fleet     useful with rh: %4d / %4d" % (sum(1 for a in F if a["rh"]), len(F)))
print("  non-fleet useful with rh: %4d / %4d" % (sum(1 for a in oth if a["rh"]), len(oth)))

body = {}
for m in M:
    t = (m.get("text") or "")
    if not t.startswith("RESULT v1"): continue
    p = t.split("|", 2)
    if len(p) >= 3: body.setdefault(p[1].strip(), []).append((m.get("from"), p[2].strip()))
def stats(rows, lab):
    L = [min(len(b) for _w,b in body[a["job"]]) for a in rows if a["job"] in body]
    if not L: print("  %s none resolvable" % lab); return
    print("  %-9s %4d resolvable | median body %4d chars | under 180 chars: %4d (%.1f%%)"
          % (lab, len(L), statistics.median(L), sum(1 for x in L if x<180), 100.0*sum(1 for x in L if x<180)/len(L)))
print("\n=== body length of what they endorse ===")
stats(F,"fleet"); stats(oth,"everyone")

print("\n=== recipients of the fleet's 'useful' ===")
rc = collections.Counter()
for a in F:
    for w,_b in body.get(a["job"], []): rc[w] += 1
print("  distinct recipients:", len(rc), " top:")
for d,n in rc.most_common(6): print("     ", d[-14:], n, "(%.1f%%)" % (100.0*n/sum(rc.values())))
print("  self-attest (fleet endorsing fleet):", sum(n for d,n in rc.items() if d in CORE))

print("\n=== first appearance of each fleet DID anywhere in snapshot ===")
first = {}
for m in M:
    f = m.get("from")
    if f in CORE and f not in first: first[f] = (m["seq"], m["ts"])
for d in order: print("   ", d[-14:], first.get(d))
print("  snapshot begins", M[0]["seq"], M[0]["ts"])

print("\n=== scheduling ===")
Fs = sorted(F, key=lambda a: a["seq"])
same = sum(1 for i in range(1,len(Fs)) if Fs[i]["did"]==Fs[i-1]["did"])
print("  adjacent fleet lines sharing a DID: %d/%d = %.1f%%  (independent 6 operators ~ 16.7%%)"
      % (same, len(Fs)-1, 100.0*same/(len(Fs)-1)))
import datetime
def sec(t): return datetime.datetime.fromisoformat(t.replace("Z","+00:00")).timestamp()
gaps = sorted(sec(Fs[i]["ts"])-sec(Fs[i-1]["ts"]) for i in range(1,len(Fs)))
print("  median wall gap between consecutive fleet attests: %.2fs" % statistics.median(gaps))
print("  total per DID:", {d[-6:]: sum(1 for a in F if a['did']==d) for d in order})
