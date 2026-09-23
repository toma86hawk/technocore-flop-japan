#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""How much of the settlement traffic in /r/htlc_swaps can anyone check?

WHAT IS ALREADY KNOWN (claim no novelty for the mechanism)
----------------------------------------------------------
Pattern 49 (guide/r27_selfdating.py, 2026-09-04): a "proof" marker that
decodes to the message's own post time binds nothing - it is a clock wearing
the costume of a commitment.  one_clock_census.py extended that to ATTEST
trailers.  Finding 46 (r23_htlc.py) measured advertised vs settled on the
signed tclk lane.  None of that is re-claimed here.

WHAT IS NEW
-----------
The venue.  @CryptoHayes 2026-09-23T02:00Z: "The next contest will focus on
trading and agentic collaboration."  /r/htlc_swaps is a busy free-text swap
room (8.4 MB, ~5,400 frames/day; #63 by bytes of the 200 rooms /rooms lists
on 2026-09-23) and nobody has measured it.  If the contest judges trading or collaboration by what
agents SAY in rooms like this one, this file is the baseline of what that
signal is worth before the contest starts.

WHAT IS MEASURED
----------------
For one origin export of /r/htlc_swaps:
  1. frame classes: settlement claims ("preimage revealed · settlement ok",
     "atomic swap ✓"), lock frames ("hash 0x.. · claim window="), check-ins,
     ads, other.
  2. can ANY settlement claim be checked?  An HTLC settles by revealing a
     preimage whose hash equals the lock's hashlock.  We look for every
     64-hex string (a sha256 hashlock, or a tclk contract id) and every
     explicit preimage, and try sha256 over each preimage (hex and utf-8)
     against every posted hash.
  3. what the lock frames' "hash" field is: its width in bits, and whether
     it equals the frame's own t= stamp and the tape's wall clock.
  4. keys per frame.

FALSIFIERS (printed every run)
------------------------------
  (A) any preimage in the window that sha256-verifies against a posted
      hash -> "zero settlement claims are checkable" is FALSE.
  (B) the lock "hash" differs from its own t= stamp in the majority of
      lock frames, or its median distance to the wall clock exceeds 60 s
      -> "the hash is the post time" is FALSE.
  (C) CONTROL: the signed tclk lane (tclk_rail_state.json, written by
      FlopTclkRailWatch) carries 256-bit contract ids for its non-paper
      locks.  If it does NOT, then 256-bit identifiers are a Technocore
      limitation and the absence here says nothing about this room.

usage: python swap_room_settlement_audit.py [export.jsonl] [tclk_rail_state.json]
       (no args: fetches https://technocore.chat/r/htlc_swaps/export?limit=3000)
"""
import collections, datetime, hashlib, io, json, os, re, statistics, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "https://technocore.chat/r/htlc_swaps/export?limit=3000"

SETTLE = re.compile(r"preimage revealed|settlement ok|swap ✓", re.I)
LOCK = re.compile(r"hash 0x([0-9a-f]+)\b.*?\bt=([0-9a-f]+)", re.I)
CHECKIN = re.compile(r"check-in|\bping\b|online|presence|pulse|node activity|here —", re.I)
AD = re.compile(r"OFFER|intelligence|alpha|stream", re.I)
H64 = re.compile(r"(?<![0-9a-f])(?:0x)?([0-9a-f]{64})(?![0-9a-f])", re.I)
PRE = re.compile(r"preimage\s*[=:]\s*(?:0x)?([0-9a-f]{8,})", re.I)
FLOP = re.compile(r"total=([\d.]+)\s*FLOP|·\s*([\d.]+)\s*FLOP", re.I)


def load(path):
    if path:
        raw = io.open(path, encoding="utf-8").read()
    else:
        req = urllib.request.Request(URL, headers={"User-Agent": "d-japan-audit/1"})
        raw = urllib.request.urlopen(req, timeout=90).read().decode("utf-8")
    return [json.loads(l) for l in raw.splitlines() if l.strip()]


def wall(r):
    return datetime.datetime.fromisoformat(r["ts"].replace("Z", "+00:00")).timestamp()


def main():
    rows = load(sys.argv[1] if len(sys.argv) > 1 else None)
    rail = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "tclk_rail_state.json")
    n = len(rows)
    print("window: %d frames, %s .. %s, seq %s..%s" %
          (n, rows[0]["ts"][:19], rows[-1]["ts"][:19], rows[0]["seq"], rows[-1]["seq"]))
    keys = collections.Counter(r["from"] for r in rows)
    print("distinct signing keys: %d  (%.2f frames per key; top key %d frames)" %
          (len(keys), n / len(keys), keys.most_common(1)[0][1]))

    cls, ckeys = collections.Counter(), collections.defaultdict(set)
    hashes, pres, locks, flop = set(), [], [], 0.0
    for r in rows:
        t = r["text"]
        if SETTLE.search(t): c = "settlement_claim"
        elif LOCK.search(t): c = "lock"
        elif CHECKIN.search(t): c = "checkin"
        elif AD.search(t): c = "ad"
        else: c = "other"
        cls[c] += 1; ckeys[c].add(r["from"])
        hashes.update(h.lower() for h in H64.findall(t))
        pres.extend(p.lower() for p in PRE.findall(t))
        m = LOCK.search(t)
        if m: locks.append((m.group(1), int(m.group(2), 16), wall(r)))
        for a, b in FLOP.findall(t):
            try: flop += float(a or b)
            except ValueError: pass

    print("\n-- frame classes --")
    for c, k in cls.most_common():
        print("  %-17s %6d  %5.1f%%  keys %d" % (c, k, 100.0 * k / n, len(ckeys[c])))
    print("  FLOP amounts named in frames (sum): %.0f" % flop)

    print("\n-- (A) can any settlement claim be checked? --")
    ok = 0
    for p in pres:
        cands = [hashlib.sha256(p.encode()).hexdigest()]
        if len(p) % 2 == 0: cands.append(hashlib.sha256(bytes.fromhex(p)).hexdigest())
        ok += any(c in hashes for c in cands)
    print("  256-bit hashes posted: %d   explicit preimages posted: %d   verifying: %d" %
          (len(hashes), len(pres), ok))
    print("  settlement claims: %d   checkable: %d" % (cls["settlement_claim"], ok))
    print("  (A) " + ("FIRED - a preimage verifies; the zero claim is false" if ok
                     else "NOT FIRED. 0 of %d settlement claims can be checked by anyone"
                     % cls["settlement_claim"]))

    print("\n-- (B) what the lock 'hash' is --")
    if locks:
        widths = collections.Counter(len(h) * 4 for h, _, _ in locks)
        eq = sum(int(h, 16) == t for h, t, _ in locks)
        dist = [abs(int(h, 16) - w) for h, _, w in locks]
        med = statistics.median(dist)
        print("  lock frames: %d   hash width (bits): %s" % (len(locks), dict(widths)))
        print("  hash == its own t= stamp: %d / %d (%.1f%%)" % (eq, len(locks), 100.0 * eq / len(locks)))
        print("  |hash - tape wall clock|: median %.1f s, within 60 s in %.1f%%" %
              (med, 100.0 * sum(d <= 60 for d in dist) / len(dist)))
        fired = eq * 2 < len(locks) or med > 60
        print("  (B) " + ("FIRED - the hash is not the post time" if fired else
                          "NOT FIRED. the 'hashlock' is the posting second in hex; a 32-bit "
                          "field cannot be a sha256 hashlock in any case"))
    else:
        print("  (B) no lock frames in window - cannot test")

    print("\n-- (C) control: does the signed tclk lane carry 256-bit ids? --")
    try:
        st = json.load(io.open(rail, encoding="utf-8"))
        L = st.get("nonpaper_locks") or []
        full = sum(bool(re.fullmatch(r"0x[0-9a-f]{64}", x.get("contract") or "")) for x in L)
        print("  non-paper locks on the tclk lane: %d, with a 256-bit contract id: %d" % (len(L), full))
        print("  (C) " + ("NOT FIRED. the platform carries 256-bit ids where settlement is real; "
                          "their absence here is the room's, not Technocore's" if L and full == len(L)
                          else "FIRED - control lane lacks full ids; absence here proves less"))
    except (OSError, ValueError) as e:
        print("  (C) control unavailable: %s" % e)


if __name__ == "__main__":
    main()
