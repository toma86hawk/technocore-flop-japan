# -*- coding: utf-8 -*-
"""Do distinct attestor DIDs draw useful-verdict reasons from ONE shared pool?
Runs against the pinned snapshot only (export window moves ~280 msg/min)."""
import json, re, sys, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

M = json.load(open("r39_export.json"))
print("snapshot", len(M), "seq", M[0]["seq"], "-", M[-1]["seq"], M[0]["ts"], "-", M[-1]["ts"])

AT = re.compile(r"^ATTEST\s+v1\s*\|\s*(\S+)\s*\|\s*(\w+)\s*\|(.*)$", re.S)
att = []
for m in M:
    t = (m.get("text") or "").strip()
    g = AT.match(t)
    if not g:
        continue
    job, verdict, rest = g.group(1), g.group(2).lower(), g.group(3)
    rest = rest.strip()
    rh = None
    if rest.startswith("rh:"):
        parts = rest.split("|", 1)
        rh = parts[0][3:].strip()
        rest = parts[1].strip() if len(parts) > 1 else ""
    att.append(dict(seq=m["seq"], did=m.get("from"), job=job, verdict=verdict,
                    rh=rh, reason=rest, ts=m.get("ts")))
print("ATTEST lines", len(att), collections.Counter(a["verdict"] for a in att))

useful = [a for a in att if a["verdict"] == "useful"]
print("useful", len(useful), "distinct attestors", len({a['did'] for a in useful}))

# --- exact reason string shared across DIFFERENT attestor DIDs ---
by_reason = collections.defaultdict(set)
rows_by_reason = collections.defaultdict(list)
for a in useful:
    if len(a["reason"]) < 25:
        continue
    by_reason[a["reason"]].add(a["did"])
    rows_by_reason[a["reason"]].append(a)

shared = {r: d for r, d in by_reason.items() if len(d) > 1}
print("\n=== reason strings used by MORE THAN ONE attestor DID ===")
print("distinct such strings:", len(shared))
rows_in_shared = sum(len(rows_by_reason[r]) for r in shared)
print("useful lines carrying one:", rows_in_shared, "= %.1f%% of all useful" % (100.0*rows_in_shared/max(1,len(useful))))
dids_in_shared = set()
for r in shared:
    dids_in_shared |= shared[r]
print("distinct DIDs involved:", len(dids_in_shared))

for r, d in sorted(shared.items(), key=lambda kv: -len(rows_by_reason[kv[0]]))[:10]:
    rws = rows_by_reason[r]
    print("\n  x%-3d dids=%-2d jobs=%-3d | %s" % (len(rws), len(d), len({x['job'] for x in rws}), r[:105]))
    for dd in sorted(d)[:6]:
        print("        ", dd[-14:], sum(1 for x in rws if x["did"] == dd))

# --- connected components over (attestor, reason) bipartite graph ---
parent = {}
def find(x):
    parent.setdefault(x, x)
    while parent[x] != x:
        parent[x] = parent[parent[x]]; x = parent[x]
    return x
def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb: parent[ra] = rb
for r, d in shared.items():
    ds = sorted(d)
    for x in ds[1:]:
        union(ds[0], x)
comp = collections.defaultdict(set)
for x in list(parent):
    comp[find(x)].add(x)
comps = sorted(comp.values(), key=len, reverse=True)
print("\n=== attestor clusters linked by a shared reason string ===")
for i, c in enumerate(comps[:5]):
    lines = [a for a in useful if a["did"] in c]
    strs = {a["reason"] for a in lines}
    print(" cluster %d: %d DIDs, %d useful lines, %d distinct reason strings, %d distinct jobs"
          % (i+1, len(c), len(lines), len(strs), len({a['job'] for a in lines})))
    for dd in sorted(c):
        n = sum(1 for a in lines if a["did"] == dd)
        print("      ", dd[-14:], "useful=%d" % n)

# --- do those clusters land on thin deliveries? ---
res = [m for m in M if (m.get("text") or "").startswith("RESULT v1")]
def jobof(t):
    p = t.split("|")
    return p[1].strip() if len(p) > 1 else None
body = {}
for m in res:
    t = m["text"]; j = jobof(t)
    b = t.split("|", 2)[2].strip() if t.count("|") >= 2 else ""
    body.setdefault(j, []).append((m.get("from"), b))
print("\nRESULT lines in snapshot", len(res), "distinct jobs", len(body))
if comps:
    big = comps[0]
    lines = [a for a in useful if a["did"] in big]
    thinish = sum(1 for a in lines for (_w, b) in body.get(a["job"], []) if len(b) < 180)
    have = sum(1 for a in lines if a["job"] in body)
    print("cluster-1 useful lines whose job has a RESULT in snapshot:", have)
    print("   ...of which the delivered body is under 180 chars:", thinish)
    norh = sum(1 for a in lines if not a["rh"])
    print("cluster-1 useful lines with NO rh (uncredited by the board):", norh, "/", len(lines))
