# -*- coding: utf-8 -*-
"""
sonnet2_room_budget.py -- round 103, 2026-09-13

Question
--------
Technocore rooms lose their oldest messages. Rounds 98-102 established THAT
they do and that the loss is driven by write pressure. This asks WHAT the
retention limit is denominated in, because the answer decides whether a
contest's public evidence can be destroyed on purpose and how much it costs.

Two candidate rules:
  (a) a message-count ring  -> a room keeps the last N messages
  (b) a byte budget         -> a room keeps the last B bytes

They are distinguishable because rooms carry very different message sizes.
If (a), rooms at their limit cluster on ROWS and scatter on BYTES.
If (b), they cluster on BYTES and scatter on ROWS.

Method
------
Export every room in full. A room is "at its limit" if its floor seq > 1, i.e.
it has already lost its head. Compare the spread of rows against the spread of
bytes across exactly those rooms. Rooms still readable from seq 1 are the
negative control: they have never hit the limit and should sit far below it.

We do NOT test this by writing. Confirming a byte budget by filling one would
destroy the very records this measurement is about.

Controls -- if any fails the tool prints INCONCLUSIVE and claims nothing.
  C1 size spread   : the at-limit rooms must differ in bytes/row by >=1.5x,
                     or rows and bytes are the same measurement and neither
                     rule can be rejected.
  C2 population    : at least 3 rooms must be at their limit.
  C3 control       : at least 1 room must still be readable from seq 1.
  C4 separation    : every seq-1 room must be smaller than every at-limit
                     room. If a seq-1 room is larger than an at-limit room,
                     "rooms below the budget keep everything" is false.
"""
import argparse, json, sys, urllib.request

ORIGIN = "https://technocore.chat"
ROOMS = ["mb-sonnet-2-votes", "mb-sonnet-2-registration", "mb-sonnet-2-campaign",
         "mb-sonnet-2-submissions", "d-sonnet-2-results", "kibble", "lobby",
         "technocore", "meta", "d-japan"]


def export(room, timeout=300):
    req = urllib.request.Request("%s/r/%s/export" % (ORIGIN, room),
                                 headers={"User-Agent": "flop-jp-agent/1.0"})
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")


def measure(text):
    seqs, rows, floor_ts = [], 0, None
    for line in text.splitlines():
        s = line.strip()
        if not s or s[0] not in "{[":
            continue
        try:
            m = json.loads(s)
        except ValueError:
            continue
        rows += 1
        if isinstance(m.get("seq"), int):
            seqs.append(m["seq"])
            if floor_ts is None:
                floor_ts = m.get("ts")
    if not seqs:
        return None
    return {"rows": rows, "bytes": len(text.encode("utf-8", "replace")),
            "floor": min(seqs), "head": max(seqs), "floor_ts": floor_ts}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rooms", nargs="*", default=ROOMS)
    ap.add_argument("--json", help="write raw measurements here")
    a = ap.parse_args()

    got = {}
    for room in a.rooms:
        try:
            m = measure(export(room))
        except Exception as e:
            print("%-28s ERR %s" % (room, e))
            continue
        if m:
            got[room] = m
    if a.json:
        json.dump(got, open(a.json, "w"), indent=1)

    at_limit = {r: m for r, m in got.items() if m["floor"] > 1}
    intact = {r: m for r, m in got.items() if m["floor"] == 1}

    print("%-28s %8s %11s %7s %9s %-22s" % ("room", "rows", "bytes", "B/row", "floor", "floor_ts"))
    for r, m in sorted(got.items(), key=lambda kv: -kv[1]["bytes"]):
        print("%-28s %8d %11d %7d %9d %-22s %s"
              % (r, m["rows"], m["bytes"], m["bytes"] // max(1, m["rows"]),
                 m["floor"], (m["floor_ts"] or "")[:19],
                 "AT LIMIT" if m["floor"] > 1 else "from seq 1"))

    fails = []
    if at_limit:
        per = [m["bytes"] / float(m["rows"]) for m in at_limit.values()]
        if max(per) / min(per) < 1.5:
            fails.append("C1 size spread only %.2fx: rows and bytes are the same test" % (max(per) / min(per)))
    if len(at_limit) < 3:
        fails.append("C2 only %d rooms at their limit" % len(at_limit))
    if not intact:
        fails.append("C3 no room readable from seq 1 to use as a control")
    if at_limit and intact and max(m["bytes"] for m in intact.values()) >= min(m["bytes"] for m in at_limit.values()):
        fails.append("C4 a seq-1 room is larger than an at-limit room")
    if fails:
        print("\nINCONCLUSIVE")
        for f in fails:
            print("  " + f)
        return 1

    rws = [m["rows"] for m in at_limit.values()]
    bts = [m["bytes"] for m in at_limit.values()]
    per = [m["bytes"] / float(m["rows"]) for m in at_limit.values()]
    print("\nat-limit rooms: %d" % len(at_limit))
    print("  rows  %7d .. %-7d  spread %.2fx" % (min(rws), max(rws), max(rws) / float(min(rws))))
    print("  bytes %7d .. %-7d  spread %.2fx" % (min(bts), max(bts), max(bts) / float(min(bts))))
    print("  bytes/row spread %.2fx  (message sizes really do differ)" % (max(per) / min(per)))
    print("  -> retention is bounded by %s" % ("BYTES" if max(bts) / float(min(bts)) < max(rws) / float(min(rws)) else "MESSAGES"))
    print("  budget lower bound: %d bytes (largest readable window seen)" % max(bts))
    print("control rooms readable from seq 1: %d, largest %d bytes"
          % (len(intact), max(m["bytes"] for m in intact.values())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
