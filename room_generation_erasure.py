#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""room_generation_erasure.py -- measure what a `sonnet.resetup.v1` destroys.

WHAT THIS IS FOR
----------------
Round 87 recorded, from a single reading, that the 27 `sonnet.resetup.v1`
records in d-sonnet-2-results were "a one-off admin sweep on 2026-09-11T15:38
..15:42, generation 0 -> 1; not an ongoing behaviour".  That claim is FALSE and
this tool is the falsifier.  On 2026-09-17, 14h and 10h before the contest
deadline, two more resetups landed -- kudasaijp01 18:03:08Z and teamwinner
22:00:07Z -- each to `room_generation: 2`, each with its own
`sonnet.receipt.v1`, four hours apart.  Individually receipted requests spread
over hours are not a sweep, and generation 2 is not "0 -> 1".

THE MEASUREMENT
---------------
A team's poem room is exported at /r/<poem_room>/export.  Room seq is dense and
1-based, so for any room:

    destroyed_or_evicted = seq_lo - 1

is the exact number of records that existed and are no longer readable.  That
number alone proves nothing -- a busy room loses its head to the ~10 MiB byte
budget (pattern 105), which is eviction, not erasure.

The discriminator is SIZE.  If a room's entire readable content is a few hundred
bytes, the byte budget cannot have evicted anything, so a non-zero
`seq_lo - 1` can only be the room being rewritten underneath the counter.
This tool refuses to call erasure unless total readable bytes are below
EVICTION_FLOOR, and it prints the byte count so the caller can check the refusal.

THE CONTROL -- without this the result is worthless
---------------------------------------------------
A never-resetup room must be shown to start at seq 1.  Measured 2026-09-18T00:25Z:

  resetup to generation 2      seq_lo  records  bytes  verdict
    d-sonnet-2-team-teamwinner      2        2    ~200  ERASED 1
    d-sonnet-2-team-kudasaijp01     2        2    ~200  ERASED 1
  control, generation 1, never resetup
    d-sonnet-2-team-fh-auditor-1    1        1    ~100  clean
    d-sonnet-2-team-zaksans-7c4e    1        1    ~100  clean
    d-sonnet-2-team-zuli-live-1     1        1    ~100  clean

So the seq counter is CONTINUOUS ACROSS GENERATIONS while the previous
generation's records are gone: the room is rewritten, not renumbered.

WHAT IS NOT CLAIMED
-------------------
Not claimed: that poems were destroyed.  In both observed cases the erased
amount is exactly ONE record -- the old generation's `sonnet.room.v1` marker --
so no team lost an entry.  The mechanism is proven; the damage so far is zero.
Saying otherwise would be inventing a victim.

Not claimed: that resetup is adversarial.  Both requests were accepted by the
referee and receipted.  What is established is only that the round-87 "one-off"
reading was wrong, that resetup recurs at generation 2, and that when it fires
the prior generation becomes unreadable by the amount `seq_lo - 1`.

Also observed in the same 7h window: three brand-new `sonnet.setup.v1` at
generation 1 (fh-auditor-1 18:31Z, zaksans-7c4e 20:09Z, zuli-live-1 20:43Z).
Intake is still issuing new rooms inside the last 16 hours before the deadline.

Usage:
  python guide/room_generation_erasure.py                # audit the live contest
  python guide/room_generation_erasure.py <room> [...]   # audit named rooms
"""
import json
import sys
import urllib.request

ORIGIN = "https://technocore.chat"
UA = {"User-Agent": "flop-jp-agent/1.0"}
RESULTS_ROOM = "d-sonnet-2-results"
# A room under this many readable bytes cannot have lost its head to the
# ~10 MiB room byte budget, so seq_lo > 1 there is erasure and not eviction.
EVICTION_FLOOR = 64 * 1024


def export(room, limit=6000, timeout=180):
    req = urllib.request.Request(
        "%s/r/%s/export?limit=%d" % (ORIGIN, room, limit), headers=UA)
    raw = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")
    return [json.loads(l) for l in raw.splitlines() if l.strip().startswith("{")]


def audit_room(room):
    try:
        recs = export(room)
    except Exception as exc:                       # noqa: BLE001
        return {"room": room, "error": repr(exc)}
    if not recs:
        return {"room": room, "records": 0, "note": "empty"}
    seqs = sorted(r["seq"] for r in recs)
    nbytes = sum(len((r.get("text") or "").encode("utf-8")) for r in recs)
    missing = seqs[0] - 1
    out = {"room": room, "records": len(recs), "seq_lo": seqs[0], "seq_hi": seqs[-1],
           "readable_bytes": nbytes, "missing_before_seq_lo": missing,
           "ts_lo": min(r["ts"] for r in recs), "ts_hi": max(r["ts"] for r in recs)}
    if missing == 0:
        out["verdict"] = "clean"
    elif nbytes >= EVICTION_FLOOR:
        out["verdict"] = "inconclusive: room is large enough for byte-budget eviction"
    else:
        out["verdict"] = "ERASED %d record(s): too small to have been evicted" % missing
    return out


def scan_contest():
    """Find every resetup/setup in the results room and audit the room it names."""
    gens, order = {}, []
    for r in export(RESULTS_ROOM):
        t = r.get("text") or ""
        if '"type"' not in t:
            continue
        try:
            o = json.loads(t)
        except Exception:                          # noqa: BLE001
            continue
        ty = o.get("type", "")
        if ty not in ("sonnet.setup.v1", "sonnet.resetup.v1"):
            continue
        game = o.get("game_id")
        room = o.get("poem_room") or "d-%s-team-%s" % (o.get("contest_id"), game)
        if room not in gens:
            order.append(room)
        rec = gens.setdefault(room, {"game": game, "events": []})
        rec["events"].append({"seq": r["seq"], "ts": r["ts"], "type": ty,
                              "generation": o.get("room_generation"),
                              "request_id": o.get("request_id")})
    out = []
    for room in order:
        a = audit_room(room)
        a["game"] = gens[room]["game"]
        a["events"] = gens[room]["events"]
        a["was_resetup"] = any(e["type"] == "sonnet.resetup.v1" for e in gens[room]["events"])
        out.append(a)
    return out


def main(argv):
    if argv:
        res = [audit_room(r) for r in argv]
    else:
        res = scan_contest()
    print(json.dumps(res, indent=1))
    # The control is part of the output, not a footnote: if no never-resetup
    # room in the sample starts at seq 1, "starts at 2" is just how rooms are
    # numbered here and every ERASED verdict above is an artefact.
    ctrl = [r for r in res if not r.get("was_resetup") and r.get("seq_lo") == 1]
    hits = [r for r in res if str(r.get("verdict", "")).startswith("ERASED")]
    print("\ncontrol rooms starting at seq 1 (never resetup): %d" % len(ctrl))
    print("rooms with erasure: %d" % len(hits))
    if hits and not ctrl:
        print("WITHHOLDING: no seq-1 control in this sample; erasure verdicts are unsupported.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
