#!/usr/bin/env python3
"""Round 24 probe: is the trailing `[Ref:<6 hex>]` suffix a cross-DID fleet marker?

Spotted in the 2026-09-03 15:02 board window: 27 of 58 reviewable deliveries,
from 11 different DIDs, end with `[Ref:` + six lowercase hex + `]`, and all 27
ref values are distinct. Distinct values rule out the constant-paste pattern we
already catalogued, and cross-DID spread rules out one agent's house style.

IMPORTANT surface note (measured this round): /api/tape truncates RESULT bodies
to ~260 characters, so the marker - which sits at the very end - is invisible
there and a tape-based scan returns a false zero. Only /api/board carries the
untruncated body. This scans every board snapshot under attest_runs/.

Falsification attempts:
  1. cross-DID, or a handful of agents?
  2. do marked deliveries differ from unmarked on length / truncation / the
     host's own `thin` flag?
  3. is the marker stable over time, or a one-window artefact?

Truncation proxy: the character before the marker is not sentence-terminal
punctuation. Reported separately from the hard counts because it is a proxy.
"""
import json, re, sys, glob, os, collections

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MARK = re.compile(r"\[Ref:([0-9a-f]{6})\]\s*$")


def pairs(snap):
    """attest_collect snapshots are either a list of pairs or {'pairs': [...]}."""
    if isinstance(snap, dict):
        for k in ("pairs", "queue", "items", "jobs"):
            if isinstance(snap.get(k), list):
                return snap[k]
        return []
    return snap if isinstance(snap, list) else []


def field(p, *names):
    for n in names:
        v = p.get(n)
        if isinstance(v, str) and v:
            return v
    return ""


rows = []
for f in sorted(glob.glob("attest_runs/*.json")):
    try:
        snap = json.load(open(f, encoding="utf-8"))
    except Exception as e:                                    # noqa: BLE001
        print("skip %s (%r)" % (f, e)); continue
    ps = pairs(snap)
    seen = {}
    for p in ps:
        if not isinstance(p, dict):
            continue
        jid = field(p, "job_id", "id")
        res = field(p, "result", "body", "text")
        did = field(p, "worker", "worker_did", "did")
        if jid and res:
            seen[jid] = (res, did)
    if not seen:
        continue
    marked = {j: v for j, v in seen.items() if MARK.search(v[0].rstrip())}
    rows.append((os.path.basename(f)[:-5], len(seen), marked, seen))

print("%-22s %6s %8s %7s %7s" % ("board snapshot", "pairs", "marked", "share", "DIDs"))
allmarked, allplain, alldids, allrefs = {}, {}, collections.Counter(), []
for name, n, marked, seen in rows:
    dids = {v[1] for v in marked.values()}
    print("%-22s %6d %8d %6.1f%% %7d" % (name, n, len(marked), 100.0 * len(marked) / n, len(dids)))
    for j, v in seen.items():
        (allmarked if j in marked else allplain)[j] = v
    for j, v in marked.items():
        alldids[v[1]] += 1
        allrefs.append(MARK.search(v[0].rstrip()).group(1))

plaindids = collections.Counter(v[1] for v in allplain.values())
print()
print("UNION over all snapshots (deduped by job_id)")
print("  deliveries          %d   marked %d (%.1f%%)"
      % (len(allmarked) + len(allplain), len(allmarked),
         100.0 * len(allmarked) / max(1, len(allmarked) + len(allplain))))
print("  distinct DIDs emitting a marked delivery: %d" % len(alldids))
print("  distinct ref values: %d of %d marked deliveries" % (len(set(allrefs)), len(allrefs)))
only = [d for d in alldids if d not in plaindids]
both = [d for d in alldids if d in plaindids]
print("  DIDs that emit ONLY marked deliveries: %d" % len(only))
print("  DIDs that emit both marked and plain : %d" % len(both))


def avg(xs):
    xs = list(xs)
    return round(sum(xs) / len(xs)) if xs else 0


def trunc(vals):
    n = 0
    for v in vals:
        b = MARK.sub("", v[0]).rstrip()
        if b and b[-1] not in ".!?\"')]":
            n += 1
    return n, 100.0 * n / max(1, len(vals))


print("  avg body length     marked %d   plain %d"
      % (avg(len(v[0]) for v in allmarked.values()),
         avg(len(v[0]) for v in allplain.values())))
tm, tmp = trunc(list(allmarked.values()))
tp, tpp = trunc(list(allplain.values()))
print("  ends without terminal punctuation (truncation proxy):")
print("      marked %d/%d (%.1f%%)   plain %d/%d (%.1f%%)"
      % (tm, len(allmarked), tmp, tp, len(allplain), tpp))
print()
print("top marked emitters (marked / plain from the same DID):")
for d, c in alldids.most_common(20):
    print("   %3d / %-3d  %s" % (c, plaindids.get(d, 0), d))

json.dump({"deliveries": len(allmarked) + len(allplain),
           "marked": len(allmarked),
           "marked_dids": len(alldids),
           "distinct_refs": len(set(allrefs)),
           "marked_only_dids": only,
           "mixed_dids": both,
           "per_snapshot": [(n, c, len(m)) for n, c, m, _ in rows],
           "emitters": alldids.most_common()},
          open("r24_refmarker.json", "w"), indent=1)
print("\nwrote r24_refmarker.json")
