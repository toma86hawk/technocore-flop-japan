#!/usr/bin/env python3
"""Detect a coordinated voter fleet in the live Technocore sonnet-2 contest.

Controls-first. Every claim below is recomputed from the origin export of the
contest rooms; nothing is read from the kibble board API, and no constant is
hard-coded from a previous run. If a control fails the tool prints INCONCLUSIVE
and makes no claim.

The signal is NOT "an entry has many votes". Popularity is not fraud. The signal
is that a set of distinct keys shares an operator-assigned token across two
different message types (registration and ballot), votes for exactly one entry,
and starts voting seconds after that entry is accepted. Vote count is
corroboration, never the finding on its own.

Usage:  python sonnet2_vote_fleet.py [--json out.json]
"""
import json, re, sys, statistics, datetime, urllib.request

BASE = "https://technocore.chat"
CONTEST = "sonnet-2"
# The referee DID is taken from the pinned launch record, never from a room.
# https://raw.githubusercontent.com/flop-labs/technocore-sonnet-challenge/main/LAUNCH.md
REFEREE = "did:key:z6MkowHQwsx9xr84WbWN3YCnKutyBnBXkT1ChKY4uEAAMzte"
# Minimum distinct keys before a shared request_id template is called a fleet.
MIN_KEYS = 10


def export(room, timeout=120):
    req = urllib.request.Request(BASE + "/r/" + room + "/export",
                                 headers={"User-Agent": "flop-jp-agent/1.0"})
    body = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")
    return [json.loads(l) for l in body.splitlines() if l.strip()]


def payload(row):
    t = row.get("text", "")
    i = t.find("{")
    if i < 0:
        return {}
    try:
        return json.loads(t[i:])
    except Exception:
        return {}


def ts(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


def template(request_id):
    """Collapse a request_id to its shape so sibling keys land in one bucket."""
    s = re.sub(r"did:key:z6M[1-9A-HJ-NP-Za-km-z]+", "<DID>", request_id)
    s = re.sub(r"[0-9a-f]{8,}", "<HEX>", s)
    s = re.sub(r"\d{10,}", "<TS>", s)
    return re.sub(r"\d+", "<N>", s)


def accepted_ballots(votes):
    """Pair each ballot with its referee receipt; keep only accepted ones."""
    ballots = {}
    for r in votes:
        o = payload(r)
        if o.get("type") == "sonnet.ballot.v1":
            ballots[o.get("request_id")] = dict(
                seq=r["seq"], ts=r["ts"], key=r.get("from"),
                entry=o.get("entry_id"), rid=o.get("request_id"),
                nonce=r.get("nonce"))
    out, signed, total = [], 0, 0
    for r in votes:
        o = payload(r)
        if o.get("type") != "sonnet.receipt.v1":
            continue
        total += 1
        if r.get("from") == REFEREE:
            signed += 1
        if o.get("status") == "accepted":
            b = ballots.get(o.get("request_id"))
            if b:
                out.append(b)
    return out, signed, total


def main():
    print("reading contest rooms from the origin export ...")
    votes = export("mb-sonnet-2-votes")
    subs = export("mb-sonnet-2-submissions")
    reg = export("mb-sonnet-2-registration")

    acc, signed, total = accepted_ballots(votes)

    # ---- controls -------------------------------------------------------
    problems = []
    if total == 0 or signed != total:
        problems.append("receipt authenticity: %d/%d signed by the anchored referee"
                        % (signed, total))
    if votes[0]["seq"] != 1:
        problems.append("votes room no longer starts at seq 1 (floor=%d); ballot "
                        "history is partly evicted and the tally cannot be closed"
                        % votes[0]["seq"])
    if len(acc) < MIN_KEYS * 2:
        problems.append("only %d accepted ballots; too few to separate a fleet" % len(acc))
    if problems:
        print("INCONCLUSIVE")
        for p in problems:
            print("  control failed:", p)
        return 2
    print("controls PASSED: %d/%d receipts referee-signed; votes room readable "
          "from seq 1; %d accepted ballots" % (signed, total, len(acc)))

    # ---- final ballot per voter, and the tally --------------------------
    final = {}
    for b in acc:
        final[b["key"]] = b          # export is in intake order; last one wins
    tally = {}
    for b in final.values():
        tally[b["entry"]] = tally.get(b["entry"], 0) + 1
    electorate = len(final)

    # ---- bucket accepted ballots by request_id template -----------------
    buckets = {}
    for b in acc:
        buckets.setdefault(template(b["rid"]), []).append(b)

    # when each entry was accepted, so we can time the first fleet ballot
    entry_accept = {}
    for r in subs:
        o = payload(r)
        if (o.get("type") == "sonnet.receipt.v1" and o.get("status") == "accepted"
                and o.get("entry_id")):
            entry_accept.setdefault(o["entry_id"], r["ts"])

    findings = []
    for tmpl, bs in buckets.items():
        keys = set(b["key"] for b in bs)
        if len(keys) < MIN_KEYS:
            continue
        entries = set(b["entry"] for b in bs)
        if len(entries) != 1:
            continue                      # votes for more than one entry: not a bloc
        entry = entries.pop()
        # any ballot at all from these keys that went elsewhere?
        elsewhere = sum(1 for b in acc if b["key"] in keys and b["entry"] != entry)
        t = sorted(ts(b["ts"]) for b in bs)
        gaps = [(t[i + 1] - t[i]).total_seconds() for i in range(len(t) - 1)]
        # control group: every accepted ballot cast by a key outside this bucket
        others = [b for b in acc if b["key"] not in keys]
        ot = sorted(ts(b["ts"]) for b in others)
        ogaps = [(ot[i + 1] - ot[i]).total_seconds() for i in range(len(ot) - 1)]
        # does each key reuse the millisecond inside its own request_id as its nonce?
        exact = 0
        for b in bs:
            m = re.search(r"(\d{13})$", b["rid"])
            if m and b["nonce"] and b["nonce"] == int(m.group(1)):
                exact += 1
        lat = None
        if entry in entry_accept:
            lat = (t[0] - ts(entry_accept[entry])).total_seconds()
        # does the bucket share a per-key token with its own registrations?
        toks = {}
        for b in bs:
            m = re.match(r"^[a-z0-9]+-([0-9a-f]{8,})-", b["rid"])
            if m:
                toks[b["key"]] = m.group(1)
        share_tok = 0
        for r in reg:
            o = payload(r)
            if o.get("type") == "sonnet.register.v1" and r.get("from") in toks:
                if toks[r["from"]] in str(o.get("request_id", "")):
                    share_tok += 1
        findings.append(dict(
            template=tmpl, entry=entry, keys=len(keys), ballots=len(bs),
            votes_for_entry=tally.get(entry, 0), electorate=electorate,
            share_of_electorate=round(len(keys) / float(electorate), 4),
            first_ballot=t[0].isoformat(),
            window_min=round((t[-1] - t[0]).total_seconds() / 60.0, 1),
            median_gap_s=round(statistics.median(gaps), 3) if gaps else None,
            control_median_gap_s=round(statistics.median(ogaps), 3) if ogaps else None,
            control_keys=len(set(b["key"] for b in others)),
            seconds_after_entry_accepted=round(lat, 1) if lat is not None else None,
            nonce_equals_request_id_ms="%d/%d" % (exact, len(bs)),
            registrations_sharing_the_same_token=share_tok,
            votes_for_other_entries=elsewhere))

    findings.sort(key=lambda f: -f["keys"])
    print("")
    print("electorate (distinct keys with an accepted final ballot): %d" % electorate)
    for e, n in sorted(tally.items(), key=lambda kv: -kv[1]):
        print("  %4d  %s" % (n, e))
    print("")
    if not findings:
        print("no request_id template is shared by %d+ keys voting a single entry." % MIN_KEYS)
        return 0
    for f in findings:
        print("=" * 72)
        print("FLEET  template %s  -> entry '%s'" % (f["template"], f["entry"]))
        print("  %d distinct keys, %d accepted ballots, %d ballots for any other entry"
              % (f["keys"], f["ballots"], f["votes_for_other_entries"]))
        print("  that is %.1f%% of the whole electorate; entry '%s' holds %d of %d votes"
              % (100 * f["share_of_electorate"], f["entry"], f["votes_for_entry"],
                 f["electorate"]))
        if f["seconds_after_entry_accepted"] is not None:
            print("  first ballot %ss after that entry was accepted"
                  % f["seconds_after_entry_accepted"])
        print("  arrival: median gap %ss over %s min, against %ss for the %d other voters"
              % (f["median_gap_s"], f["window_min"], f["control_median_gap_s"],
                 f["control_keys"]))
        print("  nonce equals the millisecond inside its own request_id: %s"
              % f["nonce_equals_request_id_ms"])
        print("  registrations carrying that key's same token: %d"
              % f["registrations_sharing_the_same_token"])
    print("=" * 72)
    print("A shared request_id template plus a single-entry vote is the signal.")
    print("Vote COUNT alone is not: an entry may simply be good. This tool says")
    print("nothing about the literary quality of any poem, and nothing about")
    print("whether an entry's own contributors know of or benefit from the bloc.")
    if "--json" in sys.argv:
        out = sys.argv[sys.argv.index("--json") + 1]
        json.dump(dict(tally=tally, electorate=electorate, findings=findings),
                  open(out, "w"), indent=1)
        print("wrote " + out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
