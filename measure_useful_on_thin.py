#!/usr/bin/env python3
"""Re-measure useful-on-thin in the current /api/tape window, for the X reply numbers.
Prints counts only; writes the raw window to useful_on_thin_<stamp>.json."""
import json, urllib.request, collections, time, re, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with urllib.request.urlopen("https://flop-kibble.onrender.com/api/tape?limit=1500", timeout=300) as r:
    d = json.loads(r.read().decode())
msgs = d.get("messages", [])
stamp = time.strftime("%Y%m%d-%H%M")
json.dump(d, open("useful_on_thin_%s.json" % stamp, "w"), indent=0)

seqs = [m.get("seq") for m in msgs if m.get("seq") is not None]
print("window: msgs", len(msgs), "seq", min(seqs), "-", max(seqs))
kinds = collections.Counter(m.get("kind") for m in msgs)
print("kinds", dict(kinds))

results = [m for m in msgs if m.get("kind") == "result"]
thin = [m for m in results if m.get("thin") is True and m.get("scored") is False]
thin_jobs = {m.get("job_id") for m in thin}
thin_dids = collections.Counter(m.get("did") or m.get("from") for m in thin)
print("results", len(results), "thin&unscored", len(thin), "(%.1f%%)" % (100.0 * len(thin) / max(1, len(results))))
print("thin DIDs", len(thin_dids), "top", thin_dids.most_common(3))

attests = [m for m in msgs if m.get("kind") == "attest"]
useful = [m for m in attests if str(m.get("verdict", "")).lower() == "useful"]
useful_on_thin = [m for m in useful if m.get("job_id") in thin_jobs]
print("attests", len(attests), "useful", len(useful), "useful_on_thin", len(useful_on_thin),
      "(%.1f%% of useful)" % (100.0 * len(useful_on_thin) / max(1, len(useful))))

# --- r175: never print the headline number without its ceiling beside it ---
# useful_on_thin is a JOIN inside THIS response: a useful verdict can only be
# counted if the result row of its job is also here.  join% is the ceiling that
# imposes, and it is a property of the response, not of any auditor.  Measured
# across 137 saved windows it fell 65.9% -> 22.0% while the headline fell
# 17.2% -> 7.8%, so the headline alone is not readable as a trend.
result_jobs = {m.get("job_id") for m in results}
joinable = [m for m in useful if m.get("job_id") in result_jobs]
join_pct = 100.0 * len(joinable) / max(1, len(useful))
cond_pct = (100.0 * len(useful_on_thin) / len(joinable)) if joinable else None
print("join%% (CEILING) %.1f%%  = %d of %d useful verdicts whose job's result row is in this response"
      % (join_pct, len(joinable), len(useful)))
print("conditional rate %s  = useful_on_thin among those that COULD join  <- the behavioural number"
      % ("n/a" if cond_pct is None else "%.1f%%" % cond_pct))
print("attests per result %.2f  (this is what moves the ceiling)"
      % (len(attests) / float(max(1, len(results)))))
assert len(useful_on_thin) <= len(joinable), "bound violated - the join logic changed"

by_did = collections.Counter(m.get("did") or m.get("from") for m in useful_on_thin)
print("useful_on_thin attestors", len(by_did), by_did.most_common(6))
for m in useful_on_thin[:5]:
    print("  ", m.get("seq"), m.get("job_id"), (m.get("did") or m.get("from", ""))[-12:], (m.get("text") or "")[:120].replace("\n", " "))
distinct_attestors = len({m.get("did") or m.get("from") for m in attests})
distinct_deliverers = len({m.get("did") or m.get("from") for m in results})
print("distinct attestors", distinct_attestors, "distinct deliverers", distinct_deliverers)
top3 = collections.Counter(m.get("did") or m.get("from") for m in results).most_common(3)
print("top3 deliverers share %.1f%%" % (100.0 * sum(c for _, c in top3) / max(1, len(results))))
