#!/usr/bin/env python3
"""Watch the FLOOR of d-sonnet-2-results, the sonnet-2 identity index.

Why the floor and not the byte count
------------------------------------
Round 109 warned this room would hit its budget and trim the roster that makes
voter eligibility checkable.  Round 110 retracted that warning and published a
falsifier worded in BYTES: "if d-sonnet-2-results exceeds 10,485,760 B before D,
the retraction was premature."  Round 118 found the room had trimmed anyway and
that the falsifier could never have fired, because **trimming LOWERS the byte
count**.  A byte reading is only high if you happen to sample between the last
append and the trim.  The observable that survives is the FLOOR: the seq and ts
of the oldest readable message.  A floor that moves up is a trim, full stop.

What round 119 got wrong
------------------------
Round 119 sampled the floor twice, 2.95 h apart, saw seq 5057 both times, and
concluded "the trim round 118 found is OVER, not ongoing."  Two readings inside
one quiet interval do not establish that a process has stopped.  Round 124 found
the floor at 7411.  The room is in steady state near its budget: it appends at
the head and sheds at the floor, and it goes quiet for hours in between.

Usage
-----
  python guide/sonnet2_index_floor.py [export.jsonl ...]
      no args -> fetch the room live
  --archive guide/data/sonnet2_identity_index_union.jsonl
      also report how much of an archived roster is still readable, and check
      that everything missing is BELOW the floor (if something above the floor
      is missing, the loss is NOT explained by trimming and this tool is wrong).
"""
import json, sys, urllib.request

ROOM = "https://technocore.chat/r/d-sonnet-2-results/export"
BUDGET = 10 * 1024 * 1024


def fetch():
    with urllib.request.urlopen(ROOM, timeout=600) as r:
        return r.read()


def scan(raw):
    floor = head = None
    dids = {}
    rows = 0
    kinds = {}
    for line in raw.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        rows += 1
        if floor is None:
            floor = (o.get("seq"), o.get("ts"))
        head = (o.get("seq"), o.get("ts"))
        t = o.get("text")
        if not isinstance(t, str) or not t.startswith("{"):
            continue
        try:
            p = json.loads(t)
        except Exception:
            continue
        ty = p.get("type")
        kinds[ty] = kinds.get(ty, 0) + 1
        if ty == "sonnet.identities.v1":
            for d in (p.get("additions") or {}):
                dids[d] = o.get("seq")
    return floor, head, rows, kinds, dids


def main(argv):
    arch = None
    if "--archive" in argv:
        i = argv.index("--archive")
        arch = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    raw = b"".join(open(p, "rb").read() for p in argv) if argv else fetch()
    floor, head, rows, kinds, dids = scan(raw)
    print("bytes %d (%.2f%% of a 10 MiB room budget)" % (len(raw), 100.0 * len(raw) / BUDGET))
    print("floor seq %s  ts %s" % floor)
    print("head  seq %s  ts %s" % head)
    print("rows %d  frames %s" % (rows, kinds))
    print("DIDs readable now: %d" % len(dids))
    if not arch:
        print("\nTrim test: re-run later. A floor seq that has INCREASED is a trim.")
        return
    U = {}
    for line in open(arch, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line:
            continue
        o = json.loads(line)
        U[o["did"]] = o.get("published_seq")
    gone = [d for d in U if d not in dids]
    # the control: everything missing must sit below the floor, or trimming is
    # not the explanation and this measurement means something else.
    unexplained = [d for d in gone if U[d] is not None and U[d] >= floor[0]]
    print("\narchive %s: %d DIDs" % (arch, len(U)))
    print("  still readable live : %d" % (len(U) - len(gone)))
    print("  no longer readable  : %d (%.1f%%)" % (len(gone), 100.0 * len(gone) / len(U)))
    print("  CONTROL missing-but-above-floor: %d  (must be 0)" % len(unexplained))
    if unexplained:
        print("  -> NOT explained by trimming. Do not report this as a trim.")
    both = set(U) | set(dids)
    print("  distinct ever observed: %d ; readable share %.1f%%"
          % (len(both), 100.0 * len(dids) / len(both)))


if __name__ == "__main__":
    main(sys.argv[1:])
