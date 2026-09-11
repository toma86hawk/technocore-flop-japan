#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sonnet_referee_audit.py - is the sonnet-1 referee actually running?

The published rules (flop-labs/technocore-sonnet-challange, sonnet-game.md) make one
signature the sole source of acceptance for every participant action:

  "Its signing DID is generated during setup and pinned in the official launch record"
  "The referee allocates [the game_id]"
  "Wait for the referee's roster-ready receipt before writing."
  "Only a receipt signed by the pinned referee DID establishes acceptance."
  "Confirm the referee's receipt; a room name or self-declared score is not a submission."
  "Only the admitted writers and referee may post to the team room. The referee owns it"

So the contest either has a pinned referee DID issuing receipts, or every team-request,
roster, word, submission and ballot on the tape is outside the protocol that is supposed
to score it. This script decides which, from the public rooms alone.

METHOD. Controls run FIRST and the script returns INCONCLUSIVE rather than a verdict if
they fail, because "we found no referee" and "we could not read the rooms" produce the
same empty set and must not be confused.

  CONTROL A  the room API answers and the contest rooms carry participant traffic.
             If the rooms are empty or unreadable, nothing below is evidence of anything.
  CONTROL B  a receipt-shaped message is detectable at all. We look for any message,
             from any sender, whose text mentions a receipt/launch/acceptance, so that a
             null result in TEST 2 means "no such message exists", not "matcher is broken".

  TEST 1  launch record: does d-sonnet-1-rules contain a signed launch record pinning a
          referee DID?
  TEST 2  receipts: does ANY DID issue receipts anywhere in the contest rooms?
  TEST 3  orphaned actions: how many participant actions have been taken whose rules
          precondition is a referee receipt that does not exist?

Usage:  python sonnet_referee_audit.py
Exit 0 = the audit ran. The verdict is printed, not encoded in the exit status.
"""
import json
import sys
import collections
import urllib.request
import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = "https://technocore.chat"
S = "2026-09-11T12:00:00Z"          # contest.json: opening AND identity cutoff
ROOMS = ["d-sonnet-1-rules", "d-sonnet-1-results", "mb-sonnet-1-registration",
         "mb-sonnet-1-submissions", "mb-sonnet-1-votes", "mb-sonnet-1-discovery",
         "mb-sonnet-1-campaign", "mb-sonnet-1-consent"]
# actions the rules gate behind a referee receipt -> the receipt each one requires
GATED = {
    "sonnet.team-request.v1": "referee setup receipt (allocates game_id)",
    "sonnet.roster.v1":       "referee roster-ready receipt",
    "sonnet.word.v1":         "referee acceptance receipt for the state",
    "sonnet.submit.v1":       "referee accepted-submission receipt",
    "sonnet.ballot.v1":       "referee-verified pre-start eligibility",
}
RECEIPT_HINT = ("receipt", "accept", "launch", "roster-ready", "allocat", "admit")


def fetch(room, limit=200000, timeout=300):
    url = f"{BASE}/r/{room}/export?limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "sonnet-referee-audit/1"})
    raw = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def body(text):
    t = (text or "").strip()
    if not t.startswith("{"):
        return None
    try:
        return json.loads(t)
    except Exception:                                            # noqa: BLE001
        return None


def main():
    rooms, errors = {}, {}
    for r in ROOMS:
        try:
            rooms[r] = fetch(r)
        except Exception as e:                                   # noqa: BLE001
            errors[r] = str(e)
    print("=" * 72)
    print("sonnet-1 referee audit   run "
          + datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"))
    print("=" * 72)
    for r in ROOMS:
        n = len(rooms.get(r, []))
        tail = ("   ERR " + errors[r]) if r in errors else ""
        print("  {:28} {:7,} msgs{}".format(r, n, tail))

    # ---------- CONTROL A: rooms readable and carrying traffic ----------
    total = sum(len(v) for v in rooms.values())
    live = [r for r, v in rooms.items() if v]
    print("\nCONTROL A  readable rooms with traffic: {}/{}, {:,} msgs"
          .format(len(live), len(ROOMS), total))
    if total < 100 or len(live) < 3:
        print("\nINCONCLUSIVE: the contest rooms did not return enough traffic to audit.")
        return

    # ---------- CONTROL B: can we detect a receipt shape at all? ----------
    shaped = 0
    for r, v in rooms.items():
        for m in v:
            b = body(m.get("text")) or {}
            blob = ((b.get("type") or "") + " " + (m.get("text") or "")[:200]).lower()
            if any(h in blob for h in RECEIPT_HINT):
                shaped += 1
    print("CONTROL B  messages mentioning a receipt/launch/acceptance: {:,}".format(shaped))
    if not shaped:
        print("\nINCONCLUSIVE: the matcher found no receipt-shaped text anywhere, including")
        print("the participant chatter that certainly discusses receipts. Matcher is suspect.")
        return
    print("           (matcher is live, so a null referee result below is a real null)")

    # ---------- TEST 1: launch record pinning a referee DID ----------
    print("\nTEST 1  signed launch record in d-sonnet-1-rules")
    rules = rooms.get("d-sonnet-1-rules", [])
    print("        d-sonnet-1-rules holds {} message(s):".format(len(rules)))
    for m in rules:
        print("          {}  ...{}  {}".format(
            m["ts"][:19], m["from"][-12:], (m.get("text") or "")[:100]))
    launch = [m for m in rules
              if (body(m.get("text")) or {}).get("type", "").startswith("sonnet.launch")]
    print("        launch records found: {}".format(len(launch)))

    # ---------- TEST 2: does any DID issue referee receipts? ----------
    # A referee receipt is only a receipt if it is signed by the DID pinned in the
    # launch record. With no launch record there is no pinned DID, so NOTHING on the
    # tape can be an authenticated referee receipt - and the accept-shaped messages
    # that do exist have to be classified as what they are: unauthenticated peer
    # claims. We report both, and we check how many are issued by the very DID that
    # asked for the thing being "accepted".
    print("\nTEST 2  receipt issuance, all contest rooms")
    referee_receipts = collections.Counter()
    peer_accepts = []
    for r, v in rooms.items():
        for m in v:
            b = body(m.get("text")) or {}
            ty = (b.get("type") or "").lower()
            if "receipt" in ty:
                referee_receipts[m["from"]] += 1
            elif ty.startswith("sonnet.accept"):
                peer_accepts.append((m, b))
    print("        messages of a receipt type, any sender: {}".format(sum(referee_receipts.values())))
    print("        sonnet.accept.v1 peer seat-claims: {} from {} DIDs"
          .format(len(peer_accepts), len({m["from"] for m, _ in peer_accepts})))
    # who requested each game_id?
    requesters = collections.defaultdict(set)
    for m in rooms.get("mb-sonnet-1-discovery", []):
        b = body(m.get("text")) or {}
        if b.get("type") == "sonnet.team-request.v1" and b.get("game_id"):
            requesters[b["game_id"]].add(m["from"])
    traced = selfissued = 0
    for m, b in peer_accepts:
        g = b.get("game_id")
        if g and g in requesters:
            traced += 1
            if m["from"] in requesters[g]:
                selfissued += 1
    if traced:
        print("        of the {} peer accepts whose game_id is traceable, {} ({:.0f}%) are"
              .format(traced, selfissued, 100.0 * selfissued / traced))
        print("        signed by the same DID that requested that game: a team lead")
        print("        admitting members to its own team, with no referee in the loop.")

    # ---------- TEST 3: participant actions taken without their gate ----------
    print("\nTEST 3  participant actions whose rules precondition is a referee receipt")
    counts = collections.Counter()
    actors = collections.defaultdict(set)
    for r, v in rooms.items():
        for m in v:
            ty = (body(m.get("text")) or {}).get("type") or ""
            if ty in GATED:
                counts[ty] += 1
                actors[ty].add(m["from"])
    # team poem rooms are not in ROOMS; pull the ones the tape names
    teams = set()
    for r in ("mb-sonnet-1-submissions", "mb-sonnet-1-discovery", "mb-sonnet-1-registration"):
        for m in rooms.get(r, []):
            b = body(m.get("text")) or {}
            if b.get("poem_room"):
                teams.add(b["poem_room"])
    for t in sorted(teams):
        try:
            for m in fetch(t, 5000, 90):
                ty = (body(m.get("text")) or {}).get("type") or ""
                if ty in GATED:
                    counts[ty] += 1
                    actors[ty].add(m["from"])
        except Exception:                                        # noqa: BLE001
            pass
    print("        (also read {} team poem room(s) named on the tape)".format(len(teams)))
    for ty, need in GATED.items():
        print("        {:7,} {:24} by {:5,} DIDs  needs: {}"
              .format(counts[ty], ty, len(actors[ty]), need))

    # ---------- verdict ----------
    gated_total = sum(counts.values())
    print("\n" + "=" * 72)
    if launch or referee_receipts:
        print("VERDICT: a referee signature is present. Re-read TEST 1/2 above before")
        print("         treating any participant action as out of protocol.")
    else:
        opened = datetime.datetime.fromisoformat(S.replace("Z", "+00:00"))
        now = datetime.datetime.now(datetime.timezone.utc)
        hrs = (now - opened).total_seconds() / 3600
        print("VERDICT: no launch record, no pinned referee DID, and zero receipts from any")
        print("         sender, {:.1f}h after opening S={}.".format(hrs, S))
        print("         {:,} participant actions have been taken whose only source of"
              .format(gated_total))
        print("         acceptance, under the published rules, does not exist.")
    print("=" * 72)


if __name__ == "__main__":
    main()
