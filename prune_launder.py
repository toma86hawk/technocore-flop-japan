"""Measure whether recomputes of the kibble leaderboard drop negative evidence
faster than positive evidence, in POINTS, per DID.

kibble-score-v2 pays not_useful_received -3 and results_delivered +1. If a
recompute prunes a DID's older tape rows, both counters fall - but the -3 term
falls 3x harder per row, so pruning can RAISE a score with no new work.

Usage: python prune_launder.py <older_stats.json> <newer_stats.json>
"""
import json, io, sys

W = dict(useful=6, accept=1, notu=-3, result=1, jobs=2, given=1, briefs=1)

def load(f):
    return {p["did"]: p for p in json.load(io.open(f, encoding="utf-8-sig"))["passports"]}

def v2(p):
    own = p["attestations_given"] + p["results_delivered"] + p["jobs_posted"]
    s = (p["useful_attestations_received"] * W["useful"]
         + p["poster_accepts_received"] * W["accept"]
         + p["not_useful_attestations_received"] * W["notu"]
         + p["results_delivered"] * W["result"]
         + p["briefs"] * W["briefs"])
    if own >= W["given"] + 2:  # quarantine_own_actions = 3
        s += p["jobs_posted"] * W["jobs"] + p["attestations_given"] * W["given"]
    return max(0, s)

a, b = load(sys.argv[1]), load(sys.argv[2])
rows, tot_pruned_notu, tot_pruned_res, tot_laundered = [], 0, 0, 0
for did, p in b.items():
    q = a.get(did)
    if not q:
        continue
    d_notu = p["not_useful_attestations_received"] - q["not_useful_attestations_received"]
    d_res = p["results_delivered"] - q["results_delivered"]
    if d_notu >= 0 and d_res >= 0:
        continue                      # nothing pruned for this DID
    laundered = (-min(0, d_notu)) * 3 + min(0, d_res) * 1   # points gained from pruning
    tot_pruned_notu += -min(0, d_notu)
    tot_pruned_res += -min(0, d_res)
    tot_laundered += laundered
    rows.append(dict(did=did, rank_old=q["rank"], rank_new=p["rank"],
                     score_old=q["score"], score_new=p["score"],
                     d_score=p["score"] - q["score"],
                     d_not_useful=d_notu, d_results=d_res,
                     d_given=p["attestations_given"] - q["attestations_given"],
                     d_jobs=p["jobs_posted"] - q["jobs_posted"],
                     points_from_pruning=laundered))

rows.sort(key=lambda r: -r["points_from_pruning"])
print(f"compared {sys.argv[1]} -> {sys.argv[2]}   DIDs in both: {len(set(a)&set(b))}")
print(f"DIDs with pruned evidence: {len(rows)}")
print(f"not_useful rows dropped: {tot_pruned_notu}   result rows dropped: {tot_pruned_res}")
print(f"net points handed out by pruning alone: {tot_laundered:+d}")
print()
print(f"{'rank':>9} {'did':>12} {'dscore':>7} {'d_not':>6} {'d_res':>6} {'d_given':>8} {'prune_pts':>10}")
for r in rows:
    print(f"{r['rank_old']:>4}->{r['rank_new']:<4} {r['did'][-12:]:>12} {r['d_score']:>+7} "
          f"{r['d_not_useful']:>+6} {r['d_results']:>+6} {r['d_given']:>+8} {r['points_from_pruning']:>+10}")
print()
mism = [d for d in b if v2(b[d]) != b[d]["score"]]
print(f"v2 formula check on newer file: {len(b)-len(mism)}/{len(b)} exact")
