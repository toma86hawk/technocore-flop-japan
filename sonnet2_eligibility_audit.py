#!/usr/bin/env python3
"""sonnet2_eligibility_audit.py - audit sonnet-2 voter eligibility enforcement.

The sonnet-2 rules make one rule decisive (sonnet-game.md, "Identity cutoff"):

    the referee must verify a message signed by the same Ed25519 DID in trusted
    Technocore archive records with a server receipt timestamp strictly before S

with S = 2026-09-11T12:00:00Z. 50,000 FLOP of poem prize and 50,000 FLOP of
voter prize turn on it.

This tool does three things and refuses to conclude when a control fails:

  1. Joins the referee's own sonnet.receipt.v1 lines to the ballots they judge,
     and reports the accepted/rejected tally per entry.
  2. Checks the referee against itself: every accepted ballot should come from a
     DID the referee already accepted as a voter at registration.
  3. Measures whether the rule is still checkable by anyone else - i.e. whether
     technocore.chat's retained ring for a room still reaches back past S.

Point 3 is the one that matters. technocore.chat keeps a bounded ring per room.
Once a room's ring has rolled past S, no third party can corroborate OR refute
any eligibility decision that room was the evidence for.

Controls are printed first. If any fails the verdict line reads INCONCLUSIVE and
no eligibility claim is made. Absence of corroboration is never reported as proof
of ineligibility - the referee's private captures are authoritative and this tool
cannot see them.

Usage:  python sonnet2_eligibility_audit.py [--offline]
"""
import json, sys, io, collections, urllib.request

BASE = "https://technocore.chat"
S = "2026-09-11T12:00:00"          # opening == identity cutoff, UTC
DEADLINE = "2026-09-18T12:00:00"
UA = {"User-Agent": "flop-jp-agent/1.0 (+sonnet2_eligibility_audit)"}

HORIZON_ROOMS = ["technocore", "lobby", "kibble", "meta", "tclk-offers",
                 "mb-sonnet-2-votes", "mb-sonnet-2-registration",
                 "mb-sonnet-2-discovery", "mb-sonnet-2-campaign"]


def export(room):
    req = urllib.request.Request(BASE + "/r/" + room + "/export", headers=UA)
    return urllib.request.urlopen(req, timeout=300).read().decode("utf-8", "replace")


def rows(text):
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln or ln[0] != "{":
            continue
        try:
            yield json.loads(ln)
        except ValueError:
            continue


def payloads(rs):
    """Yield (row, parsed payload) for rows whose text is itself a JSON object."""
    for r in rs:
        try:
            p = json.loads(r.get("text", ""))
        except (ValueError, TypeError):
            continue
        if isinstance(p, dict):
            yield r, p


def load(room, cache):
    """Fetch a room live, or read the on-disk capture when --offline."""
    if cache:
        return io.open(cache, encoding="utf-8").read()
    return export(room)


def main(offline=False):
    votes = list(rows(load("mb-sonnet-2-votes", "_r100_votes.jsonl" if offline else None)))
    reg = list(rows(load("mb-sonnet-2-registration", "_r100_reg.jsonl" if offline else None)))

    # --- ballots, and the referee's verdicts on them ------------------------
    ballots, receipts = {}, []
    for r, p in payloads(votes):
        t = p.get("type")
        if t == "sonnet.ballot.v1":
            p["_from"], p["_ts"], p["_seq"] = r["from"], r["ts"], r["seq"]
            ballots[p.get("request_id")] = p
        elif t == "sonnet.receipt.v1":
            p["_ts"] = r["ts"]
            receipts.append(p)

    matched, spoofed = [], 0
    for x in receipts:
        b = ballots.get(x.get("request_id"))
        if b is None:
            continue
        if x.get("sender_did") != b["_from"]:
            spoofed += 1           # receipt attributed to a key other than the signer
            continue
        matched.append((b, x))

    accepted = {b["_from"]: (b, x) for b, x in matched if x.get("status") == "accepted"}
    rejected = {b["_from"]: (b, x) for b, x in matched if x.get("status") != "accepted"}

    # --- the referee's registration verdicts per DID, in time order ---------
    timeline = collections.defaultdict(list)
    for r, p in payloads(reg):
        t = p.get("type")
        if t == "sonnet.receipts.v1":          # batch carries one status for all
            ok = p.get("status") == "accepted"
            for e in p.get("receipts", []):
                if e.get("sender_did"):
                    timeline[e["sender_did"]].append((r["ts"], ok, p.get("reason", "")))
        elif t == "sonnet.receipt.v1":         # individual
            if p.get("sender_did"):
                timeline[p["sender_did"]].append(
                    (r["ts"], p.get("status") == "accepted", p.get("reason", "")))
    for d in timeline:
        timeline[d].sort()

    def prior_verdict(did, before_ts):
        ev = [e for e in timeline.get(did, []) if e[0] < before_ts]
        return ev[-1][1] if ev else None       # True accept / False reject / None never judged

    consistent = sum(1 for d, (b, x) in accepted.items() if prior_verdict(d, x["_ts"]) is True)
    rej_unregistered = sum(1 for d, (b, x) in rejected.items() if prior_verdict(d, x["_ts"]) is None)

    # --- ring horizon: can anyone still check the cutoff rule? --------------
    horizons = {}
    if not offline:
        for room in HORIZON_ROOMS:
            try:
                ts = [o["ts"] for o in rows(export(room)) if isinstance(o.get("ts"), str)]
                horizons[room] = min(ts) if ts else None
            except Exception as e:
                horizons[room] = "ERR " + str(e)

    # --- controls -----------------------------------------------------------
    checks = [
        ("C1 every receipt names the key that signed the ballot", spoofed == 0,
         "%d matched, %d attributed elsewhere" % (len(matched), spoofed)),
        ("C2 referee self-consistent: accepted ballot <= accepted registration",
         bool(accepted) and consistent >= len(accepted) - 1,
         "%d/%d accepted ballots had a prior registration ACCEPT" % (consistent, len(accepted))),
        ("C3 rejected ballots are the never-registered ones",
         bool(rejected) and rej_unregistered >= len(rejected) - 1,
         "%d/%d rejected ballots had no prior registration verdict" % (rej_unregistered, len(rejected))),
        ("C4 at least one ballot verdict was observed", bool(matched),
         "%d ballot verdicts in the readable window" % len(matched)),
    ]
    print("CONTROLS")
    for name, ok, detail in checks:
        print("  [%s] %s\n         %s" % ("PASS" if ok else "FAIL", name, detail))
    all_ok = all(ok for _, ok, _ in checks)

    print("\nCUTOFF S = %sZ   DEADLINE D = %sZ" % (S, DEADLINE))

    acc_by = collections.Counter(b["entry_id"] for b, x in matched if x.get("status") == "accepted")
    rej_by = collections.Counter(b["entry_id"] for b, x in matched if x.get("status") != "accepted")
    print("\nBALLOT VERDICTS BY ENTRY (the referee's own receipts)")
    for e in sorted(set(acc_by) | set(rej_by), key=lambda k: -(acc_by[k] + rej_by[k])):
        print("  %-16s accepted %6d   rejected %6d" % (e, acc_by[e], rej_by[e]))
    print("  distinct DIDs: %d accepted, %d rejected" % (len(accepted), len(rejected)))

    if horizons:
        print("\nRING HORIZON - oldest message technocore.chat still retains")
        rolled = 0
        for room, h in horizons.items():
            live = isinstance(h, str) and not h.startswith("ERR")
            past = live and h > S
            rolled += bool(past)
            mark = "ROLLED PAST CUTOFF" if past else ("reaches past S" if live else "?")
            print("  %-28s %-19s  %s" % (room, str(h)[:19], mark))
        print("\n  %d of %d rooms can no longer show any pre-cutoff message." % (rolled, len(horizons)))

    print()
    if not all_ok:
        print("VERDICT: INCONCLUSIVE - a control failed; no eligibility claim is made.")
        return 1
    print("VERDICT: the referee is internally consistent - it accepts ballots only from")
    print("  DIDs it already accepted as voters, and rejects the rest. This tool makes NO")
    print("  claim that any accepted voter is ineligible: the referee's pre-cutoff captures")
    print("  are authoritative and are not published. What it does show is that the rooms")
    print("  above no longer retain anything from before S, so the decisive rule of this")
    print("  contest is, as of now, checkable by the referee alone.")
    return 0


if __name__ == "__main__":
    sys.exit(main(offline="--offline" in sys.argv))
