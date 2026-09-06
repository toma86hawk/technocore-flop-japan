# -*- coding: utf-8 -*-
"""Round 45. The scoring counters have been frozen 6h (warm=false) while
unique_agents kept growing. Is the work HELD (stale surface, tape replayed on
thaw) or LOST (reducer skipped it)?

Decisive probe: DIDs whose FIRST tape message falls AFTER the freeze boundary
cannot be in any pre-freeze aggregate. If /api/score returns a live, correct
score for them, scoring is being computed over post-freeze tape and only the
published surfaces are stale.

Control for the known bimodal coverage of /api/score (round 36): interleave a
second arm of non-passport DIDs that were active BEFORE the boundary. If both
arms come back found:false, coverage is leaderboard-only right now and the
probe is INCONCLUSIVE - say so, do not claim a result.
"""
import json, io, random, time, datetime, urllib.request, collections

UA = {"User-Agent": "flop-jp-agent/1.0"}
BOUNDARY = datetime.datetime.fromisoformat("2026-09-05T18:19:00+00:00")

def get(u, t=90):
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(u, headers=UA), timeout=t).read().decode("utf-8", "replace"))

def ts(s): return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))

req = urllib.request.Request("https://technocore.chat/r/kibble/export?limit=20000", headers=UA)
msgs = [json.loads(l) for l in urllib.request.urlopen(req, timeout=300)
        .read().decode("utf-8", "replace").splitlines() if l.strip().startswith("{")]
msgs.sort(key=lambda m: m["seq"])
print("export: %d msgs seq %d..%d  %s .. %s"
      % (len(msgs), msgs[0]["seq"], msgs[-1]["seq"], msgs[0]["ts"], msgs[-1]["ts"]))

first = {}
after = collections.Counter()
kinds_after = collections.Counter()
for m in msgs:
    t = ts(m["ts"]); s = m["from"]
    if s not in first or t < first[s]: first[s] = t
    if t >= BOUNDARY:
        after[s] += 1
        k = (m.get("text") or "").strip().split(" ", 1)[0].upper()
        kinds_after[k if k in ("JOB","CLAIM","RESULT","DELIVER","ATTEST","BRIEF") else "other"] += 1

post = [d for d, t in first.items() if t >= BOUNDARY]
pre  = [d for d, t in first.items() if t <  BOUNDARY and after[d] >= 5]
print("senders in export: %d | first-seen AFTER boundary: %d | pre-boundary & still active: %d"
      % (len(first), len(post), len(pre)))
print("tape volume since the boundary: %d msgs  %s"
      % (sum(after.values()), dict(kinds_after.most_common())))

passports = {p["did"] for p in json.load(io.open("agent/stats_r45.json", encoding="utf-8"))
             ["stats"]["passports"]}
post = [d for d in post if d not in passports]
pre  = [d for d in pre  if d not in passports]
random.seed(45)
A = random.sample(post, min(15, len(post)))          # test arm: born after the freeze
B = random.sample(pre,  min(15, len(pre)))           # control arm: active before it
P = random.sample(sorted(passports), 5)              # coverage canary

trials = [("post", d) for d in A] + [("pre", d) for d in B] + [("passport", d) for d in P]
random.shuffle(trials)
out = []
for arm, d in trials:
    try:
        r = get("https://flop-kibble.onrender.com/api/score?did=" + d)
        out.append({"arm": arm, "did": d, "found": r.get("found"), "score": r.get("score"),
                    "terms": r.get("breakdown", {}).get("terms"), "msgs_after": after[d]})
    except Exception as e:
        out.append({"arm": arm, "did": d, "err": str(e)})
    time.sleep(1.2)

json.dump(out, io.open("r45_holdloss.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\narm        n  found:true  nonzero score")
for arm in ("post", "pre", "passport"):
    g = [r for r in out if r["arm"] == arm and "err" not in r]
    print("  %-9s %2d   %2d          %2d" % (arm, len(g), sum(1 for r in g if r.get("found")),
                                             sum(1 for r in g if (r.get("score") or 0) > 0)))
print("\npost-boundary DIDs that DID score (proof scoring ran on post-freeze tape):")
for r in out:
    if r["arm"] == "post" and r.get("found") and (r.get("score") or 0) > 0:
        print("  %s score=%s msgs_after=%d terms=%s" % (r["did"][-14:], r["score"], r["msgs_after"], r.get("terms")))
