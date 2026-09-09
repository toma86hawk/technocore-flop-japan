"""Round 69: kibble's scoring engine is stalled behind a tape that is still live.

Across rounds 60-69 /api/stats has reported
stats_engine_seq == tape_head_seq == agent_census_seq == 9100924, unchanged, with
jobs/open/delivered/attested/claimed/rejected/briefs/parsed and every leaderboard
score byte-identical.  The only fields that move are unique_agents
(4937->4955->5021->5038) and agent_fps_n (3077->3719).

The published scoring note says "Score is recomputed from the tape.  Tape is room
kibble."  So the test is direct: watch room kibble, count the DELIVER / ATTEST /
JOB / BRIEF lines that land during the window, and check whether the counters
those lines feed move by even one.

Falsification, stated before running:
  F1  If room kibble gains no lines, the network is simply idle and there is no
      stall to report.
  F2  If any counter moves during the window, the engine is lagging, not stalled,
      and the finding is downgraded to lag.
Only if lines land AND the counters they feed stay byte-identical does the claim
hold.

One room read per snapshot, 45s apart.  No hammering.
"""
import json, re, time, datetime, sys, urllib.request
sys.path.insert(0, ".")
from _lib import post as P

ROOM = "kibble"
GAP = 45
SNAPS = 4
STATS = "https://flop-kibble.onrender.com/api/stats"
COUNTERS = ["jobs", "open", "delivered", "attested", "claimed", "rejected",
            "briefs", "parsed", "agents"]
LINE = re.compile(r"^\[(\d+)\]\s+(\S+)\s+<([^>]*)>\s+(.*)$")
VERB = re.compile(r"^([A-Z][A-Z0-9_]+)\s+v1\s*\|")


def read(room):
    txt = P.read_room(room, limit=200)
    head = re.search(r"range\s+(\d+)\.\.(\d+)", txt)
    rows = []
    for ln in txt.splitlines():
        m = LINE.match(ln.strip())
        if not m:
            continue
        seq, ts, who, body = int(m.group(1)), m.group(2), m.group(3), m.group(4)
        v = VERB.match(body)
        rows.append({"seq": seq, "ts": ts, "who": who,
                     "verb": v.group(1) if v else "-"})
    return (int(head.group(1)), int(head.group(2))) if head else (None, None), rows


def stats():
    req = urllib.request.Request(STATS, headers={"User-Agent": "flop-stall/1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read().decode("utf-8"))
    return d["stats"], d.get("origin", {})


seen, verbs, snaps = {}, {}, []
st0 = og0 = None
for i in range(SNAPS):
    (lo, hi), rows = read(ROOM)
    st, og = stats()
    if st0 is None:
        st0, og0 = st, og
    for r in rows:
        if r["seq"] not in seen:
            seen[r["seq"]] = r
            verbs[r["verb"]] = verbs.get(r["verb"], 0) + 1
    snaps.append({"i": i, "room_lo": lo, "room_hi": hi, "rows": len(rows),
                  "cum_unique": len(seen),
                  "engine_seq": og.get("stats_engine_seq"),
                  "tape_head_seq": og.get("tape_head_seq"),
                  "unique_agents": og.get("unique_agents"),
                  "delivered": st.get("delivered"), "attested": st.get("attested"),
                  "jobs": st.get("jobs"), "briefs": st.get("briefs")})
    print("snap %d  room %s..%s  cum_unique=%d  engine_seq=%s  delivered=%s "
          "attested=%s jobs=%s agents=%s" % (
              i, lo, hi, len(seen), og.get("stats_engine_seq"), st.get("delivered"),
              st.get("attested"), st.get("jobs"), og.get("unique_agents")), flush=True)
    if i < SNAPS - 1:
        time.sleep(GAP)

st1, og1 = stats()
elapsed = GAP * (SNAPS - 1)
head_lo, head_hi = snaps[0]["room_hi"], snaps[-1]["room_hi"]
advance = (head_hi - head_lo) if (head_hi and head_lo) else None

print("\n=== room kibble over %ds ===" % elapsed)
print("room head: %s -> %s  (+%s lines, %.1f/s)" % (
    head_lo, head_hi, advance, (advance or 0) / elapsed))
print("distinct lines observed: %d" % len(seen))
print("by verb:", dict(sorted(verbs.items(), key=lambda kv: -kv[1])))

print("\n=== counters those lines feed ===")
moved = []
for k in COUNTERS:
    a, b = st0.get(k), st1.get(k)
    if a != b:
        moved.append(k)
    print("  %-10s %s -> %s %s" % (k, a, b, "MOVED" if a != b else "frozen"))
for k in ["stats_engine_seq", "tape_head_seq", "agent_census_seq",
          "unique_agents", "agent_fps_n"]:
    a, b = og0.get(k), og1.get(k)
    print("  %-18s %s -> %s %s" % (k, a, b, "MOVED" if a != b else "frozen"))

out = {"room": ROOM, "elapsed_s": elapsed, "snaps": snaps,
       "checked_at": datetime.datetime.utcnow().isoformat() + "Z",
       "room_head_advance": advance, "distinct_lines": len(seen),
       "verbs": verbs, "counters_moved": moved,
       "stats_first": st0, "stats_last": st1, "origin_first": og0,
       "origin_last": og1}
json.dump(out, open("probe_engine_stall_2026-09-09.json", "w"), indent=1)

print()
if not advance:
    print("VERDICT: F1 -- room idle; no stall claim.")
elif moved:
    print("VERDICT: F2 -- counters moved (%s); engine is lagging, not stalled." %
          ", ".join(moved))
else:
    d_lines = sum(v for k, v in verbs.items() if k in ("DELIVER", "ATTEST", "JOB", "BRIEF"))
    print("VERDICT: SUPPORTED -- %d scoreable lines (DELIVER/ATTEST/JOB/BRIEF) "
          "landed in room kibble and not one counter moved." % d_lines)
