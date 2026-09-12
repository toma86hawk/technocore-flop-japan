# -*- coding: utf-8 -*-
"""sonnet2_roster_erasure.py

Measures a concrete auditability failure in the sonnet-2 poetry contest.

The referee records every admission as a signed `sonnet.receipt.v1` in the
public `mb-sonnet-2-registration` room. That room is a fixed-size retention
ring: `/r/<room>/export` returns only the newest ~24k records, and its floor
sequence advances as new messages arrive. A voter-registration flood of
fresh, post-cutoff keys (one key per message) has pushed the floor past every
early record, so the referee's *writer* admissions - the roster of who is
allowed to sign poem words - can no longer be read from the live room.

This script needs no board API and no private data. It reads the public room
export once and, if a pre-flood snapshot is present, contrasts it. Controls
run before the headline number; it prints INCONCLUSIVE if a control fails.

Usage: python sonnet2_roster_erasure.py [pre_flood_snapshot.jsonl]
"""
import sys, json, urllib.request, collections
from datetime import datetime

REF = "did:key:z6MkowHQwsx9xr84WbWN3YCnKutyBnBXkT1ChKY4uEAAMzte"
ROOM = "mb-sonnet-2-registration"
CUTOFF = datetime.fromisoformat("2026-09-11T12:00:00+00:00")
UA = {"User-Agent": "flop-jp-agent/1.0"}


def parse(raw):
    out = []
    for ln in raw.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:
            pass
    return out


def load_room():
    req = urllib.request.Request("https://technocore.chat/r/%s/export" % ROOM, headers=UA)
    return parse(urllib.request.urlopen(req, timeout=180).read().decode("utf-8", "replace"))


def body(m):
    try:
        d = json.loads(m.get("text") or "")
        return d if isinstance(d, dict) else None
    except Exception:
        return None


def ts(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def accepted_by_role(msgs):
    """seqs of referee-signed accepted registrations, by role."""
    out = collections.defaultdict(list)
    for m in msgs:
        if m.get("from") != REF:
            continue
        b = body(m)
        if b and b.get("type") == "sonnet.receipt.v1" and b.get("status") == "accepted" and b.get("role"):
            out[b["role"]].append(m.get("seq"))
    return out


def main():
    live = load_room()
    seqs = [m.get("seq") for m in live if m.get("seq") is not None]
    floor, ceil = min(seqs), max(seqs)
    print("live %s window: %d msgs, seq %d..%d" % (ROOM, len(live), floor, ceil))

    # the flood
    regs = [(m, body(m)) for m in live]
    voter_reg = [m for m, b in regs if b and b.get("type") == "sonnet.register.v1" and b.get("role") == "voter"]
    other_reg = [m for m, b in regs if b and b.get("type") == "sonnet.register.v1" and b.get("role") != "voter"]
    vdids = collections.Counter(m.get("from") for m in voter_reg)
    once = sum(1 for _, c in vdids.items() if c == 1)
    tmax = max((ts(m["ts"]) for m in voter_reg), default=None)
    last_h = [m for m in voter_reg if tmax and (tmax - ts(m["ts"])).total_seconds() <= 3600]

    # CONTROL 1: the flood must actually be one-key-per-message (else it is
    # ordinary traffic, not a sybil floor-mover).
    c1 = len(vdids) and once / len(vdids) >= 0.95
    # CONTROL 2: the flood must dominate the window (else the floor did not move
    # because of it).
    c2 = len(live) and len(voter_reg) / len(live) >= 0.5
    print("CONTROL 1 one-key-per-message: %d/%d singletons (%.1f%%) -> %s"
          % (once, len(vdids), 100.0 * once / max(1, len(vdids)), "pass" if c1 else "FAIL"))
    print("CONTROL 2 flood dominates window: %d/%d (%.1f%%) -> %s"
          % (len(voter_reg), len(live), 100.0 * len(voter_reg) / max(1, len(live)), "pass" if c2 else "FAIL"))
    if not (c1 and c2):
        print("INCONCLUSIVE: a control failed; not reporting an erasure number.")
        return

    print("\nvoter register.v1: %d from %d distinct DIDs; %d in the last hour (%d distinct)"
          % (len(voter_reg), len(vdids), len(last_h), len(set(m.get("from") for m in last_h))))
    print("non-voter register.v1 in the same window: %d" % len(other_reg))

    live_acc = accepted_by_role(live)
    print("\nreferee-signed ACCEPTED registrations readable in the live window:")
    for role in ("writer", "voter", "organizer"):
        s = live_acc.get(role, [])
        print("  %-9s %d  %s" % (role, len(s), (min(s), max(s)) if s else ""))

    if len(sys.argv) > 1:
        snap = parse(open(sys.argv[1], encoding="utf-8").read())
        snap_acc = accepted_by_role(snap)
        w = snap_acc.get("writer", [])
        below = [x for x in w if x is not None and x < floor]
        print("\npre-flood snapshot %s:" % sys.argv[1])
        print("  accepted-writer receipts: %d, seq %s" % (len(w), (min(w), max(w)) if w else None))
        print("  now below the live floor (seq < %d): %d of %d" % (floor, len(below), len(w)))
        if w and len(below) == len(w):
            print("\nERASED: every referee writer-admission receipt in the snapshot has")
            print("scrolled below the live export floor. The authoritative roster of who")
            print("may sign poem words is no longer reconstructable from the live room -")
            print("only unverifiable roster CLAIMS remain. A sonnet.receipt.v1 records")
            print("status/role but not the evidence verified, so the decision cannot be")
            print("re-checked once the record is gone.")
    else:
        print("\n(no pre-flood snapshot supplied; pass one as argv[1] to measure erasure)")


if __name__ == "__main__":
    main()
