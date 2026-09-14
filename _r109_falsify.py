#!/usr/bin/env python3
"""Round 109: fire our OWN standing falsifier on pattern 109.

Round 108 published: "since ~2026-09-13T17:00Z the referee accepts gated
registrations/ballots without adding them to sonnet.identities.v1; 2,831 of
3,610 currently-voting DIDs (78.4%) are unbacked", with this falsifier:

  "if a later sonnet.identities.v1 batch covers the DIDs reported missing,
   this is publication lag and NOT a gate failure. Re-run and say so."

The naive re-run is CONFOUNDED: mb-sonnet-2-votes truncates, so today's window
holds a different (smaller) voter set. The only clean test is to take the EXACT
DIDs we named unbacked at round 108 - from the round-108 export saved on disk -
and ask whether TODAY's roster covers them.
"""
import json, datetime, urllib.request, collections

BASE = "https://technocore.chat"
UA = {"User-Agent": "flop-sonnet2-falsifier/1.0"}
REFEREE = "did:key:z6MkowHQwsx9xr84WbWN3YCnKutyBnBXkT1ChKY4uEAAMzte"
OURS = "did:key:z6Mkpjt48fahhtdXLpw9Tvzutd5KeYSSkMLaSbfAmfxfdwqb"
GATED = ("voter", "writer")


def ts(s):
    return datetime.datetime.strptime(str(s).replace("Z", "")[:26],
                                      "%Y-%m-%dT%H:%M:%S.%f").replace(tzinfo=datetime.timezone.utc)


def body(r):
    try:
        return json.loads(r["text"])
    except Exception:
        return {}


def rows_from_file(p):
    out = []
    for line in open(p, encoding="utf-8"):
        line = line.strip()
        if line.startswith("{"):
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def export(room, timeout=300):
    raw = urllib.request.urlopen(urllib.request.Request(BASE + "/r/" + room + "/export", headers=UA),
                                 timeout=timeout).read().decode("utf-8", "replace")
    open("_r109_" + room + ".jsonl", "w", encoding="utf-8").write(raw)
    out = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out, len(raw.encode("utf-8"))


def accepted_voters(rows):
    """DIDs holding an accepted ballot receipt (same walk as the audit tool)."""
    out = set()
    for r in rows:
        if r["from"] != REFEREE:
            continue
        o = body(r)
        if o.get("status") != "accepted":
            continue
        t = o.get("type")
        if t == "sonnet.receipt.v1" and o.get("sender_did"):
            out.add(o["sender_did"])
        elif t == "sonnet.receipts.v1":
            for it in o.get("receipts", []):
                if it.get("sender_did"):
                    out.add(it["sender_did"])
    return out


def gated_accepts(rows):
    out = []
    for r in rows:
        if r["from"] != REFEREE:
            continue
        o = body(r)
        if o.get("status") != "accepted":
            continue
        if o.get("role") not in GATED:
            continue
        t = o.get("type")
        if t == "sonnet.receipt.v1" and o.get("sender_did"):
            out.append((ts(r["ts"]), o["sender_did"]))
        elif t == "sonnet.receipts.v1":
            for it in o.get("receipts", []):
                if it.get("sender_did"):
                    out.append((ts(r["ts"]), it["sender_did"]))
    return out


print("r109 falsifier run", datetime.datetime.now(datetime.timezone.utc).isoformat())

res_now, bytes_now = export("d-sonnet-2-results")
roster_now = {}
for r in res_now:
    o = body(r)
    if o.get("type") != "sonnet.identities.v1":
        continue
    for did, meta in (o.get("additions") or {}).items():
        roster_now[did] = {"added_ts": r["ts"], "added_seq": r["seq"],
                           "first_seen": meta.get("first_seen"),
                           "sha": meta.get("evidence_sha256")}
json.dump(roster_now, open("_r109_roster.json", "w"), indent=0)
print("roster NOW  %d DIDs, rows %d, seq %d..%d, floor_is_1=%s, bytes %d" % (
    len(roster_now), len(res_now), res_now[0]["seq"], res_now[-1]["seq"],
    res_now[0]["seq"] == 1, bytes_now))

roster_108 = json.load(open("_r108_roster.json", encoding="utf-8"))
print("roster r108 %d DIDs" % len(roster_108))
print("roster growth since r108: +%d DIDs" % (len(roster_now) - len(roster_108)))
print("r108 roster is a SUBSET of today's:", set(roster_108) <= set(roster_now),
      " (dropped: %d)" % len(set(roster_108) - set(roster_now)))

# --- TEST 1: the exact DIDs we named unbacked at round 108 -------------------
v108 = rows_from_file("_r108_mb-sonnet-2-votes.jsonl")
voters_108 = accepted_voters(v108)
unbacked_108 = voters_108 - set(roster_108)
print("\n=== TEST 1  voters we named unbacked at round 108 ===")
print("  r108 accepted-ballot DIDs        %d" % len(voters_108))
print("  unbacked against the r108 roster %d  (%.1f%%)   [published: 2831 / 78.4%%]" % (
    len(unbacked_108), 100.0 * len(unbacked_108) / max(1, len(voters_108))))
now_ok = unbacked_108 & set(roster_now)
print("  of those, PRESENT in today's roster: %d  (%.1f%%)" % (
    len(now_ok), 100.0 * len(now_ok) / max(1, len(unbacked_108))))
print("  still absent today:                  %d" % len(unbacked_108 - set(roster_now)))
if now_ok:
    added = sorted(roster_now[d]["added_ts"] for d in now_ok)
    print("  published between %s and %s" % (added[0], added[-1]))
    seqs = sorted({roster_now[d]["added_seq"] for d in now_ok})
    print("  in %d distinct batches, seq %d..%d" % (len(seqs), seqs[0], seqs[-1]))
    S = datetime.datetime(2026, 9, 11, 12, 0, 0, tzinfo=datetime.timezone.utc).timestamp()
    fs = [roster_now[d]["first_seen"] for d in now_ok if roster_now[d]["first_seen"]]
    print("  among the newly published, first_seen >= S (would break the rule): %d"
          % sum(1 for x in fs if x >= S))
    if fs:
        print("  newest first_seen among them: %s"
              % datetime.datetime.fromtimestamp(max(fs), datetime.timezone.utc).isoformat())
    shas = collections.Counter(roster_now[d]["sha"] for d in now_ok)
    print("  distinct evidence hashes among them: %d of %d (shared: %d)"
          % (len(shas), len(now_ok), sum(1 for h, n in shas.items() if n > 1)))

# --- TEST 2: same on the registration side ----------------------------------
r108 = rows_from_file("_r108_mb-sonnet-2-registration.jsonl")
g108 = gated_accepts(r108)
unb_reg = {d for t, d in g108 if d not in roster_108}
print("\n=== TEST 2  gated registration acceptances unbacked at round 108 ===")
print("  gated acceptances in the r108 window %d, distinct DIDs %d"
      % (len(g108), len({d for _, d in g108})))
print("  unbacked then %d" % len(unb_reg))
print("  present in today's roster: %d (%.1f%%)"
      % (len(unb_reg & set(roster_now)),
         100.0 * len(unb_reg & set(roster_now)) / max(1, len(unb_reg))))
hourly = collections.defaultdict(lambda: [0, 0, 0])
for t, d in g108:
    k = t.strftime("%m-%dT%H")
    hourly[k][0] += 1
    if d not in roster_108:
        hourly[k][1] += 1
        if d in roster_now:
            hourly[k][2] += 1
print("  hour           n   unbacked@r108      since published")
for k in sorted(hourly):
    n, u, f = hourly[k]
    print("   %s %7d %8d (%5.1f%%) %8d (%5.1f%%)"
          % (k, n, u, 100.0 * u / n, f, 100.0 * f / max(1, u)))

# --- TEST 3: our own DID ----------------------------------------------------
print("\n=== TEST 3  our own DID ===")
print("  in r108 roster: %s   in today's roster: %s"
      % (OURS in roster_108, OURS in roster_now))
if OURS in roster_now:
    print("  entry: %s" % json.dumps(roster_now[OURS]))

# --- TEST 4: the byte budget ------------------------------------------------
B108 = 6270273
BUD = 10 * 1024 * 1024
t0 = datetime.datetime(2026, 9, 14, 0, 22, 0, tzinfo=datetime.timezone.utc)
dt_h = (datetime.datetime.now(datetime.timezone.utc) - t0).total_seconds() / 3600.0
rate = (bytes_now - B108) / dt_h
print("\n=== TEST 4  the room that holds the evidence is filling ===")
print("  bytes r108 %d -> now %d  (+%d over %.2f h = %.0f B/h)"
      % (B108, bytes_now, bytes_now - B108, dt_h, rate))
print("  %.1f%% -> %.1f%% of a ~10MiB budget" % (100.0 * B108 / BUD, 100.0 * bytes_now / BUD))
if rate > 0:
    left = (BUD - bytes_now) / rate
    fill_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=left)
    D = datetime.datetime(2026, 9, 18, 12, 0, 0, tzinfo=datetime.timezone.utc)
    print("  headroom %d B; at the measured rate the room fills in %.2f h" % (BUD - bytes_now, left))
    print("  projected fill %s ; D = %s (%.2f days AFTER the fill)"
          % (fill_at.isoformat(), D.isoformat(), (D - fill_at).total_seconds() / 86400.0))
