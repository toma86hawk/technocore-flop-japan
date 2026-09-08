# -*- coding: utf-8 -*-
"""Measure the exact-byte clone ring in the current window.

Round 56 identified the ring by cross-key pools (pattern 79). This measures the
per-key structure instead: how many deliveries each key makes, how many distinct
bodies it owns, and therefore how many jobs one written answer is serving.

reuse factor = deliveries / distinct bodies. A key that writes one answer and
sends it to 400 jobs has reuse 400 and is indistinguishable, on the board, from
400 separate results because each carries a different result_hash.
"""
import json, collections

Q = json.load(open("attest_queue_offboard.json", encoding="utf-8"))
byw = collections.defaultdict(list)
for x in Q:
    byw[x["worker"]].append(x)

rows = []
for w, items in byw.items():
    bodies = collections.Counter(i["result"].strip() for i in items)
    rows.append({
        "worker": w,
        "deliveries": len(items),
        "distinct_bodies": len(bodies),
        "reuse": round(len(items) / len(bodies), 2),
        "top_body_n": bodies.most_common(1)[0][1],
        "top_body": bodies.most_common(1)[0][0][:200],
        "cloned_deliveries": sum(n for _, n in bodies.items() if n > 1),
    })
rows.sort(key=lambda r: -r["cloned_deliveries"])

tot = len(Q)
cl = sum(r["cloned_deliveries"] for r in rows)
print("window deliveries        : %d across %d keys" % (tot, len(byw)))
print("deliveries whose exact bytes appear >=2x from the SAME key: %d (%.1f%%)"
      % (cl, 100.0 * cl / tot))
print()
print("%-24s %6s %8s %7s %8s" % ("key", "deliv", "distinct", "reuse", "cloned"))
for r in rows[:12]:
    print("%-24s %6d %8d %7.2f %8d"
          % (r["worker"][-24:], r["deliveries"], r["distinct_bodies"], r["reuse"], r["cloned_deliveries"]))
print()
for r in rows[:5]:
    print("--- %s  reuse %.1f  most-reused body sent to %d jobs:"
          % (r["worker"][-22:], r["reuse"], r["top_body_n"]))
    print("    %s" % r["top_body"].replace("\n", " "))
json.dump(rows, open("_r60_clone_pool.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# cross-key: is one body shared by MORE THAN ONE key (the round-56 ring)?
owners = collections.defaultdict(set)
for x in Q:
    owners[x["result"].strip()].add(x["worker"])
shared = {b: k for b, k in owners.items() if len(k) > 1}
n_shared_deliv = sum(1 for x in Q if x["result"].strip() in shared)
print()
print("bodies posted by MORE THAN ONE key: %d, covering %d deliveries (%.1f%%)"
      % (len(shared), n_shared_deliv, 100.0 * n_shared_deliv / tot))
allkeys = set()
for b, k in shared.items():
    allkeys |= k
print("keys participating in cross-key pools:", len(allkeys))
