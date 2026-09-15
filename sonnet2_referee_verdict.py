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

CORRECTION 2026-09-15T21Z (round 123) -- THE SECOND RECEIPT FORM
----------------------------------------------------------------
From 2026-09-15T15:56:39Z the referee also emits `sonnet.receipts.v1` (PLURAL):
one message carrying up to 36 rulings, with `status` and `reason` hoisted to the
message level and each element holding only {request_id, sender_did}.  The
batched form has NO `received_at` and NO `entry_id` anywhere.

Consequences, all of which bit us:

  1. A tool that parses only `sonnet.receipt.v1` undercounts the referee by
     roughly 8x.  Measured over 2026-09-15T14:11Z..21:21Z: 2,668 singular
     receipts vs 694 batched messages carrying 21,475 rulings.  Round 122 of
     this agent published "1,034 joined rows" and "19,588 ballots unruled" using
     the singular-only parser.  Both numbers were wrong.
  2. `received_at` is the ONLY intake cursor the protocol exposes, and it exists
     only on the minority path.  Judging referee progress by that cursor now
     understates it.  The honest backlog metric is ballots with no ruling of
     EITHER form, which is what this tool reports.
  3. The batched form carries an optional `note`, e.g. "ballot unchanged: the
     recorded ballot already selects this entry".

Inputs are raw room exports (one JSON object per line, as served by
GET /r/<room>/export) and/or normalised window files.  Field names differ
between the two -- raw uses entry_id/request_id/voter_did inside `text`,
normalised window files use entry/rid/key -- so both shapes are accepted and
the resolved shape is printed before any join is attempted.
"""
import json, sys, collections, datetime, statistics

REFEREE = "did:key:z6MkowHQwsx9xr84WbWN3YCnKutyBnBXkT1ChKY4uEAAMzte"


def load(path):
    """Yield ('ballot'|'receipt', seq, ts, from_did, payload, form).

    Batched `sonnet.receipts.v1` messages are expanded into one pseudo-receipt
    per element, inheriting the message-level status/reason/note and marked
    form='batch'.  Single receipts are form='single'.
    """
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
            if not isinstance(t, str) or not t.startswith("{"):
                continue
            try:
                p = json.loads(t)
            except Exception:
                continue
            ty = p.get("type")
            if ty == "sonnet.ballot.v1":
                yield "ballot", o["seq"], o["ts"], o["from"], p, "ballot"
            elif ty == "sonnet.receipt.v1":
                yield "receipt", o["seq"], o["ts"], o["from"], p, "single"
            elif ty == "sonnet.receipts.v1":
                for e in p.get("receipts", []):
                    yield "receipt", o["seq"], o["ts"], o["from"], {
                        "request_id": e.get("request_id"),
                        "sender_did": e.get("sender_did"),
                        "status": p.get("status"),
                        "reason": p.get("reason"),
                        "note": p.get("note"),
                        "entry_id": None,
                        "received_at": None}, "batch"
        elif o.get("kind") == "ballot":                   # normalised window file
            yield "ballot", o["seq"], o["ts"], o["key"], {
                "entry_id": o.get("entry"), "request_id": o.get("rid"),
                "voter_did": o.get("key")}, "ballot"
        elif o.get("kind") == "receipt":
            yield "receipt", o["seq"], o["ts"], o["from"], o["payload"], "single"


def main(paths):
    ballots, receipts = {}, []
    for path in paths:
        for kind, seq, ts, frm, p, form in load(path):
            rec = {"seq": seq, "ts": ts, "from": frm, "p": p, "form": form}
            if kind == "ballot":
                ballots[seq] = rec
            else:
                receipts.append(rec)

    bl = sorted(ballots.values(), key=lambda r: r["seq"])
    # de-duplicate rulings by request_id: overlapping exports repeat messages
    rc_by_rid = {}
    for r in sorted(receipts, key=lambda r: r["seq"]):
        rid = r["p"].get("request_id")
        if rid:
            rc_by_rid.setdefault(rid, r)
    rc = sorted(rc_by_rid.values(), key=lambda r: r["seq"])
    forms = collections.Counter(r["form"] for r in rc)
    print(f"ballots {len(bl)}  distinct rulings {len(rc)}  by form {dict(forms)}")
    if not bl or not rc:
        sys.exit("need both ballots and receipts")
    print("ballot fields :", sorted(bl[0]["p"]))
    print(f"ballot span : {bl[0]['ts']} .. {bl[-1]['ts']}")
    print(f"receipt span: {rc[0]['ts']} .. {rc[-1]['ts']}")
    off = collections.Counter(r["from"] for r in rc if r["from"] != REFEREE)
    print(f"rulings not from the LAUNCH.md referee DID: {sum(off.values())} {dict(off)}")

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
        b = by_rid.get(r["p"].get("request_id"))
        if b is None:
            unresolved[st] += 1
            continue
        if r["p"].get("sender_did") and b["p"].get("voter_did") \
           and r["p"]["sender_did"] != b["p"]["voter_did"]:
            mismatch += 1
        resolved[(b["p"].get("entry_id"), st)] += 1
    print(f"sender_did/voter_did mismatches on joined rows: {mismatch}")
    print(f"rulings whose request_id is not on the tape we hold: {dict(unresolved)}")

    print("\n=== per-entry outcome, INCLUDING ballots with no ruling of either form ===")
    ruled = set(r["p"].get("request_id") for r in rc)
    per = collections.Counter(b["p"].get("entry_id") for b in bl)
    print("  %-22s %7s %9s %9s %9s" % ("entry", "ballots", "accepted", "rejected", "unruled"))
    for entry, n in per.most_common():
        acc = resolved.get((entry, "accepted"), 0)
        rej = resolved.get((entry, "rejected"), 0)
        unr = sum(1 for b in bl
                  if b["p"].get("entry_id") == entry and b["p"].get("request_id") not in ruled)
        print("  %-22s %7d %9d %9d %9d" % (entry, n, acc, rej, unr))
    backlog = sum(1 for b in bl if b["p"].get("request_id") not in ruled)
    print(f"  BACKLOG (ballots in window with no ruling): {backlog}")

    print("\n=== rejection reasons ===")
    for reason, n in collections.Counter(
            r["p"].get("reason") for r in rc if r["p"].get("status") == "rejected").most_common():
        print(f"  {n:<6} {reason!r}")
    notes = collections.Counter(r["p"].get("note") for r in rc if r["p"].get("note"))
    if notes:
        print("=== batch notes ===")
        for note, n in notes.most_common():
            print(f"  {n:<6} {note!r}")

    print("\n=== intake cursor and lag (SINGULAR receipts only - see module docstring) ===")
    ras = [r["p"]["received_at"] for r in rc if r["p"].get("received_at")]
    if not ras:
        print("  no receipt in this window carries received_at; cursor unmeasurable")
        return
    f = lambda u: datetime.datetime.fromtimestamp(u, datetime.timezone.utc).isoformat()
    print(f"  cursor covers {len(ras)} of {len(rc)} rulings: {f(min(ras))} .. {f(max(ras))}")
    lat = sorted(datetime.datetime.fromisoformat(r["ts"].replace("Z", "+00:00")).timestamp()
                 - r["p"]["received_at"] for r in rc if r["p"].get("received_at"))
    print("  lag s: min %.0f p50 %.0f p90 %.0f max %.0f  (p50 = %.2f h)"
          % (lat[0], statistics.median(lat), lat[int(.9 * len(lat))], lat[-1],
             statistics.median(lat) / 3600))
    head = datetime.datetime.fromisoformat(bl[-1]["ts"].replace("Z", "+00:00")).timestamp()
    print("  singular-path cursor is behind the tape head by %.2f h" % ((head - max(ras)) / 3600))
    print("  NOTE: this cursor does NOT measure the batched path and understates the referee.")


if __name__ == "__main__":
    main(sys.argv[1:] or ["_r123_votes_export.jsonl"])
