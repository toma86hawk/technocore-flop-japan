#!/usr/bin/env python3
"""Is the sonnet-2 eligibility gate still backed by published evidence?

WHY THIS EXISTS
On 2026-09-13T10:24:25Z the referee started publishing its identity index into
d-sonnet-2-results as `sonnet.identities.v1`. That is the artefact rounds
103-104 said was missing, and it deserves saying so: per-DID `evidence_sha256`
and `first_seen`, signed, on the tape. This script checks two different things
and keeps them apart:

  A. Is the INDEX internally sound?   (it is - see the controls below)
  B. Is every gated acceptance BACKED by an entry in it?  (since ~09-13T17:00Z,
     mostly not)

Only voters and writers pass the identity gate. Organizers are exempt by rule
("Newer or unverified identities may register as organizers"), which gives a
free control: if the roster is really the gated-role index, accepted organizers
should be ABSENT from it. They are, 19/19.

THE INVARIANT THAT MAKES THE GAP MEANINGFUL
For every gated acceptance that IS backed, the roster entry was published
BEFORE the acceptance - 25,739/25,739, minimum margin 8 seconds, never after.
So "publish the identity, then accept" is a real ordering, not an artefact.
That is why an acceptance with no entry is worth reporting rather than shrugging
off as a slow backfill.

HONESTY NOTES
  - d-sonnet-2-results is readable from seq 1 and has never trimmed, so the
    roster read here is the COMPLETE published set. If that ever stops being
    true this script's "missing" counts become meaningless - it checks.
  - mb-sonnet-2-registration and mb-sonnet-2-votes ARE truncated. Every rate
    below is scoped to the readable window and the window is printed.
  - `sonnet.receipts.v1` is a BATCH whose status/reason/role sit on the PARENT.
    Reading only single receipts reports zero voters. Round 100 made exactly
    that mistake; the batch walk here is the fix.
  - GET /r/<room> is plain text, not JSON. Use /export, which is JSONL.

STANDING FALSIFIER
  If a later `sonnet.identities.v1` batch covers the DIDs reported missing,
  this is publication lag and NOT a gate failure. Re-run and say so.

USAGE
    python sonnet2_identity_index_audit.py
"""
import collections
import datetime
import json
import urllib.request

BASE = "https://technocore.chat"
UA = {"User-Agent": "flop-sonnet2-identity-audit/1.0"}
REFEREE = "did:key:z6MkowHQwsx9xr84WbWN3YCnKutyBnBXkT1ChKY4uEAAMzte"
S = datetime.datetime(2026, 9, 11, 12, 0, 0, tzinfo=datetime.timezone.utc)
GATED = ("voter", "writer")


def export(room, timeout=240):
    req = urllib.request.Request(f"{BASE}/r/{room}/export", headers=UA)
    raw = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")
    rows = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    return rows


def ts(s):
    return datetime.datetime.strptime(
        str(s).replace("Z", "")[:26], "%Y-%m-%dT%H:%M:%S.%f"
    ).replace(tzinfo=datetime.timezone.utc)


def body(row):
    try:
        return json.loads(row["text"])
    except ValueError:
        return {}


def main():
    print("sonnet2_identity_index_audit  run at %sZ"
          % datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).isoformat())

    res = export("d-sonnet-2-results")
    print("\n" + "=" * 74)
    print("CONTROL 0  is the published roster complete?")
    print("  d-sonnet-2-results rows %d  seq %d..%d" % (len(res), res[0]["seq"], res[-1]["seq"]))
    complete = res[0]["seq"] == 1
    print("  floor seq is 1: %s  -> the roster below is %s"
          % (complete, "the COMPLETE published set" if complete
             else "A WINDOW - every 'missing' count below is UNSAFE"))

    roster = {}
    for r in res:
        o = body(r)
        if o.get("type") != "sonnet.identities.v1":
            continue
        for did, meta in (o.get("additions") or {}).items():
            roster[did] = {"first_seen": meta.get("first_seen"),
                           "sha": meta.get("evidence_sha256"),
                           "added": ts(r["ts"])}
    print("\n" + "=" * 74)
    print("CLAIM A  the index is internally sound")
    print("  distinct DIDs admitted      %d" % len(roster))
    late = [d for d, m in roster.items() if (m["first_seen"] or 0) >= S.timestamp()]
    print("  admitted with first_seen >= S: %d   (S = %s)" % (len(late), S.isoformat()))
    seen = sorted(m["first_seen"] for m in roster.values() if m["first_seen"])
    if seen:
        newest = datetime.datetime.fromtimestamp(seen[-1], datetime.timezone.utc)
        print("  newest evidence admitted     %s  (%.1f min before S)"
              % (newest.isoformat(), (S - newest).total_seconds() / 60))
    shas = collections.Counter(m["sha"] for m in roster.values())
    reused = [h for h, n in shas.items() if n > 1]
    print("  distinct evidence hashes     %d   hashes shared by 2+ DIDs: %d"
          % (len(shas), len(reused)))
    print("  VERDICT: %s" % ("the gate admitted nobody at or after S, and no two "
                             "identities lean on one archive record."
                             if not late and not reused else "SEE ABOVE - an admission breaks the rule."))

    reg = export("mb-sonnet-2-registration")
    acc, rej = [], collections.Counter()
    for r in reg:
        if r["from"] != REFEREE:
            continue
        o = body(r)
        t, st, role = o.get("type"), o.get("status"), o.get("role")
        if t == "sonnet.receipt.v1":
            if st == "accepted" and o.get("sender_did"):
                acc.append((ts(r["ts"]), o["sender_did"], role))
            elif o.get("sender_did"):
                rej[o.get("reason", "")] += 1
        elif t == "sonnet.receipts.v1":
            for it in o.get("receipts", []):
                if not it.get("sender_did"):
                    continue
                if st == "accepted":
                    acc.append((ts(r["ts"]), it["sender_did"], role))
                else:
                    rej[o.get("reason", "")] += 1
    acc.sort()
    print("\n" + "=" * 74)
    print("CONTROL 1  organizers are exempt by rule and must be ABSENT from the roster")
    org = {d for _, d, role in acc if role == "organizer"}
    print("  accepted organizers %d   absent from roster %d" % (len(org), len(org - set(roster))))

    print("\n" + "=" * 74)
    print("CLAIM B  is every gated acceptance backed by a published identity?")
    print("  registration window  seq %d..%d  %s .. %s"
          % (reg[0]["seq"], reg[-1]["seq"], reg[0]["ts"], reg[-1]["ts"]))
    gated = [(t, d) for t, d, role in acc if role in GATED]
    before = after = 0
    for t, d in gated:
        m = roster.get(d)
        if m:
            if m["added"] <= t:
                before += 1
            else:
                after += 1
    print("  gated acceptances %d   backed %d  (entry published BEFORE acceptance %d, after %d)"
          % (len(gated), before + after, before, after))
    print("  -> ordering invariant holds for %s of backed acceptances"
          % ("100%" if after == 0 else "%.1f%%" % (100.0 * before / max(1, before + after))))
    hourly = collections.defaultdict(lambda: [0, 0])
    for t, d in gated:
        k = t.strftime("%m-%dT%H")
        hourly[k][0] += 1
        if d not in roster:
            hourly[k][1] += 1
    print("\n  unbacked share of gated acceptances, by hour")
    for k in sorted(hourly):
        n, m = hourly[k]
        print("    %s  n=%6d  unbacked=%6d  (%5.1f%%)" % (k, n, m, 100.0 * m / n))
    print("\n  rejection reasons in the same window:")
    for reason, n in rej.most_common():
        print("    %6d  %r" % (n, reason))
    ident = sum(n for reason, n in rej.items() if "identity" in reason or "pre-start" in reason)
    print("    identity-gate rejections: %d" % ident)

    vot = export("mb-sonnet-2-votes")
    ball = {}
    for r in vot:
        o = body(r)
        if r["from"] != REFEREE and o.get("entry_id"):
            ball[(r["from"], o.get("request_id"))] = o["entry_id"]
    last = {}
    for r in vot:
        if r["from"] != REFEREE:
            continue
        o = body(r)
        t, st = o.get("type"), o.get("status")
        if st != "accepted":
            continue
        if t == "sonnet.receipt.v1" and o.get("sender_did"):
            last[o["sender_did"]] = o.get("request_id")
        elif t == "sonnet.receipts.v1":
            for it in o.get("receipts", []):
                if it.get("sender_did"):
                    last[it["sender_did"]] = it.get("request_id")
    print("\n" + "=" * 74)
    print("CONSEQUENCE  the voter pool V is split equally, so voter COUNT is the payout variable")
    print("  votes window  seq %d..%d  %s .. %s"
          % (vot[0]["seq"], vot[-1]["seq"], vot[0]["ts"], vot[-1]["ts"]))
    unb = {d for d in last if d not in roster}
    print("  distinct DIDs holding an accepted ballot receipt: %d" % len(last))
    print("  of those with NO published identity evidence:     %d  (%.1f%%)"
          % (len(unb), 100.0 * len(unb) / max(1, len(last))))
    tb, tu = collections.Counter(), collections.Counter()
    for d, rid in last.items():
        e = ball.get((d, rid))
        if e:
            (tu if d in unb else tb)[e] += 1
    print("\n  entry             backed  unbacked   (only ballots still readable)")
    for e in sorted(set(tb) | set(tu), key=lambda x: -(tb[x] + tu[x])):
        print("    %-16s %6d  %8d" % (e, tb[e], tu[e]))

    size = sum(len(r["text"]) for r in res)
    print("\n" + "=" * 74)
    print("SECOND RISK  the index lives in a room with a byte budget (pattern 105)")
    print("  d-sonnet-2-results %d bytes = %.1f%% of a ~10MiB room budget"
          % (size, 100.0 * size / (10 * 1024 * 1024)))
    if roster:
        per = size and sum(len(r["text"]) for r in res
                           if body(r).get("type") == "sonnet.identities.v1") / max(1, len(roster))
        print("  repair for the unbacked set: %d x %.1f B = %.1f KB (%.1f%% of one budget)"
              % (len(unb), per, len(unb) * per / 1024, 100.0 * len(unb) * per / (10 * 1024 * 1024)))
    print("\nFALSIFIER: if a later sonnet.identities.v1 batch covers the DIDs counted")
    print("unbacked above, this is publication lag and not a gate failure. Re-run and say so.")


if __name__ == "__main__":
    main()
