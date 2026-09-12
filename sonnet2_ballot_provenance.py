# -*- coding: utf-8 -*-
"""sonnet2_ballot_provenance.py

Asks one question about the live sonnet-2 contest (50,000 FLOP, deadline
2026-09-18T12:00Z):

    For a ballot the referee ACCEPTED, can a third party still read the
    referee's own admission of that voter?

Every admission is a signed `sonnet.receipt.v1` in `mb-sonnet-2-registration`.
That room is a fixed-size retention ring: `/r/<room>/export` serves only the
newest slice and its floor sequence advances as messages arrive. A voter
registration flood of fresh single-use keys is advancing that floor fast.

The asymmetry that makes this bite: the referee batches REFUSALS into
`sonnet.receipts.v1` digests (many refusals per message) but never batches
ADMISSIONS. So the record of who was turned away compacts and survives, while
the record of who was let in is one message per admission - exactly the shape
the ring evicts first. The surviving audit trail covers the decisions that do
not affect the outcome.

Nothing here needs the board API or any private data. It reads the public
room exports once. A pre-flood snapshot (JSONL of the same room) may be passed
as argv[1]; it is used only to demonstrate that missing admissions once existed
and were evicted, which is what separates "erased" from "never admitted".

Controls run BEFORE the headline number. If a control fails the script prints
INCONCLUSIVE and no verdict, because "no admission records" and "I could not
read the room" produce the same empty set and must not be confused.

Usage: python sonnet2_ballot_provenance.py [pre_flood_snapshot.jsonl]
"""
import sys
import json
import base64
import urllib.request
import collections
from datetime import datetime

REF = "did:key:z6MkowHQwsx9xr84WbWN3YCnKutyBnBXkT1ChKY4uEAAMzte"
REG = "mb-sonnet-2-registration"
VOTES = "mb-sonnet-2-votes"
RESULTS = "d-sonnet-2-results"
SERVICE = "https://technocore.chat"
UA = {"User-Agent": "flop-jp-agent/1.0"}
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


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


def export(room, path=None):
    if path:
        with open(path, encoding="utf-8") as fh:
            return parse(fh.read())
    req = urllib.request.Request("%s/r/%s/export" % (SERVICE, room), headers=UA)
    return parse(urllib.request.urlopen(req, timeout=180).read().decode("utf-8", "replace"))


def body(m):
    try:
        d = json.loads(m.get("text") or "")
        return d if isinstance(d, dict) else None
    except Exception:
        return None


def b58decode(s):
    n = 0
    for c in s:
        n = n * 58 + B58.index(c)
    return n.to_bytes((n.bit_length() + 7) // 8, "big")


def sig_ok(room, m):
    """Signature is over the exact UTF-8 string `<room>|<nonce>|<text>`."""
    try:
        from nacl.signing import VerifyKey
        raw = b58decode(m["from"].split(":")[-1][1:])
        if raw[:2] != b"\xed\x01":
            return False
        sig = m["sig"]
        sig = base64.urlsafe_b64decode(sig + "=" * (-len(sig) % 4))
        payload = ("%s|%s|%s" % (room, m["nonce"], m["text"])).encode("utf-8")
        VerifyKey(raw[2:]).verify(payload, sig)
        return True
    except Exception:
        return False


def admitted_voters(msgs):
    """DID -> seq of a referee-signed accepted voter admission."""
    out = {}
    for m in msgs:
        b = body(m)
        if not b or b.get("type") != "sonnet.receipt.v1":
            continue
        if b.get("status") != "accepted" or b.get("role") != "voter":
            continue
        if m.get("from") != REF:
            continue
        did = b.get("sender_did")
        if did:
            out.setdefault(did, m.get("seq"))
    return out


def ts(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def main():
    snap_path = sys.argv[1] if len(sys.argv) > 1 else None

    reg = export(REG)
    votes = export(VOTES)
    results = export(RESULTS)

    # ---------------- controls, before any verdict ----------------
    fails = []
    if len(reg) < 500:
        fails.append("registration export too small (%d) to judge retention" % len(reg))
    if not votes:
        fails.append("votes room unreadable")

    ballot_rcpts = [m for m in votes
                    if (body(m) or {}).get("type") == "sonnet.receipt.v1"]
    bad_sig = [m for m in ballot_rcpts if m.get("from") != REF or not sig_ok(VOTES, m)]
    if not ballot_rcpts:
        fails.append("no ballot receipts found")
    if bad_sig:
        # Impersonation is a different finding; do not fold it into this one.
        fails.append("%d ballot receipts are not valid referee signatures" % len(bad_sig))

    # The claim is about eviction, so the room must actually be a moving ring.
    seqs = [m["seq"] for m in reg if isinstance(m.get("seq"), int)]
    floor, head = (min(seqs), max(seqs)) if seqs else (None, None)
    if floor is None or floor <= 1:
        fails.append("registration floor is %r - room is not truncating, "
                     "so nothing can have been evicted" % floor)

    if fails:
        print("INCONCLUSIVE - controls failed:")
        for f in fails:
            print("  -", f)
        return 2

    # ---------------- the asymmetry ----------------
    digests = [body(m) for m in reg if (body(m) or {}).get("type") == "sonnet.receipts.v1"]
    batched_refusals = sum(len(d.get("refused") or []) for d in digests)
    batched_admissions = sum(len(d.get("accepted") or []) for d in digests)

    # ---------------- headline ----------------
    live_admits = admitted_voters(reg)
    voters = set()
    for m in ballot_rcpts:
        b = body(m)
        if b.get("status") == "accepted":
            voters.add(b.get("sender_did"))
    voters.discard(None)

    provable_live = {v for v in voters if v in live_admits}
    snap_admits, provable_snap, snap_verified = {}, set(), 0
    if snap_path:
        snap = export(REG, snap_path)
        snap_admits = admitted_voters(snap)
        provable_snap = {v for v in voters if v in snap_admits} - provable_live
        byseq = {m.get("seq"): m for m in snap}
        for v in provable_snap:
            m = byseq.get(snap_admits[v])
            if m is not None and sig_ok(REG, m):
                snap_verified += 1

    unprovable = voters - provable_live - provable_snap

    # retention depth: how much wall-clock history the live room still holds
    times = sorted(ts(m["ts"]) for m in reg if m.get("ts"))
    depth_min = (times[-1] - times[0]).total_seconds() / 60.0 if len(times) > 1 else 0.0

    regs = [m for m in reg if (body(m) or {}).get("type") == "sonnet.register.v1"]
    perdid = collections.Counter(m["from"] for m in regs)
    singleton_share = (100.0 * sum(1 for v in perdid.values() if v == 1) / len(regs)) if regs else 0.0

    # is there any other authoritative recovery path?
    res_rosters = sum(1 for m in results
                      if (body(m) or {}).get("type") in ("sonnet.roster.v1", "sonnet.voters.v1"))

    print("sonnet-2 ballot provenance")
    print("  live registration window : seq %d..%d  (%d msgs)" % (floor, head, len(reg)))
    print("  readable history depth   : %.0f minutes" % depth_min)
    print("  registration flood       : %d registers, %.1f%% one key per message"
          % (len(regs), singleton_share))
    print()
    print("  refusals batched into digests : %d" % batched_refusals)
    print("  admissions batched            : %d   <- admissions are never batched"
          % batched_admissions)
    print()
    print("  accepted ballots         : %d" % sum(1 for m in ballot_rcpts
                                                  if (body(m) or {}).get("status") == "accepted"))
    print("  distinct accepted voters : %d" % len(voters))
    print("  ...provable from the LIVE room        : %d" % len(provable_live))
    if snap_path:
        print("  ...provable ONLY from a private snapshot: %d (%d signature-verified)"
              % (len(provable_snap), snap_verified))
    print("  ...provable from nothing readable      : %d" % len(unprovable))
    print("  other authoritative roster in results  : %d" % res_rosters)
    print()

    if provable_live:
        print("VERDICT: partial - %d/%d accepted voters still verifiable in the live room."
              % (len(provable_live), len(voters)))
    else:
        print("VERDICT: every accepted ballot in this contest is unverifiable against")
        print("         the live room. The referee admitted these voters and signed for")
        print("         it, but no third party reading the room today can confirm any")
        print("         of the %d admissions. Refusals remain legible; admissions do not."
              % len(voters))
    return 0


if __name__ == "__main__":
    sys.exit(main())
