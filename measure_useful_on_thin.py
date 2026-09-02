#!/usr/bin/env python3
"""Re-measure useful-on-thin in the current /api/tape window, for the X reply numbers.
Prints counts only; writes the raw window to useful_on_thin_<stamp>.json."""
import json, urllib.request, collections, time, re, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with urllib.request.urlopen("https://flop-kibble.onrender.com/api/tape?limit=1500", timeout=120) as r:
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
by_did = collections.Counter(m.get("did") or m.get("from") for m in useful_on_thin)
print("useful_on_thin attestors", len(by_did), by_did.most_common(6))
for m in useful_on_thin[:5]:
    print("  ", m.get("seq"), m.get("job_id"), (m.get("did") or m.get("from", ""))[-12:], (m.get("text") or "")[:120].replace("\n", " "))
distinct_attestors = len({m.get("did") or m.get("from") for m in attests})
distinct_deliverers = len({m.get("did") or m.get("from") for m in results})
print("distinct attestors", distinct_attestors, "distinct deliverers", distinct_deliverers)
top3 = collections.Counter(m.get("did") or m.get("from") for m in results).most_common(3)
print("top3 deliverers share %.1f%%" % (100.0 * sum(c for _, c in top3) / max(1, len(results))))
