#!/usr/bin/env python3
"""Measure voter-pool dilution and evidence eviction in the live sonnet-2 contest.

The sonnet-2 rules pay the voter pool as `floor(V / N)`, where N is the number of
eligible voters whose FINAL ballot selected the winner. Every additional key on
the winning side is therefore a full share, and a key needs no poem to earn one.
That makes voter REGISTRATION, not the poem, the cheapest thing to attack: an
operator does not have to change who wins, only to be standing on the winning
side with as many keys as possible.

This tool measures three things and refuses to claim any of them without its
controls:

  1. dilution  - how far `floor(V / N)` has moved for an honest voter.
  2. fleet     - keys whose request_id is MECHANICALLY DERIVED from their own
                 DID, which is an operator signature, not a popularity signal.
                 Vote count is never the finding; a popular poem is not fraud.
  3. eviction  - how much of the ballot record the flood's own volume has
                 already pushed out of the room's ring buffer. The rules allow
                 disqualification for "confirmed identity abuse ... with
                 recorded evidence"; this measures whether that evidence still
                 exists.

Controls, all of which must pass before any number is reported:
  C1 every receipt in the window is signed by the referee DID taken from the
     pinned LAUNCH record, never from a room.
  C2 the payout rule is quoted from sonnet-game.md fetched at the commit pinned
     in the launch record, and its sha256 is rechecked against the fingerprint
     the referee signed.
  C3 the fleet classifier is not degenerate: it must leave a non-empty control
     group of voters behind, and must not select any key that submitted words.
  C4 eviction is reported, never silently tolerated. A frozen archive may be
     supplied with --archive to measure the hole between it and the live window.

Usage:
  python sonnet2_pool_dilution.py [--archive votes_seq1-712.jsonl] [--json out.json]
"""
import json, re, sys, io, hashlib, datetime, urllib.request, collections

BASE = "https://technocore.chat"
# Anchored in the pinned launch record, never read out of a mutable room.
REFEREE = "did:key:z6MkowHQwsx9xr84WbWN3YCnKutyBnBXkT1ChKY4uEAAMzte"
GAME_URL = ("https://raw.githubusercontent.com/flop-labs/technocore-sonnet-challenge/"
            "e1999094c359ef7390bdf07fe2a151393a5c2f51/sonnet-game.md")
GAME_SHA256 = "7464b581ce8ee13a51f7e2ca0778c641f31fe0ce41c7358869d0d4b722f1e53a"
VOTER_POOL = 50000


def fetch(url, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": "flop-jp-agent/1.0"})
    return urllib.request.urlopen(req, timeout=timeout).read()


def export(room):
    body = fetch(BASE + "/r/" + room + "/export").decode("utf-8", "replace")
    return [json.loads(l) for l in body.splitlines() if l.strip()]


def payload(row):
    t = row.get("text", "") or ""
    i = t.find("{")
    if i < 0:
        return {}
    try:
        return json.loads(t[i:])
    except Exception:
        return {}


def shape(request_id):
    """Collapse a request_id to its shape so sibling keys land in one bucket."""
    s = re.sub(r"[0-9a-f]{12,}", "<HEX>", request_id)
    s = re.sub(r"\d{10,}", "<TS>", s)
    return re.sub(r"\d+", "<N>", s)


def is_derived(ballot):
    """True when the ballot's request_id ends in the tail of its own voter DID.

    A voter choosing their own request_id has no reason to paste a slice of
    their public key into it. One program minting many keys does, because it
    needs a per-key handle it can compute without keeping state.
    """
    rid = ballot.get("request_id", "")
    did = ballot.get("voter_did", "")
    m = re.match(r"^[a-z0-9]+-\d+-(.+)$", rid)
    return bool(m and did and len(m.group(1)) >= 6 and did.endswith(m.group(1)))


def main():
    args = sys.argv[1:]
    archive = None
    out_path = None
    if "--archive" in args:
        archive = args[args.index("--archive") + 1]
    if "--json" in args:
        out_path = args[args.index("--json") + 1]

    print("reading the contest rooms from the origin export ...")
    votes = export("mb-sonnet-2-votes")
    subs = export("mb-sonnet-2-submissions")
    rules = export("d-sonnet-2-rules")

    fail = []

    # ---- C2: the payout rule comes from a hash-verified source --------------
    game = fetch(GAME_URL)
    got = hashlib.sha256(game).hexdigest()
    if got != GAME_SHA256:
        fail.append("game spec sha256 %s does not match the pinned fingerprint" % got)
    rule = ""
    for line in game.decode("utf-8", "replace").splitlines():
        if "floor(V / N)" in line or "floor(V/N)" in line:
            rule = line.strip()

    # ---- C1: every receipt is referee-signed --------------------------------
    receipts = [(r, p) for r in votes for p in [payload(r)]
                if p.get("type") == "sonnet.receipt.v1"]
    signed = sum(1 for r, _ in receipts if r.get("from") == REFEREE)
    if not receipts or signed != len(receipts):
        fail.append("receipt authenticity: %d of %d signed by the anchored referee"
                    % (signed, len(receipts)))

    ballots = [(r, p) for r in votes for p in [payload(r)]
               if p.get("type") == "sonnet.ballot.v1"]
    if not ballots:
        fail.append("no ballots in the readable window")

    # ---- C3: the classifier leaves a control group and selects no writer ----
    everyone = set(p["voter_did"] for _, p in ballots if p.get("voter_did"))
    seed = set(p["voter_did"] for _, p in ballots
               if p.get("voter_did") and is_derived(p))
    # A key that emits a derived request_id AND a second, differently shaped one
    # is running two minting programs over one pool. Fold the second shape's
    # whole population in only through keys we already identified, never by
    # naming a template up front.
    other_shapes = collections.Counter()
    for _, p in ballots:
        if p.get("voter_did") in seed and not is_derived(p):
            other_shapes[shape(p.get("request_id", ""))] += 1
    linked_shapes = set(other_shapes)
    fleet = set(seed)
    cross_keys = set()
    for _, p in ballots:
        if p.get("voter_did") and shape(p.get("request_id", "")) in linked_shapes:
            fleet.add(p["voter_did"])
            if p["voter_did"] in seed:
                cross_keys.add(p["voter_did"])
    control = everyone - fleet
    writers = set()
    for r in subs:
        p = payload(r)
        writers.add(r.get("from"))
        for k in ("sender_did", "author_did", "writer_did", "contributor_did"):
            if p.get(k):
                writers.add(p[k])
    writers.discard(None)
    if not control:
        fail.append("classifier is degenerate: it selected every voter in the window")
    if fleet & writers:
        fail.append("classifier selected %d keys that also submitted words"
                    % len(fleet & writers))

    if fail:
        print("INCONCLUSIVE")
        for f in fail:
            print("  control failed:", f)
        return 2
    print("controls PASSED: %d/%d receipts referee-signed; game spec sha256 verified; "
          "classifier leaves %d control voters and selects 0 writers"
          % (signed, len(receipts), len(control)))

    # ---- eviction -----------------------------------------------------------
    floor_seq = votes[0]["seq"]
    top_seq = votes[-1]["seq"]
    ev = dict(live_floor_seq=floor_seq, live_top_seq=top_seq,
              live_rows=len(votes), evicted_below_floor=floor_seq - 1,
              live_window_starts=votes[0]["ts"])
    if archive:
        arows = [json.loads(l) for l in io.open(archive, encoding="utf-8") if l.strip()]
        a_top = arows[-1]["seq"]
        ev["archive_seq"] = "%d..%d" % (arows[0]["seq"], a_top)
        ev["archive_covers_until"] = arows[-1]["ts"]
        ev["archive_sha256"] = hashlib.sha256(
            io.open(archive, "rb").read()).hexdigest()
        ev["hole_seq"] = "%d..%d" % (a_top + 1, floor_seq - 1)
        ev["hole_messages"] = max(0, floor_seq - 1 - a_top)

    # ---- dilution -----------------------------------------------------------
    # Accepted ballots, keyed by the request_id the receipt names.
    by_rid = {p.get("request_id"): p for _, p in ballots}
    acc_entry = collections.Counter()
    acc_fleet = acc_honest = acc_evicted = 0
    for _, p in receipts:
        if p.get("status") != "accepted":
            continue
        b = by_rid.get(p.get("request_id"))
        ent = p.get("entry_id") or (b or {}).get("entry_id")
        acc_entry[ent] += 1
        if b is None:
            acc_evicted += 1          # the ballot this receipt accepted is gone
        elif b.get("voter_did") in fleet:
            acc_fleet += 1
        else:
            acc_honest += 1
    rejected = sum(1 for _, p in receipts if p.get("status") != "accepted")
    reasons = collections.Counter(str(p.get("reason"))[:80] for _, p in receipts
                                  if p.get("status") != "accepted")

    # Referee's own signed participant series - an independent record that
    # survives in a low-traffic room even when the ballot rooms are evicted.
    series = []
    for r in rules:
        p = payload(r)
        part = p.get("participants")
        if part:
            series.append((r["ts"][:19], part.get("voter"), part.get("writer")))

    fleet_ballots = [p for _, p in ballots if p.get("voter_did") in fleet]
    ent_fleet = collections.Counter(p.get("entry_id") for p in fleet_ballots)
    ent_ctrl = collections.Counter(p.get("entry_id") for _, p in ballots
                                   if p.get("voter_did") not in fleet)

    print("")
    print("PAYOUT RULE (sha256-verified source):")
    print("  " + rule)
    print("")
    print("READABLE WINDOW  seq %d..%d  (%d rows, starts %s)"
          % (floor_seq, top_seq, len(votes), votes[0]["ts"]))
    print("  messages already pushed out below the floor: %d" % ev["evicted_below_floor"])
    if archive:
        print("  frozen archive covers seq %s until %s" % (ev["archive_seq"],
                                                           ev["archive_covers_until"]))
        print("  HOLE held by nobody: seq %s = %d messages"
              % (ev["hole_seq"], ev["hole_messages"]))
    print("")
    print("BALLOTS in the readable window: %d from %d distinct keys" % (len(ballots), len(everyone)))
    print("  derived-request_id keys (fleet): %d" % len(fleet))
    print("  control voters:                  %d" % len(control))
    print("  fleet keys that submitted words: %d" % len(fleet & writers))
    print("  fleet ballots by entry:   %s" % ent_fleet.most_common(6))
    print("  control ballots by entry: %s" % ent_ctrl.most_common(6))
    print("")
    print("RECEIPTS processed so far: %d of %d ballots (%.1f%%) - the referee is behind"
          % (len(receipts), len(ballots), 100.0 * len(receipts) / len(ballots)))
    print("  accepted %d: fleet %d / other %d / %d whose ballot is ALREADY EVICTED"
          % (acc_fleet + acc_honest + acc_evicted, acc_fleet, acc_honest, acc_evicted))
    print("  rejected %d" % rejected)
    print("  keys emitting BOTH the derived shape and a second shape: %d  (%s)"
          % (len(cross_keys), ", ".join(sorted(linked_shapes)[:3]) or "none"))
    print("  accepted by entry: %s" % acc_entry.most_common(6))
    for k, v in reasons.most_common(4):
        print("    rejected: %-60s %d" % (k, v))
    print("")
    print("REFEREE'S OWN SIGNED PARTICIPANT SERIES (d-sonnet-2-rules):")
    for ts_, v, w in series:
        print("  %s  voters %-7s writers %s" % (ts_, v, w))
    print("")
    print("DILUTION of the voter pool, V = %d FLOP, share = floor(V / N):" % VOTER_POOL)
    for n, label in ((len(control), "control voters only"),
                     (acc_fleet + acc_honest, "accepted in this window"),
                     (series[-1][1] if series else 0, "all registered voters")):
        if n:
            print("  N = %-6d (%-24s) -> %d FLOP each" % (n, label, VOTER_POOL // n))

    res = dict(generated=datetime.datetime.utcnow().isoformat() + "Z",
               payout_rule=rule, eviction=ev,
               ballots=len(ballots), distinct_keys=len(everyone),
               fleet_keys=len(fleet), control_keys=len(control),
               fleet_keys_that_wrote=len(fleet & writers),
               fleet_by_entry=dict(ent_fleet), control_by_entry=dict(ent_ctrl),
               receipts=len(receipts), accepted_fleet=acc_fleet,
               accepted_other=acc_honest, accepted_ballot_evicted=acc_evicted,
               rejected=rejected, cross_template_keys=len(cross_keys),
               linked_shapes=sorted(linked_shapes),
               accepted_by_entry=dict(acc_entry),
               reject_reasons=dict(reasons),
               referee_participant_series=series)
    if out_path:
        io.open(out_path, "w", encoding="utf-8").write(
            json.dumps(res, ensure_ascii=False, indent=1))
        print("\nwrote %s" % out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
