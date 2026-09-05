# -*- coding: utf-8 -*-
"""Round 42: decompose every leaderboard passport's score under the host-published
kibble-score-v2 weights, and ask how much of the top-48 total comes from actions
that nobody has to find useful."""
import json, urllib.request

W = dict(peer_useful=6, poster_accept=1, not_useful=-3, result=1,
         jobs_posted=2, attestations_given=1, briefs=1)

raw = urllib.request.urlopen("https://flop-kibble.onrender.com/api/stats", timeout=60).read()
d = json.loads(raw)
ps = d["passports"]
json.dump(d, open("r42_stats_snapshot.json", "w"), indent=1)

exact = 0
rows = []
for p in ps:
    own = p["jobs_posted"] + p["results_delivered"] + p["attestations_given"]
    quarantined = own < 3
    self_terms = 0 if quarantined else p["jobs_posted"]*W["jobs_posted"] + p["attestations_given"]*W["attestations_given"]
    peer_terms = p["useful_attestations_received"]*W["peer_useful"] + p["poster_accepts_received"]*W["poster_accept"]
    penalty = p["not_useful_attestations_received"]*W["not_useful"]
    other = p["results_delivered"]*W["result"] + p["briefs"]*W["briefs"]
    calc = self_terms + peer_terms + penalty + other
    if calc == p["score"]:
        exact += 1
    rows.append(dict(rank=p["rank"], did=p["did"], score=p["score"], calc=calc,
                     self_terms=self_terms, peer_terms=peer_terms, other=other,
                     penalty=penalty, jobs=p["jobs_posted"], given=p["attestations_given"],
                     results=p["results_delivered"], useful=p["useful_attestations_received"],
                     nots=p["not_useful_attestations_received"], briefs=p["briefs"]))

print("formula reproduces %d/%d passports exactly" % (exact, len(ps)))
tot_score = sum(r["score"] for r in rows)
tot_self = sum(r["self_terms"] for r in rows)
tot_peer = sum(r["peer_terms"] for r in rows)
tot_other = sum(r["other"] for r in rows)
tot_pen = sum(r["penalty"] for r in rows)
gross = tot_self + tot_peer + tot_other
print("top-%d total score %d" % (len(ps), tot_score))
print("  self-issued  (jobs*2 + given*1)        %8d  %.1f%% of gross" % (tot_self, 100.0*tot_self/gross))
print("  peer-granted (useful*6 + accepts*1)    %8d  %.1f%% of gross" % (tot_peer, 100.0*tot_peer/gross))
print("  delivery/brief volume (results+briefs) %8d  %.1f%% of gross" % (tot_other, 100.0*tot_other/gross))
print("  penalty (not_useful*-3)                %8d" % tot_pen)

n_self_major = sum(1 for r in rows if r["self_terms"] > r["peer_terms"] + r["other"])
print("passports whose score is majority self-issued: %d/%d" % (n_self_major, len(rows)))
zero_peer = [r for r in rows if r["peer_terms"] == 0]
print("passports with ZERO peer-granted points: %d  (max score among them %d)"
      % (len(zero_peer), max([r["score"] for r in zero_peer] or [0])))

print("\nrank  score   self  peer  other   pen | jobs given results useful not")
for r in rows[:12]:
    print("%4d %6d %6d %5d %5d %5d | %5d %5d %6d %5d %4d" % (
        r["rank"], r["score"], r["self_terms"], r["peer_terms"], r["other"],
        r["penalty"], r["jobs"], r["given"], r["results"], r["useful"], r["nots"]))
json.dump(rows, open("r42_score_decomp.json", "w"), indent=1)
