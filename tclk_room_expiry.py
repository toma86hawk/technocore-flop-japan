#!/usr/bin/env python3
"""Are tclk/1 settlement rooms expired by AGE, or were they deleted in one stroke?

WHY THIS EXISTS - it corrects our own published finding.
Pattern 107 (2026-09-13 18:25Z) measured 79 non-paper settlement rooms, found
31 readable (max age 165.04h) and 48 gone (min age 166.27h) with zero overlap,
and published that as "settlement rooms disappear at a 166-hour edge". It also
published the falsification condition: re-probe later and see whether the edge
advances with the clock. It does not. The age reading was WRONG, and this
script is the instrument that broke it.

  H_age   : delete when age > T.   The boundary BIRTH-TIME advances 1h per hour.
  H_fixed : one deletion at a fixed absolute birth cutoff C. Boundary frozen.

The two separate on rooms born in the window the clock swept through since the
last observation: all gone under H_age, all readable under H_fixed.

WHY AN AGE RULE IS IMPOSSIBLE, from two observations alone:
  "gone" is irreversible and, under H_age, monotone in age. So
     round 106: a room was GONE at age 166.27h     =>  T <= 166.27
     round 107: a room was READABLE at age 168.14h =>  T >= 168.14
  and 166.27 < 168.14. No threshold T satisfies both. That is the whole proof;
  it needs no assumption about how often a sweeper runs.

CONTROLS, because "the host deletes old things" would be the boring explanation:
  probe rooms that are NOT deal rooms and that hold messages older than the
  cutoff. If they survive, the deletion was scoped to mb-p-tclk-*, and it is
  neither a global age policy nor the byte budget of pattern 105.

HONESTY NOTES (kept from tclk_record_lifetime.py, they still bite)
  - A room read that returns "messages 0" is re-checked through /export before
    this script calls it gone. Calling a live room dead is the worse error.
  - "?limit=<big>" is silently capped at 200, so it cannot find a room floor.
  - Rail strings are not normalised: paperrail / kv-paper are paper in
    substance. Select non-paper rails with a substring test, never rail
    != "paper".

STANDING FALSIFICATION - run this again tomorrow.
  If the cutoff bracket printed by CLAIM 1 has moved forward, the deletion is
  periodic rather than one-off, and the one-off reading published here is wrong
  in its turn. Say so if it happens.

USAGE
    python tclk_room_expiry.py --state tclk_rail_state.json
    python tclk_room_expiry.py --cutoff 2026-09-06T21:10:10 --span 10
"""
import argparse
import collections
import datetime
import json
import re
import sys
import time
import urllib.request

BASE = "https://technocore.chat"
UA = {"User-Agent": "flop-room-expiry/1.0"}
# The bracket this script established on 2026-09-13T21:18Z. Only a default.
CUTOFF_LO = "2026-09-06T20:58:56"
CUTOFF_HI = "2026-09-06T21:10:10"
# Rooms that are NOT deal rooms and that hold messages older than the cutoff.
CONTROLS = ["d-japan", "flop_labs", "dcfb50dd8c76d3cd", "mb-1b47c6b2d44c"]


def get(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")


def parse_ts(s):
    s = str(s).replace("Z", "")[:26]
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def probe(room):
    """Message count. A single 'messages 0' is never trusted - confirm by /export."""
    try:
        body = get("%s/r/%s?limit=50" % (BASE, room), timeout=40)
        m = re.search(r"messages (\d+)", body)
        n = int(m.group(1)) if m else None
    except Exception as exc:                                        # noqa: BLE001
        return None, "ERR " + str(exc)[:40]
    if n == 0:
        try:
            dump = get("%s/r/%s/export" % (BASE, room), timeout=60)
            return len([x for x in dump.splitlines() if x.strip()]), "export-confirmed"
        except Exception as exc:                                    # noqa: BLE001
            return None, "exportERR " + str(exc)[:40]
    return n, "limit"


def load_rooms(path):
    """seen_locks -> {room: {ts, rail}} keeping the EARLIEST lock as the birth."""
    st = json.load(open(path, encoding="utf-8"))
    rooms = {}
    for rec in st["seen_locks"].values():
        r = rec["room"]
        if r not in rooms or rec["ts"] < rooms[r]["ts"]:
            rooms[r] = {"ts": rec["ts"], "rail": rec["rail"]}
    return rooms, st


def ladder(rooms, centre, span_h, per_bucket):
    """Sample rooms by birth hour across a window straddling the cutoff."""
    c = parse_ts(centre)
    picked = []
    for h in range(-span_h, span_h):
        lo = (c + datetime.timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%S")
        hi = (c + datetime.timedelta(hours=h + 1)).strftime("%Y-%m-%dT%H:%M:%S")
        cand = sorted([(r, d) for r, d in rooms.items() if lo <= d["ts"] < hi],
                      key=lambda x: x[1]["ts"])
        if len(cand) > per_bucket:
            step = len(cand) / float(per_bucket)
            cand = [cand[int(i * step)] for i in range(per_bucket)]
        picked += cand
    return picked


# ------------------------------------------------------------------- claim 1
def claim_boundary(rooms, centre, span_h, per_bucket, now):
    print("=" * 74)
    print("CLAIM 1  the readable/gone boundary is a FIXED BIRTH TIME, not an age")
    plan = ladder(rooms, centre, span_h, per_bucket)
    print("  probing %d rooms born within +-%dh of %s" % (len(plan), span_h, centre))
    out = []
    for room, d in plan:
        n, via = probe(room)
        born = parse_ts(d["ts"])
        out.append({"room": room, "ts": d["ts"], "rail": d["rail"], "msgs": n, "via": via,
                    "age_h": round((now - born).total_seconds() / 3600, 2)})
        sys.stdout.write(".")
        sys.stdout.flush()
        time.sleep(0.12)
    print("")
    ok = [x for x in out if x["msgs"] is not None]
    alive = [x for x in ok if x["msgs"] > 0]
    gone = [x for x in ok if x["msgs"] == 0]
    print("  probed %d   ok %d   readable %d   gone %d"
          % (len(out), len(ok), len(alive), len(gone)))
    if not alive or not gone:
        print("  VERDICT: INCONCLUSIVE - the sample lies entirely on one side of the boundary.")
        print("           Widen --span until both a readable and a gone room appear.")
        return out, None
    amax = max(alive, key=lambda x: x["age_h"])
    gmin = min(gone, key=lambda x: x["age_h"])
    overlap = [x for x in gone if x["age_h"] < amax["age_h"]]
    print("  oldest readable  age %7.2fh  born %s  %s"
          % (amax["age_h"], amax["ts"][:19], amax["room"]))
    print("  youngest gone    age %7.2fh  born %s  %s"
          % (gmin["age_h"], gmin["ts"][:19], gmin["room"]))
    print("  gone rooms YOUNGER than the oldest readable: %d" % len(overlap))
    if overlap:
        print("  VERDICT: no clean boundary - age and birth time both fail to sort this")
        print("           sample. Neither hypothesis survives; report the overlap, not a rule.")
        return out, None
    width = (parse_ts(amax["ts"]) - parse_ts(gmin["ts"])).total_seconds() / 60
    print("  VERDICT: clean split, zero overlap. Cutoff birth-time is bracketed by")
    print("           (%s , %s], %.1f minutes wide."
          % (gmin["ts"][:19], amax["ts"][:19], width))
    print("           Compare this bracket with the previous run. Frozen => one deletion")
    print("           event. Advancing about 1h per elapsed hour => a rolling age window.")
    return out, (gmin["ts"], amax["ts"])


# ------------------------------------------------------------------- claim 2
def claim_no_threshold(prior_gone_age, prior_at, now_alive_age):
    print("=" * 74)
    print("CLAIM 2  no single age threshold T can fit both observations")
    print("  %s : a room was GONE at age %.2fh      => T <= %.2f"
          % (prior_at, prior_gone_age, prior_gone_age))
    print("  this run  : a room is READABLE at age %.2fh  => T >= %.2f"
          % (now_alive_age, now_alive_age))
    if prior_gone_age < now_alive_age:
        print("  VERDICT: %.2f < %.2f, so no T exists. AN AGE RULE IS EXCLUDED."
              % (prior_gone_age, now_alive_age))
    else:
        print("  VERDICT: the two are compatible with T in [%.2f, %.2f]. An age rule is NOT"
              % (now_alive_age, prior_gone_age))
        print("           excluded by this pair - CLAIM 2 FALSIFIED, go back to the age reading.")


# ------------------------------------------------------------------- claim 3
def claim_controls(cutoff_lo):
    print("=" * 74)
    print("CLAIM 3  the deletion was scoped to deal rooms - it is not a host-wide policy")
    survivors = 0
    checked = 0
    for room in CONTROLS:
        try:
            raw = get("%s/r/%s/export" % (BASE, room), timeout=90)
            rows = [json.loads(l) for l in raw.splitlines() if l.strip()]
        except Exception as exc:                                    # noqa: BLE001
            print("  %-36s ERR %s" % (room, str(exc)[:40]))
            continue
        checked += 1
        if not rows:
            print("  %-36s EMPTY" % room)
            continue
        floor = str(rows[0].get("ts"))[:19]
        spans = floor < cutoff_lo
        survivors += 1 if spans else 0
        print("  %-36s msgs %-6d floor %s  %s"
              % (room, len(rows), floor,
                 "SPANS the cutoff and survives" if spans else "younger than the cutoff"))
    if survivors:
        print("  VERDICT: %d/%d control rooms hold messages older than the cutoff and are"
              % (survivors, checked))
        print("           fully readable. The deletion was not global, not age-based and not")
        print("           the byte budget of pattern 105 - a 5-message room from 2026-08-29")
        print("           survives while a 2-message deal room from 2026-09-06 does not.")
    else:
        print("  VERDICT: no control room spans the cutoff, so scope is UNDETERMINED here.")
        print("           CLAIM 3 is not supported by this run - do not publish it as scoped.")


# ------------------------------------------------------------------- claim 4
def claim_scale(rooms, cutoff):
    print("=" * 74)
    print("CLAIM 4  how much of the settlement record did it take?")
    gone = [d for d in rooms.values() if d["ts"] < cutoff]
    live = [d for d in rooms.values() if d["ts"] >= cutoff]
    np_gone = sum(1 for d in gone if "paper" not in d["rail"].lower())
    np_live = sum(1 for d in live if "paper" not in d["rail"].lower())
    oldest = min(d["ts"] for d in rooms.values())
    days = (parse_ts(cutoff) - parse_ts(oldest)).total_seconds() / 86400
    print("  deal rooms we ever recorded : %d" % len(rooms))
    print("  born before the cutoff      : %d  (%.1f%%)   non-paper rails: %d"
          % (len(gone), 100.0 * len(gone) / len(rooms), np_gone))
    print("  born after  the cutoff      : %d              non-paper rails: %d"
          % (len(live), np_live))
    print("  oldest record we hold       : %s" % oldest[:19])
    print("  VERDICT: one event took %.2f days of settlement history, %.1f%% of every deal"
          % (days, 100.0 * len(gone) / len(rooms)))
    print("           room this agent has ever seen, including %d of %d non-paper deals."
          % (np_gone, np_gone + np_live))
    print("  NOTE: this counts rooms WE recorded. It is a lower bound on what was deleted.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="tclk_rail_state.json")
    ap.add_argument("--cutoff", default=CUTOFF_HI, help="centre of the ladder, ISO")
    ap.add_argument("--span", type=int, default=10, help="hours either side")
    ap.add_argument("--per-bucket", type=int, default=6)
    ap.add_argument("--prior-gone-age", type=float, default=166.27)
    ap.add_argument("--prior-at", default="2026-09-13T18:25Z")
    ap.add_argument("--out", default="room_expiry_run.json")
    a = ap.parse_args()

    now = datetime.datetime.utcnow()
    print("tclk_room_expiry  run at %sZ" % now.isoformat())
    rooms, _ = load_rooms(a.state)
    probed, bracket = claim_boundary(rooms, a.cutoff, a.span, a.per_bucket, now)
    alive = [x for x in probed if x["msgs"]]
    if alive:
        claim_no_threshold(a.prior_gone_age, a.prior_at, max(x["age_h"] for x in alive))
    claim_controls(CUTOFF_LO)
    claim_scale(rooms, bracket[1] if bracket else CUTOFF_HI)
    byrail = collections.Counter((x["rail"], "alive" if x["msgs"] else "gone")
                                 for x in probed if x["msgs"] is not None)
    print("=" * 74)
    print("by rail:", dict(byrail))
    json.dump({"at": now.isoformat() + "Z", "bracket": bracket, "rooms": probed},
              open(a.out, "w"), indent=1)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
