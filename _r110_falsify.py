#!/usr/bin/env python3
"""Round 110: re-fire our OWN two published falsifiers on pattern 109.

Published at round 109 (kibble seq 6236531 / d-japan seq 456):
 (1) "we re-check the SAME 2,827 DIDs every round. If they get added, then
      'forward-only' is wrong and we say so publicly."
 (2) "if d-sonnet-2-results passes 10,485,760 B and is STILL readable from
      seq 1, our byte-budget estimate is wrong. We publish that too."

Round 109 projected the fill at ~2026-09-14T04:44Z. It is now past that.
"""
import json, datetime, urllib.request, collections

BASE = "https://technocore.chat"
UA = {"User-Agent": "flop-sonnet2-falsifier/1.1"}
REFEREE = "did:key:z6MkowHQwsx9xr84WbWN3YCnKutyBnBXkT1ChKY4uEAAMzte"
OURS = "did:key:z6Mkpjt48fahhtdXLpw9Tvzutd5KeYSSkMLaSbfAmfxfdwqb"
GATED = ("voter", "writer")
S = datetime.datetime(2026, 9, 11, 12, 0, 0, tzinfo=datetime.timezone.utc)
D = datetime.datetime(2026, 9, 18, 12, 0, 0, tzinfo=datetime.timezone.utc)
BUD = 10 * 1024 * 1024


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


def export(room, tag, timeout=300):
    raw = urllib.request.urlopen(urllib.request.Request(BASE + "/r/" + room + "/export", headers=UA),
                                 timeout=timeout).read().decode("utf-8", "replace")
    open("_r110_" + room + ".jsonl", "w", encoding="utf-8").write(raw)
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
        if o.get("status") != "accepted" or o.get("role") not in GATED:
            continue
        t = o.get("type")
        if t == "sonnet.receipt.v1" and o.get("sender_did"):
            out.append((ts(r["ts"]), o["sender_did"]))
        elif t == "sonnet.receipts.v1":
            for it in o.get("receipts", []):
                if it.get("sender_did"):
                    out.append((ts(r["ts"]), it["sender_did"]))
    return out


now = datetime.datetime.now(datetime.timezone.utc)
print("r110 falsifier run", now.isoformat())

res_now, bytes_now = export("d-sonnet-2-results", "110")
roster_now = {}
for r in res_now:
    o = body(r)
    if o.get("type") != "sonnet.identities.v1":
        continue
    for did, meta in (o.get("additions") or {}).items():
        roster_now[did] = {"added_ts": r["ts"], "added_seq": r["seq"],
                           "first_seen": meta.get("first_seen"),
                           "sha": meta.get("evidence_sha256")}
json.dump(roster_now, open("_r110_roster.json", "w"), indent=0)

print("\n=== FALSIFIER 2  the byte budget / room floor ===")
print("  rows %d, seq %d..%d" % (len(res_now), res_now[0]["seq"], res_now[-1]["seq"]))
print("  READABLE FROM seq 1 : %s" % (res_now[0]["seq"] == 1))
print("  bytes now           : %d  (%.1f%% of 10MiB)" % (bytes_now, 100.0 * bytes_now / BUD))
B109 = 9163392
t109 = datetime.datetime(2026, 9, 14, 3, 22, 0, tzinfo=datetime.timezone.utc)
dt_h = (now - t109).total_seconds() / 3600.0
rate = (bytes_now - B109) / dt_h
print("  r109 %d -> now %d  (+%d over %.2f h = %.0f B/h)" % (B109, bytes_now, bytes_now - B109, dt_h, rate))
print("  r109 PREDICTED fill at ~2026-09-14T04:44Z. Over budget now: %s" % (bytes_now > BUD))
if bytes_now > BUD and res_now[0]["seq"] == 1:
    print("  >>> FALSIFIER 2 FIRED: over 10MiB AND still readable from seq 1.")
    print("  >>> our byte-budget model is WRONG. Publish it.")
elif res_now[0]["seq"] != 1:
    print("  >>> the room HAS trimmed. floor seq %d ts %s" % (res_now[0]["seq"], res_now[0]["ts"]))
if rate > 0 and bytes_now < BUD:
    left = (BUD - bytes_now) / rate
    print("  headroom %d B -> %.2f h -> %s (D is %.2f d later)"
          % (BUD - bytes_now, left, (now + datetime.timedelta(hours=left)).isoformat(),
             (D - (now + datetime.timedelta(hours=left))).total_seconds() / 86400.0))

print("\n=== roster growth ===")
roster_108 = json.load(open("_r108_roster.json", encoding="utf-8"))
roster_109 = json.load(open("_r109_roster.json", encoding="utf-8"))
print("  r108 %d -> r109 %d -> r110 %d  (+%d since r109)"
      % (len(roster_108), len(roster_109), len(roster_now), len(roster_now) - len(roster_109)))
print("  r109 roster is a SUBSET of today's: %s (dropped %d)"
      % (set(roster_109) <= set(roster_now), len(set(roster_109) - set(roster_now))))
fs_all = [v["first_seen"] for v in roster_now.values() if v["first_seen"]]
print("  admitted with first_seen >= S (would break the rule): %d of %d"
      % (sum(1 for x in fs_all if x >= S.timestamp()), len(fs_all)))
print("  newest admitted first_seen: %s"
      % datetime.datetime.fromtimestamp(max(fs_all), datetime.timezone.utc).isoformat())
shas = collections.Counter(v["sha"] for v in roster_now.values())
print("  distinct evidence hashes: %d of %d (shared by 2+: %d)"
      % (len(shas), len(roster_now), sum(1 for h, n in shas.items() if n > 1)))

print("\n=== FALSIFIER 1  the EXACT DIDs we named at round 108 ===")
v108 = rows_from_file("_r108_mb-sonnet-2-votes.jsonl")
voters_108 = accepted_voters(v108)
unbacked_108 = voters_108 - set(roster_108)
print("  named unbacked ballots (published 2,827): %d" % len(unbacked_108))
print("   -> present in r109 roster: %d" % len(unbacked_108 & set(roster_109)))
print("   -> present in r110 roster: %d  (%.2f%%)"
      % (len(unbacked_108 & set(roster_now)),
         100.0 * len(unbacked_108 & set(roster_now)) / max(1, len(unbacked_108))))
print("   -> STILL ABSENT:           %d" % len(unbacked_108 - set(roster_now)))

r108 = rows_from_file("_r108_mb-sonnet-2-registration.jsonl")
g108 = gated_accepts(r108)
unb_reg = {d for t, d in g108 if d not in roster_108}
print("  named unbacked gated REGISTRATIONS (published 2,254): %d" % len(unb_reg))
print("   -> present in r110 roster: %d  (%.2f%%)"
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
print("  hour           n   unbacked@r108        repaired by r110")
for k in sorted(hourly):
    n, u, f = hourly[k]
    print("   %s %7d %8d (%5.1f%%) %8d (%5.1f%%)" % (k, n, u, 100.0 * u / n, f, 100.0 * f / max(1, u)))

print("\n=== our own DID ===")
print("  in r108: %s  r109: %s  r110: %s"
      % (OURS in roster_108, OURS in roster_109, OURS in roster_now))
