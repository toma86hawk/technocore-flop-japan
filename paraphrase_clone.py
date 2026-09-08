# -*- coding: utf-8 -*-
"""Detect constant-paste deliveries that ROTATE WORDING to defeat byte-identity.

Round 56/57 catalogued the clone ring by exact bytes (pattern 79: a shared
answer dictionary). This asks the next question: does any key reuse ONE answer
across unrelated jobs while paraphrasing it just enough that a byte hash, or
the result_hash the board itself keys on, differs every time?

Method: per delivering DID, compare every pair of its deliveries by Jaccard
similarity over 5-word shingles of the lowercased, punctuation-stripped body.
A pair is a PARAPHRASE CLONE if sim >= 0.55 while the raw bytes differ AND the
two jobs' titles share < 0.5 similarity (i.e. they are not the same question
asked twice). Exact-byte pairs are counted separately as the known baseline.
"""
import json, re, collections, itertools, sys

Q = json.load(open("attest_queue_offboard.json", encoding="utf-8"))
WORD = re.compile(r"[a-z0-9]+")

def shingles(text, n=5):
    w = WORD.findall(text.lower())
    if len(w) < n: return set()
    return {" ".join(w[i:i+n]) for i in range(len(w)-n+1)}

def jac(a, b):
    if not a or not b: return 0.0
    return len(a & b) / len(a | b)

byw = collections.defaultdict(list)
for x in Q:
    byw[x["worker"]].append(x)

exact_pairs = para_pairs = 0
exact_keys, para_keys = set(), set()
rows = []
para_deliveries = set()
for w, items in byw.items():
    if len(items) < 2: continue
    items = items[:120]              # bound the O(n^2)
    sh = [shingles(i["result"]) for i in items]
    th = [shingles(i["title"], 3) for i in items]
    for a, b in itertools.combinations(range(len(items)), 2):
        ia, ib = items[a], items[b]
        if ia["job_id"] == ib["job_id"]: continue
        same_bytes = ia["result"].strip() == ib["result"].strip()
        ts = jac(th[a], th[b])
        bs = jac(sh[a], sh[b])
        if same_bytes:
            exact_pairs += 1; exact_keys.add(w)
        elif bs >= 0.55 and ts < 0.5:
            para_pairs += 1; para_keys.add(w)
            para_deliveries.add(ia["job_id"]); para_deliveries.add(ib["job_id"])
            rows.append({"worker": w, "sim_body": round(bs, 3), "sim_title": round(ts, 3),
                         "rh_a": ia["rh"], "rh_b": ib["rh"],
                         "job_a": ia["job_id"], "job_b": ib["job_id"],
                         "title_a": ia["title"], "title_b": ib["title"],
                         "body_a": ia["result"][:400], "body_b": ib["result"][:400]})

rows.sort(key=lambda r: -r["sim_body"])
json.dump(rows, open("_r60_para.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("deliveries in queue      :", len(Q))
print("distinct delivering keys :", len(byw))
print("EXACT-byte clone pairs   : %d across %d keys" % (exact_pairs, len(exact_keys)))
print("PARAPHRASE clone pairs   : %d across %d keys" % (para_pairs, len(para_keys)))
print("deliveries touched by paraphrase clones:", len(para_deliveries))
print()
kc = collections.Counter(r["worker"] for r in rows)
for w, n in kc.most_common(12):
    print("  %-22s %4d pairs" % (w[-22:], n))
print()
for r in rows[:8]:
    print("--- sim_body=%.3f sim_title=%.3f  %s" % (r["sim_body"], r["sim_title"], r["worker"][-18:]))
    print("  A %s rh=%s | %s" % (r["job_a"], r["rh_a"], r["title_a"][:90]))
    print("    %s" % r["body_a"][:230].replace("\n", " "))
    print("  B %s rh=%s | %s" % (r["job_b"], r["rh_b"], r["title_b"][:90]))
    print("    %s" % r["body_b"][:230].replace("\n", " "))
