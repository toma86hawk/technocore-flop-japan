#!/usr/bin/env python3
"""Independent replication of The Call (overheard-five.vercel.app/prediction).

The market's author states the property plainly: "Read the room, run the public
rules file, and you'll get exactly what the page shows." This script tests that
claim. It is a line-for-line Python port of the published rules in
https://overheard-five.vercel.app/call.js (foldMarket), applied to the room read
through three different paths:

  A. https://technocore.chat/r/overheard-calls/export   the room itself (JSONL)
  B. https://overheard-five.vercel.app/api/calls        what the page folds
  C. https://overheard-five.vercel.app/api/room         the app's other reader

The rules are deterministic and all three folds run identical code, so any
disagreement in the output is a disagreement about which messages were supplied,
not about how they were counted.

Verified against the author's own unmodified call.js under node: identical
totals on all three inputs (2026-09-08).

    python call_fold.py            # fetch live and compare the three paths
    python call_fold.py room.jsonl # fold one saved JSONL file
"""
import datetime
import json
import re
import sys
import urllib.request

PREFIX = "call1 "
MARKET = "flop-mainnet-2027"
TAP = 1000
SHOP = "did:key:z6MkiuhfekPgiihLWarPAzhuvoMjg86F8dqmLiCTmtQgMrR3"
SIDES = ("yes", "no")
DID_RE = re.compile(r"^did:key:z6Mk[1-9A-HJ-NP-Za-km-z]{44}$")
CLOSES_MS = int(datetime.datetime(2027, 3, 31, 23, 59, 59, 999000,
                                  tzinfo=datetime.timezone.utc).timestamp() * 1000)

ROOM_EXPORT = "https://technocore.chat/r/overheard-calls/export"
API_CALLS = "https://overheard-five.vercel.app/api/calls"
API_ROOM = "https://overheard-five.vercel.app/api/room?room=overheard-calls"


def read_call(text):
    s = text or ""
    if not s.startswith(PREFIX):
        return None
    try:
        b = json.loads(s[len(PREFIX):])
    except Exception:
        return None
    return b if isinstance(b, dict) else None


def whole(v):
    """Paper is whole numbers. Untrimmed, exactly as the rules file has it."""
    s = "" if v is None else str(v)
    if not re.fullmatch(r"[0-9]{1,9}", s):
        return None
    n = int(s)
    return n if n > 0 else None


def parse_ms(ts):
    if not ts:
        return 0
    try:
        return int(datetime.datetime.fromisoformat(
            str(ts).replace("Z", "+00:00")).timestamp() * 1000)
    except Exception:
        return 0


def fold(messages, market=MARKET, closes=CLOSES_MS, shop=SHOP):
    rows = sorted(({**m, "seq": int(m.get("seq") or 0), "at": parse_ms(m.get("ts"))}
                   for m in messages), key=lambda r: (r["seq"], r["at"]))
    by, refused, ledger = {}, [], []
    settled, calls = None, 0

    def seat(did):
        return by.setdefault(did, {"did": did, "tapped": 0, "yes": 0, "no": 0,
                                   "put": 0, "calls": 0, "last": 0})

    def no(m, why):
        refused.append({"from": m.get("from"), "seq": m["seq"], "why": why})

    for m in rows:
        b = read_call(m.get("text"))
        if not b or b.get("market") != market:
            continue
        f = m.get("from")
        # from inside the body is a claim; the transport's from is who signed.
        if not isinstance(f, str) or not f or not DID_RE.match(f):
            continue
        if m.get("sig", "ABSENT") is None or m.get("signed") is False:
            no(m, "no signature behind this frame")
            continue
        if b.get("from") != f:
            no(m, "the frame names a different author than the key that signed it")
            continue

        if b.get("type") == "settle":
            if f != shop:
                no(m, "only the shop can settle this")
            elif settled:
                no(m, "this market is already settled")
            elif b.get("outcome") not in SIDES:
                no(m, "a settlement has to name yes or no")
            else:
                settled = {"outcome": b["outcome"], "at": m["at"], "ts": m["ts"]}
            continue

        if settled:
            no(m, "the market was already settled")
            continue
        if m["at"] and m["at"] > closes:
            no(m, "the question had closed")
            continue

        if b.get("type") == "tap":
            who = seat(f)
            if who["tapped"]:
                no(m, "this key has already taken its paper")
                continue
            who["tapped"] = TAP
            who["last"] = max(who["last"], m["at"])
            continue

        if b.get("type") == "call":
            if b.get("side") not in SIDES:
                no(m, "a call has to be on yes or no")
                continue
            put = whole(b.get("put"))
            if put is None:
                no(m, "the amount is not a whole number of paper")
                continue
            who = seat(f)
            if not who["tapped"]:
                # The tap comes first. A windowed reader that drops the tap
                # turns this honest call into a refusal - see compare().
                no(m, "this key has no paper - the tap comes first")
                continue
            left = who["tapped"] - who["put"]
            if put > left:
                no(m, "only %d paper left, and this call was for %d" % (left, put))
                continue
            who[b["side"]] += put
            who["put"] += put
            who["calls"] += 1
            who["last"] = max(who["last"], m["at"])
            ledger.append({"did": f, "side": b["side"], "put": put, "seq": m["seq"]})
            calls += 1

    people = [r for r in by.values() if r["put"] > 0]
    yes = sum(r["yes"] for r in people)
    no_ = sum(r["no"] for r in people)
    pool = yes + no_
    for r in people:
        r["ifYes"] = (r["yes"] / yes) * pool if yes else 0
        r["ifNo"] = (r["no"] / no_) * pool if no_ else 0
        side = None if (r["yes"] and r["no"]) else ("yes" if r["yes"] else "no")
        r["sideTaken"] = side
        r["multiple"] = ((r["ifYes"] if side == "yes" else r["ifNo"]) / r["put"]) if side else None
    return {"settled": settled, "refused": refused, "calls": calls, "ledger": ledger,
            "yes": yes, "no": no_, "total": pool, "volume": pool,
            "share": (yes / pool) if pool else None,
            "people": len(people),
            "tapped": len([r for r in by.values() if r["tapped"] > 0]),
            "standings": sorted(people, key=lambda r: (-r["put"], -r["last"])),
            "by": by}


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "call-fold/1.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode("utf-8", "replace")


def _line(name, msgs, f):
    share = "null" if f["share"] is None else "%.1f%%" % (100 * f["share"])
    window = ""
    seqs = [int(m.get("seq") or 0) for m in msgs]
    if seqs:
        window = "seq %d..%d" % (min(seqs), max(seqs))
    print("%-34s msgs %4d  %-16s YES %6d  NO %6d  pool %6d  share %6s  people %4d  refused %2d"
          % (name, len(msgs), window, f["yes"], f["no"], f["total"], share,
             f["people"], len(f["refused"])))


def compare():
    room = [json.loads(l) for l in _get(ROOM_EXPORT).splitlines() if l.strip()]
    page = json.loads(_get(API_CALLS))
    app = json.loads(_get(API_ROOM))
    print("checked %s\n" % datetime.datetime.now(datetime.timezone.utc).isoformat())
    folds = []
    for name, msgs in (("A room /r/<room>/export", room),
                       ("B page /api/calls", page.get("frames") or []),
                       ("C app  /api/room", app.get("messages") or [])):
        f = fold(msgs)
        _line(name, msgs, f)
        folds.append((name, msgs, f))
    print("\n/api/calls says truncated=%s source=%s archived=%s"
          % (page.get("truncated"), page.get("source"), page.get("archived")))

    # Are the shared messages actually the same bytes? If yes, the divergence
    # above is entirely about supply, and nothing here is a content dispute.
    byseq = {int(m.get("seq") or 0): m.get("text") for m in room}
    for name, msgs, _f in folds[1:]:
        diff = sum(1 for m in msgs if byseq.get(int(m.get("seq") or 0)) != m.get("text"))
        absent = len(byseq) - len([m for m in msgs if int(m.get("seq") or 0) in byseq])
        print("%-34s bytes differing from the room at the same seq: %d   room messages it omits: %d"
              % (name, diff, absent))

    # Refusals the narrower readers invent because a tap fell out of the window.
    print()
    for name, _m, f in folds:
        n = sum(1 for r in f["refused"] if "tap comes first" in r["why"])
        print("%-34s calls refused for 'no paper - the tap comes first': %d" % (name, n))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        msgs = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
        f = fold(msgs)
        _line(sys.argv[1], msgs, f)
    else:
        compare()
