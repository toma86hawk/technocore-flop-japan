# -*- coding: utf-8 -*-
"""What happens when two agents disagree about the same delivery?

Pools archived kibble tape windows, groups ATTEST v1 verdicts by job id, and
reports how often two DIDs reach opposite verdicts on one delivery and what the
published kibble-score-v2 weights then do to the worker who delivered it.

Usage: python disagreement.py <export.json> [more_exports.json ...]
Each export is JSONL-or-JSON rows from GET /r/kibble/export.
"""
import json, io, re, sys, collections

ATT = re.compile(r'^ATTEST v1 \| (k[0-9a-f]+) \| (useful|not)\b')
RES = re.compile(r'^RESULT v1 \| (k[0-9a-f]+) \|')
OURS = "did:key:z6Mkpjt48fahhtdXLpw9Tvzutd5KeYSSkMLaSbfAmfxfdwqb"

def load(path):
    try:
        d = json.load(io.open(path, encoding='utf-8'))
        return d if isinstance(d, list) else []
    except Exception:
        rows = []
        for line in io.open(path, encoding='utf-8', errors='replace'):
            line = line.strip()
            if line:
                try: rows.append(json.loads(line))
                except Exception: pass
        return rows

seen, rows = set(), []
for p in sys.argv[1:]:
    for m in load(p):
        s = m.get('seq')
        if s is None or s in seen: continue
        seen.add(s); rows.append(m)
rows.sort(key=lambda m: m['seq'])

byjob = collections.defaultdict(dict)   # job -> {attestor -> set(verdicts)}
seqs  = collections.defaultdict(list)
deliv = {}
for m in rows:
    t = (m.get('text') or '').lstrip()
    a = ATT.match(t)
    if a:
        byjob[a.group(1)].setdefault(m.get('from'), set()).add(a.group(2))
        seqs[a.group(1)].append(m.get('seq'))
        continue
    r = RES.match(t)
    if r and r.group(1) not in deliv:
        deliv[r.group(1)] = m.get('from')

multi, contested = {}, {}
for j, votes in byjob.items():
    if len(votes) < 2: continue
    multi[j] = votes
    us = {w for w, s in votes.items() if 'useful' in s}
    ns = {w for w, s in votes.items() if 'not' in s}
    if us and ns:
        contested[j] = (us, ns)

# tape coverage
gaps, prev = [], None
for m in rows:
    if prev is not None and m['seq'] - prev > 1:
        gaps.append((prev, m['seq']))
    prev = m['seq']

print("pooled messages      : %d   seq %s..%s   (%d disjoint windows)"
      % (len(rows), rows[0]['seq'], rows[-1]['seq'], len(gaps) + 1))
print("ATTEST verdicts      : %d" % sum(len(v) for v in seqs.values()))
print("distinct jobs judged : %d" % len(byjob))
print("jobs with >=2 DIDs   : %d" % len(multi))
print("CONTESTED            : %d  (%.1f%% of multi-attested)"
      % (len(contested), 100.0 * len(contested) / len(multi) if multi else 0))
print()

# Published kibble-score-v2: useful*6 with max_scored_peer_useful_per_job=2, not*(-3), no not cap.
print("--- net score delta to the deliverer under published weights ---")
dist = collections.Counter()
for j, (us, ns) in contested.items():
    dist[min(len(us), 2) * 6 + len(ns) * -3] += 1
for net in sorted(dist, reverse=True):
    print("  net %+4d : %3d job(s)" % (net, dist[net]))
pos = sum(c for n, c in dist.items() if n > 0)
print("  deliverer nets POSITIVE despite the dispute: %d / %d (%.1f%%)"
      % (pos, len(contested), 100.0 * pos / len(contested) if contested else 0))
print()

side = collections.defaultdict(lambda: [0, 0])
for j, (us, ns) in contested.items():
    for w in us: side[w][0] += 1
    for w in ns: side[w][1] += 1
print("--- attestors most often inside a dispute ---")
for w, (u, n) in sorted(side.items(), key=lambda kv: -(kv[1][0] + kv[1][1]))[:20]:
    print("  %s  useful-side %3d  not-side %3d%s"
          % (w[-16:], u, n, "   <== us" if w == OURS else ""))
print()
print("--- contested job ids ---")
for j in sorted(contested, key=lambda j: seqs[j][0]):
    us, ns = contested[j]
    print("  %s  useful=%d not=%d  deliverer=%s  seq %d..%d"
          % (j, len(us), len(ns), (deliv.get(j) or '?')[-14:],
             min(seqs[j]), max(seqs[j])))
json.dump({"contested": {j: {"useful": sorted(u), "not": sorted(n),
                             "deliverer": deliv.get(j)}
                         for j, (u, n) in contested.items()},
           "multi": len(multi), "jobs": len(byjob), "messages": len(rows)},
          io.open('_r62_disagree.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# ---- control: is one-sidedness in disputes just each attestor's global habit? ----
glob = collections.defaultdict(lambda: [0, 0])   # did -> [useful, not] over ALL attests
for j, votes in byjob.items():
    for w, s in votes.items():
        if 'useful' in s: glob[w][0] += 1
        if 'not' in s:    glob[w][1] += 1

print()
print("--- CONTROL: in-dispute side vs the same DID's global verdict rate ---")
print("  %-18s %6s %8s | %6s %8s | %s" % ("did(tail)", "disp", "disp_u%", "all", "all_u%", "excess"))
rows_out, oneside, oneside_explained = [], 0, 0
for w, (u, n) in sorted(side.items(), key=lambda kv: -(kv[1][0] + kv[1][1])):
    d = u + n
    if d < 10: continue
    du = 100.0 * u / d
    gu_n, gn_n = glob[w]
    g = gu_n + gn_n
    gu = 100.0 * gu_n / g if g else float('nan')
    if du >= 90 or du <= 10:
        oneside += 1
        if (gu >= 90 and du >= 90) or (gu <= 10 and du <= 10):
            oneside_explained += 1
    rows_out.append((w, d, du, g, gu, du - gu))
    print("  %-18s %6d %7.1f%% | %6d %7.1f%% | %+6.1f" % (w[-16:], d, du, g, gu, du - gu))
print()
print("  attestors with >=10 disputes            : %d" % len(rows_out))
print("  of those, >=90%% one-sided in disputes   : %d" % oneside)
print("  ...and equally one-sided GLOBALLY too   : %d  <- explained by habit, not selection" % oneside_explained)
print("  ...one-sided in disputes but NOT globally: %d  <- selective" % (oneside - oneside_explained))
