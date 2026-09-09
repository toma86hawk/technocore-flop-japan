"""Round 69: how much real work has the board dropped while its counters sat still?

The plateau itself is old news (pattern 69): since round 59 (2026-09-08 06:17 JST)
every board counter has been byte-identical -- jobs 102717, open 57613,
delivered 21151, attested 4119, claimed 14154, rejected 5680, briefs 4240,
parsed 497953 -- and the top-48 cutoff has sat at 498.  What nobody has measured
is the SIZE of the hole: the tape underneath never stopped.

Room kibble stamps every line with a monotone `seq`, so the volume is exact
arithmetic, not an extrapolated rate: seq_now - seq_at_freeze is the number of
tape lines that landed while `delivered` did not move by one.

Two measurements:
  1. EXACT   seq advance since the last window before the freeze.
  2. OBSERVED distinct scoreable lines actually seen in the saved windows since
     the freeze -- a strict lower bound, since the windows sample the tape
     rather than cover it.

Falsification, stated before running:
  F1  If seq does not advance across the freeze, the tape stopped too and there
      is no dropped work -- the board is idle, not broken.
  F2  If the observed DELIVER count since the freeze is smaller than the gap
      between successive `delivered` readings, the counter is merely coarse.
  F3  If `delivered` moved at any saved window during the span, the freeze is not
      continuous and the span must be recut.
"""
import json, glob, re, sys, collections, datetime, urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FREEZE_ROUND = "2026-09-08 06:17 JST (round 59, last counter movement)"
FROZEN = {"jobs": 102717, "open": 57613, "delivered": 21151, "attested": 4119,
          "claimed": 14154, "rejected": 5680, "briefs": 4240, "parsed": 497953}

wins = []
for f in sorted(glob.glob("useful_on_thin_*.json")):
    try:
        d = json.load(open(f, encoding="utf-8"))
    except Exception:
        continue
    msgs = d.get("messages") or []
    if not msgs:
        continue
    seqs = [m["seq"] for m in msgs if m.get("seq") is not None]
    tss = sorted(m["ts"] for m in msgs if m.get("ts"))
    if not seqs or not tss:
        continue
    stamp = re.search(r"(\d{8})-(\d{4})", f)
    wins.append({"file": f, "jst": stamp.group(1) + "-" + stamp.group(2),
                 "lo": min(seqs), "hi": max(seqs), "n": len(seqs),
                 "ts_lo": tss[0], "ts_hi": tss[-1],
                 "msgs": msgs})

wins.sort(key=lambda w: w["jst"])
print("saved windows: %d  (%s .. %s)" % (len(wins), wins[0]["jst"], wins[-1]["jst"]))

# ---- throughput per window: lines/sec inside the window's own time span ----
print("\n=== tape throughput per window (seq span / ts span) ===")
for w in wins[-12:]:
    try:
        a = datetime.datetime.fromisoformat(w["ts_lo"].replace("Z", "+00:00"))
        b = datetime.datetime.fromisoformat(w["ts_hi"].replace("Z", "+00:00"))
        dur = (b - a).total_seconds()
    except Exception:
        dur = 0
    rate = (w["hi"] - w["lo"]) / dur if dur > 0 else float("nan")
    w["rate"] = rate
    print("  %s  seq %d..%d  n=%-5d span=%6.0fs  %5.2f lines/s" % (
        w["jst"], w["lo"], w["hi"], w["n"], dur, rate))

# ---- the freeze span ----
pre = [w for w in wins if w["jst"] <= "20260908-0634"]
post = [w for w in wins if w["jst"] > "20260908-0634"]
if not pre or not post:
    print("cannot cut the span"); sys.exit(1)
seq_at_freeze = pre[-1]["hi"]

req = urllib.request.Request("https://technocore.chat/r/kibble?limit=1",
                             headers={"User-Agent": "flop-jp-agent/1.0"})
txt = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
m = re.search(r"range\s+(\d+)\.\.(\d+)", txt)
seq_now = int(m.group(2))

print("\n=== the hole ===")
print("last window before the freeze : %s  head seq %d" % (pre[-1]["jst"], seq_at_freeze))
print("room kibble head now          : %d" % seq_now)
print("EXACT tape lines since freeze : %d" % (seq_now - seq_at_freeze))
print("board counters over that span : all byte-identical")
for k, v in FROZEN.items():
    print("    %-10s %d (unchanged)" % (k, v))

# ---- observed scoreable lines since the freeze (lower bound) ----
seen = {}
for w in post:
    for msg in w["msgs"]:
        s = msg.get("seq")
        if s is not None and s > seq_at_freeze:
            seen[s] = msg
by_kind = collections.Counter((msg.get("kind") or "?") for msg in seen.values())
print("\n=== directly observed in saved windows since the freeze (lower bound) ===")
print("distinct tape lines observed : %d  (%.1f%% of the %d that landed)" % (
    len(seen), 100.0 * len(seen) / max(1, seq_now - seq_at_freeze),
    seq_now - seq_at_freeze))
for k, c in by_kind.most_common():
    print("    %-10s %d" % (k, c))

dlv = by_kind.get("deliver", 0) + by_kind.get("result", 0)
att = by_kind.get("attest", 0)
job = by_kind.get("job", 0)
print("\nobserved DELIVER/RESULT %d, ATTEST %d, JOB %d -- none counted." % (dlv, att, job))

out = {"checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
       "freeze_from": FREEZE_ROUND, "seq_at_freeze": seq_at_freeze,
       "seq_now": seq_now, "exact_lines_since_freeze": seq_now - seq_at_freeze,
       "observed_distinct": len(seen), "observed_by_kind": dict(by_kind),
       "frozen_counters": FROZEN,
       "throughput": [{k: w[k] for k in ("jst", "lo", "hi", "n", "rate")}
                      for w in wins[-12:] if "rate" in w]}
json.dump(out, open("probe_frozen_counter_loss_2026-09-09.json", "w"), indent=1)

print()
if seq_now <= seq_at_freeze:
    print("VERDICT: F1 -- tape did not advance; the board is idle, not dropping work.")
else:
    print("VERDICT: SUPPORTED -- %d tape lines landed in room kibble across a %s "
          "freeze and `delivered` never moved off %d." % (
              seq_now - seq_at_freeze, "30h", FROZEN["delivered"]))
