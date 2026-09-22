#!/usr/bin/env python3
"""Re-measure useful-on-thin in the current /api/tape window, for the X reply numbers.
Prints counts only; writes the raw window to useful_on_thin_<stamp>.json."""
import json, urllib.request, collections, time, re, sys, os, statistics
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# r178: this fetch had no handler. On 2026-09-22 /api/tape?limit=1500 answered
# 502 after ~78 s, the script died on its first line, and three invocations that
# printed nothing were read as "the tool emits nothing" before the endpoint was
# probed directly. A measurement tool must say which of its dependencies failed
# and must not exit 0 when it produced no series point.
URL = "https://flop-kibble.onrender.com/api/tape?limit=1500"
try:
    with urllib.request.urlopen(URL, timeout=300) as r:
        d = json.loads(r.read().decode())
except Exception as e:
    print("NO SERIES POINT: %s is unreadable - %s: %s"
          % (URL, type(e).__name__, str(e)[:200]))
    print("This is an upstream failure, not a result. Do not record a gap in "
          "useful_on_thin_series without naming this cause.")
    sys.exit(3)
msgs = d.get("messages", [])
stamp = time.strftime("%Y%m%d-%H%M")
json.dump(d, open("useful_on_thin_%s.json" % stamp, "w"), indent=0)

seqs = [m.get("seq") for m in msgs if m.get("seq") is not None]
print("window: msgs", len(msgs), "seq", min(seqs), "-", max(seqs))

# --- r176 GUARD: certify the response shape before the numbers are read. ---
# Every point in useful_on_thin_series since 2026-08-31 assumed /api/tape?limit=1500
# returns the newest rows.  r175 checked that by asking whether seq_hi advanced,
# which constrains only the newest row in the response.  On 2026-09-22 the tape's
# ordinal RESET: the 12:32Z response held 1,000 rows at seq 400..1393 carrying
# timestamps 11:30:30Z..12:17:14Z - current traffic at low seq, with seq 400
# appearing seven times - while /api/stats still reported tape_head_seq 9,997,001.
# Test the BULK (median), not an extreme: a statistic resting on min or max is set
# by one stray row, which is how the first draft of the certificate tool condemned
# 13 good responses.
import glob as _glob
bulk = statistics.median(seqs)
prev = sorted(_glob.glob("useful_on_thin_*.json"), key=os.path.getmtime)[:-1]
prev_bulk = None
if prev:
    try:
        _p = [m["seq"] for m in json.load(open(prev[-1]))["messages"] if m.get("seq") is not None]
        prev_bulk = statistics.median(_p)
    except Exception:
        pass
print("bulk (median seq) %d   previous response bulk %s" % (bulk, prev_bulk))
CERTIFIED = True
if prev_bulk and bulk < 0.5 * prev_bulk:
    CERTIFIED = False
    print("*** TAPE ORDINAL RESET - the bulk fell from %d to %d. ***" % (prev_bulk, bulk))
    print("*** This response's seq cannot be compared with earlier points. ***")
dups = len(seqs) - len(set(seqs))
if dups:
    CERTIFIED = False
    print("*** %d duplicate seq values in one response - seq is not unique here. ***" % dups)
print("certified as a comparable series point: %s" % CERTIFIED)
if not CERTIFIED:
    print("*** DO NOT append the numbers below to useful_on_thin_series. ***")

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
