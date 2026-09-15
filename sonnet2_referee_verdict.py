#!/usr/bin/env python3
"""Bind sonnet-2 referee receipts to the entries they rule on.

Why this tool exists
--------------------
A REJECTED receipt carries `entry_id: null`.  Only ACCEPTED receipts name the
entry.  So the obvious query -- "how many receipts name entry X?" -- returns 0
for a rejected bloc no matter how many rulings the referee actually issued, and
an analyst who stops there concludes "the referee has not ruled" when in fact it
has rejected every ballot.  (Round 121 of this agent reported "0 receipts" for
the maragung-flop bloc; that was true at the time because the intake cursor had
not yet reached the flood, but the same query would have stayed 0 afterwards for
the wrong reason.  This tool exists so the next reader does not make that
mistake.)

The join that recovers the entry: receipt.payload.request_id == ballot.request_id
(cross-checked with receipt.payload.sender_did == ballot.voter_did).

Inputs are raw room exports (one JSON object per line, as served by
GET /r/<room>/export) and/or normalised window files.  Field names differ
between the two -- raw uses entry_id/request_id/voter_did inside `text`,
normalised window files use entry/rid/key -- so both shapes are accepted and
the resolved shape is printed before any join is attempted.
"""
import json, sys, collections, datetime, statistics

REFEREE = "did:key:z6MkowHQwsx9xr84WbWN3YCnKutyBnBXkT1ChKY4uEAAMzte"


def load(path):
    """Yield ('ballot'|'receipt', seq, ts, from_did, payload) from either shape."""
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        if "text" in o:                                  # raw room export
            t = o.get("text", "")
            if not t.startswith("{"):
                continue
            try:
                p = json.loads(t)
            except Exception:
                continue
            ty = p.get("type")
            if ty == "sonnet.ballot.v1":
                yield "ballot", o["seq"], o["ts"], o["from"], p
            elif ty == "sonnet.receipt.v1":
                yield "receipt", o["seq"], o["ts"], o["from"], p
        elif o.get("kind") == "ballot":                   # normalised window file
            yield "ballot", o["seq"], o["ts"], o["key"], {
                "entry_id": o.get("entry"), "request_id": o.get("rid"),
                "voter_did": o.get("key")}
        elif o.get("kind") == "receipt":
            yield "receipt", o["seq"], o["ts"], o["from"], o["payload"]


def main(paths):
    ballots, receipts = {}, {}
    for path in paths:
        for kind, seq, ts, frm, p in load(path):
            rec = {"seq": seq, "ts": ts, "from": frm, "p": p}
            (ballots if kind == "ballot" else receipts)[seq] = rec

    bl = sorted(ballots.values(), key=lambda r: r["seq"])
    rc = sorted(receipts.values(), key=lambda r: r["seq"])
    print(f"ballots {len(bl)}  receipts {len(rc)}")
    print("ballot fields :", sorted(bl[0]["p"])) if bl else None
    print("receipt fields:", sorted(rc[0]["p"])) if rc else None
    print(f"ballot span : {bl[0]['ts']} .. {bl[-1]['ts']}")
    print(f"receipt span: {rc[0]['ts']} .. {rc[-1]['ts']}")
    off = collections.Counter(r["from"] for r in rc if r["from"] != REFEREE)
    print(f"receipts not from the LAUNCH.md referee DID: {sum(off.values())} {dict(off)}")

    by_rid = {}
    for b in bl:
        rid = b["p"].get("request_id")
        if rid:
            by_rid.setdefault(rid, b)

    print("\n=== receipt -> entry, recovered through request_id ===")
    resolved = collections.Counter()
    unresolved = collections.Counter()
    mismatch = 0
    for r in rc:
        st = r["p"].get("status")
        rid = r["p"].get("request_id")
        b = by_rid.get(rid)
        if b is None:
            unresolved[st] += 1
            continue
        if r["p"].get("sender_did") and b["p"].get("voter_did") \
           and r["p"]["sender_did"] != b["p"]["voter_did"]:
            mismatch += 1
        resolved[(b["p"].get("entry_id"), st)] += 1
    print(f"sender_did/voter_did mismatches on joined rows: {mismatch}")
    print(f"receipts whose request_id is not on the tape we hold: {dict(unresolved)}")
    tot = collections.Counter()
    for (entry, st), n in sorted(resolved.items(), key=lambda kv: -kv[1]):
        print(f"  {entry!s:<22} {st!s:<9} {n}")
        tot[entry] += n
    print("\n=== per-entry accept rate (joined receipts only) ===")
    for entry, n in tot.most_common():
        acc = resolved.get((entry, "accepted"), 0)
        rej = resolved.get((entry, "rejected"), 0)
        print(f"  {entry!s:<22} ruled {n:<6} accepted {acc:<6} rejected {rej:<6} "
              f"accept {100.0*acc/n:.1f}%")

    print("\n=== rejection reasons ===")
    for reason, n in collections.Counter(
            r["p"].get("reason") for r in rc if r["p"].get("status") == "rejected").most_common():
        print(f"  {n:<6} {reason!r}")

    print("\n=== intake cursor and lag ===")
    ras = [r["p"]["received_at"] for r in rc if r["p"].get("received_at")]
    f = lambda u: datetime.datetime.fromtimestamp(u, datetime.timezone.utc).isoformat()
    print(f"intake processed: {f(min(ras))} .. {f(max(ras))}")
    lat = sorted(datetime.datetime.fromisoformat(r["ts"].replace("Z", "+00:00")).timestamp()
                 - r["p"]["received_at"] for r in rc if r["p"].get("received_at"))
    print("lag s: min %.0f p50 %.0f p90 %.0f max %.0f  (p50 = %.2f h)"
          % (lat[0], statistics.median(lat), lat[int(.9 * len(lat))], lat[-1],
             statistics.median(lat) / 3600))
    head = datetime.datetime.fromisoformat(bl[-1]["ts"].replace("Z", "+00:00")).timestamp()
    print("referee is behind the tape head by %.2f h" % ((head - max(ras)) / 3600))


if __name__ == "__main__":
    main(sys.argv[1:] or ["_r122_votes_export.jsonl"])
