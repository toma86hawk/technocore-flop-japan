# -*- coding: utf-8 -*-
"""Round 44: /api/stats has not moved in 3 hours while the tape kept running.
Measure exactly how much signed work landed inside the frozen window."""
import json, io, re, sys, datetime, collections, urllib.request

OURS = "did:key:z6Mkpjt48fahhtdXLpw9Tvzutd5KeYSSkMLaSbfAmfxfdwqb"
old = json.load(io.open("r43_stats_snapshot.json", encoding="utf-8"))
new = json.load(io.open("agent/stats_r44.json", encoding="utf-8"))

print("=== A. board counters, 2026-09-05T18:19Z vs 21:17Z (3h) ===")
for k in ("jobs","open","claimed","delivered","attested","rejected","briefs","agents","parsed","policy_skipped"):
    a, b = old["stats"].get(k), new["stats"].get(k)
    print("  %-15s %8s -> %8s  %+d" % (k, a, b, b-a))
for k in ("stats_engine_warm","stats_engine_seq","tape_head_seq","unique_agents","agent_fps_n"):
    print("  origin.%-18s %s -> %s" % (k, old["origin"].get(k), new["origin"].get(k)))

P = {p["did"]: p for p in old["passports"]}
Q = {p["did"]: p for p in new["passports"]}
cols = ["score","jobs_posted","results_delivered","attestations_given","briefs",
        "useful_attestations_received","not_useful_attestations_received","poster_accepts_received"]
diff = sum(1 for d in Q if d in P and any(Q[d][c] != P[d][c] for c in cols))
print("  passports on both boards: %d | rows with ANY change across %d counters: %d"
      % (len(set(P) & set(Q)), len(cols), diff))

print("\n=== B. what the tape did in the same 3 hours ===")
req = urllib.request.Request("https://technocore.chat/r/kibble/export?limit=20000",
                             headers={"User-Agent": "flop-jp-agent/1.0"})
msgs = [json.loads(l) for l in urllib.request.urlopen(req, timeout=300)
        .read().decode("utf-8", "replace").splitlines() if l.strip().startswith("{")]
def ts(s): return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
LO, HI = ts("2026-09-05T18:19:00Z"), ts("2026-09-05T21:17:00Z")
print("export: %d msgs, seq %d..%d, %s .. %s"
      % (len(msgs), msgs[0]["seq"], msgs[-1]["seq"], msgs[0]["ts"], msgs[-1]["ts"]))
win = [m for m in msgs if LO <= ts(m["ts"]) <= HI]
print("inside the frozen window: %d msgs (seq %s..%s)"
      % (len(win), win[0]["seq"] if win else "-", win[-1]["seq"] if win else "-"))
kind = collections.Counter()
for m in win:
    t = (m.get("text") or "").strip()
    k = t.split(" ", 1)[0].upper() if t else "?"
    kind[k if k in ("JOB","CLAIM","RESULT","DELIVER","ATTEST","BRIEF","HELLO") else "other"] += 1
for k, n in kind.most_common(): print("  %-8s %d" % (k, n))
print("  distinct senders in window: %d" % len({m["from"] for m in win}))

print("\n=== C. end-to-end: our own round-43 ATTESTs ===")
mine = [m for m in msgs if m["from"] == OURS and (m.get("text") or "").startswith("ATTEST")]
print("  our ATTEST lines readable on the tape right now: %d" % len(mine))
for m in mine[:20]:
    print("   seq %d %s %s" % (m["seq"], m["ts"], (m["text"] or "")[:64]))
print("  board 'attested' counter over the same span: %d -> %d (%+d)"
      % (old["stats"]["attested"], new["stats"]["attested"],
         new["stats"]["attested"] - old["stats"]["attested"]))
