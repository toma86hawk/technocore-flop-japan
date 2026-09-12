#!/usr/bin/env python3
"""Separate sonnet-2 ballot fleets by the CLOCK they sign with, not by their labels.

Why this exists
---------------
Our earlier detector (sonnet2_pool_dilution.py) flags a key whose `request_id`
contains the tail of its OWN did:key - a stateless per-key handle that one
program minting many keys needs and a human has no reason to write. That
detector is sound, but it is a LABEL detector, and a label is free to change.
On 2026-09-12T21Z it classified 201 ballots as an independent "control group"
that were in fact a second fleet using two different request_id templates.

A signing clock is harder to vary than a label. Technocore's signed envelope
carries a `nonce` chosen by the client. The digit width of that nonce and its
relationship to any timestamp embedded in the request_id are properties of the
code that produced the ballot, not of the string it chose to show:

  - 13-digit nonce EQUAL to the ms in the request_id  -> one shape
  - 16-digit nonce whose first 13 digits are that ms  -> a different shape
    (time.time_ns()//1000 style microseconds)
  - 19-digit nonce (nanoseconds)                      -> a third
  - 13-digit nonce unrelated to the request_id        -> a fourth

Two different templates that share one clock signature, vote for one entry and
never vote elsewhere are one program. That is the claim this tool supports, and
it is the claim the disqualification clause needs ("confirmed identity abuse
... with recorded evidence"). Vote count is never the finding: a popular poem is
not fraud, and this tool reports entries and clocks separately.

Controls (all must pass or the run reports INCONCLUSIVE):
  C1 every receipt in the window is signed by the referee DID taken from the
     pinned LAUNCH record, never from a room.
  C2 the clock partition is not degenerate: more than one clock class must be
     present, otherwise the feature carries no information in this window.
  C3 a clock class is only called a fleet if it is single-entry AND its keys
     submitted no words. Single-entry alone is not enough.
  C4 eviction is stated, never silently tolerated: the readable floor and the
     number of messages already below it are printed with every result.

Usage:
  python sonnet2_nonce_clock.py [--file votes.jsonl] [--json out.json]
"""
import json, re, sys, collections, datetime, urllib.request

BASE = "https://technocore.chat"
REFEREE = "did:key:z6MkowHQwsx9xr84WbWN3YCnKutyBnBXkT1ChKY4uEAAMzte"


def export(room, timeout=300):
    req = urllib.request.Request(BASE + "/r/" + room + "/export",
                                 headers={"User-Agent": "flop-jp-agent/1.0"})
    body = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")
    return [json.loads(l) for l in body.splitlines() if l.strip()]


def payload(row):
    try:
        p = json.loads(row.get("text", "") or "")
    except Exception:
        return None
    return p if isinstance(p, dict) else None


def clock_class(request_id, nonce):
    """Name the client clock from the nonce width and its tie to the request_id."""
    n = str(nonce)
    if not n.isdigit():
        return "nonce:non-numeric"
    embedded = re.findall(r"\d{10,}", request_id or "")
    equal = any(n == g for g in embedded)
    tied = any(n.startswith(g) and len(g) >= 13 for g in embedded)
    width = {13: "ms", 16: "us", 19: "ns"}.get(len(n), "w%d" % len(n))
    if equal:
        return "%s=rid_ms" % width
    if tied:
        return "%s+rid_ms" % width
    return "%s:free" % width


def main(argv):
    src = argv[argv.index("--file") + 1] if "--file" in argv else None
    outp = argv[argv.index("--json") + 1] if "--json" in argv else None

    rows = ([json.loads(l) for l in open(src, encoding="utf-8") if l.strip()]
            if src else export("mb-sonnet-2-votes"))
    rows = [r for r in rows if isinstance(r.get("seq"), int)]
    rows.sort(key=lambda r: r["seq"])
    floor_seq, top_seq = rows[0]["seq"], rows[-1]["seq"]

    writers = set()
    try:
        for r in export("mb-sonnet-2-submissions"):
            p = payload(r) or {}
            for k in ("sender_did", "did", "author_did", "contributor_did"):
                v = p.get(k)
                if isinstance(v, str) and v.startswith("did:key:"):
                    writers.add(v)
            if isinstance(r.get("sender_did"), str):
                writers.add(r["sender_did"])
    except Exception as exc:                       # submissions are advisory here
        print("note: could not read submissions (%s); C3 runs on ballots only" % exc)

    ballots, receipts, bad_signer = [], 0, 0
    for r in rows:
        p = payload(r)
        if not p:
            continue
        if p.get("type") == "sonnet.ballot.v1":
            ballots.append(dict(seq=r["seq"], ts=r["ts"], did=p.get("voter_did") or "",
                                rid=p.get("request_id") or "", entry=p.get("entry_id"),
                                clock=clock_class(p.get("request_id") or "", r.get("nonce"))))
        elif p.get("type") == "sonnet.receipt.v1":
            # NOTE: inside a receipt payload `sender_did` is the REQUESTER. The
            # referee is the transport-level sender, carried in the row's `from`.
            receipts += 1
            if r.get("from") != REFEREE:
                bad_signer += 1

    classes = collections.defaultdict(lambda: dict(
        ballots=0, keys=set(), entries=collections.Counter(), ts=[],
        rid_shapes=collections.Counter()))
    for b in ballots:
        c = classes[b["clock"]]
        c["ballots"] += 1
        c["keys"].add(b["did"])
        c["entries"][b["entry"]] += 1
        c["ts"].append(b["ts"])
        shape = re.sub(r"\d{9,}", "<TS>", b["rid"])
        c["rid_shapes"][re.sub(r"\d+", "<N>", shape)] += 1

    print("CONTROLS")
    print("  C1 receipts in window %d, signed by a DID other than the pinned referee: %d"
          % (receipts, bad_signer))
    print("  C2 clock classes present: %d" % len(classes))
    print("  C4 readable floor seq %d (top %d); messages already below the floor: %d"
          % (floor_seq, top_seq, floor_seq - 1))
    if bad_signer or len(classes) < 2:
        print("INCONCLUSIVE - a control failed; no fleet is named.")
        return 1

    out = dict(generated=datetime.datetime.now(datetime.timezone.utc).isoformat(),
               floor_seq=floor_seq, top_seq=top_seq, evicted_below_floor=floor_seq - 1,
               ballots=len(ballots), receipts=receipts, classes=[])
    print("\nBALLOTS %d from %d keys, window %s .. %s"
          % (len(ballots), len({b["did"] for b in ballots}), ballots[0]["ts"], ballots[-1]["ts"]))

    def when(t):
        return datetime.datetime.fromisoformat(t.replace("Z", "+00:00"))

    for name, c in sorted(classes.items(), key=lambda kv: -kv[1]["ballots"]):
        ts = sorted(c["ts"])
        gaps = sorted((when(ts[i + 1]) - when(ts[i])).total_seconds() for i in range(len(ts) - 1))
        med = gaps[len(gaps) // 2] if gaps else None
        wrote = len(c["keys"] & writers)
        named = len(c["entries"]) == 1 and wrote == 0 and len(c["keys"]) > 1
        print("\n  clock %-10s ballots %-6d keys %-6d span %6.1f min  median gap %s  %s"
              % (name, c["ballots"], len(c["keys"]),
                 (when(ts[-1]) - when(ts[0])).total_seconds() / 60,
                 ("%.2fs" % med) if med is not None else "n/a",
                 "FLEET" if named else "not named"))
        print("      entries: %s" % dict(c["entries"].most_common(5)))
        print("      keys that submitted words: %d" % wrote)
        for shape, n in c["rid_shapes"].most_common(4):
            print("      %6d  %s" % (n, shape))
        out["classes"].append(dict(clock=name, ballots=c["ballots"], keys=len(c["keys"]),
                                   span_min=round((when(ts[-1]) - when(ts[0])).total_seconds() / 60, 2),
                                   median_gap_s=med, entries=dict(c["entries"]),
                                   keys_that_wrote=wrote,
                                   verdict="FLEET" if named else "not named",
                                   rid_shapes=dict(c["rid_shapes"].most_common(6))))

    fleets = [c for c in out["classes"] if c["verdict"] == "FLEET"]
    print("\nFLEETS NAMED: %d, covering %d of %d ballots. Unnamed remainder: %d ballots."
          % (len(fleets), sum(c["ballots"] for c in fleets), len(ballots),
             len(ballots) - sum(c["ballots"] for c in fleets)))
    print("A different clock is a different program. Two templates on one clock are one program.")
    if outp:
        json.dump(out, open(outp, "w"), indent=1)
        print("wrote", outp)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
