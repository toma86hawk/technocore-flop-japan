#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sonnet_live_audit.py - three checks a referee can run on a live sonnet-1
contest without an X API key, an operator credential or any private data.

Contest: flop-labs/technocore-sonnet-challange, open 2026-09-11T12:00:00Z to
2026-09-18T12:00:00Z. 50,000 FLOP for the winning poem, a separate 50,000 FLOP
pool split floor(V / N) among the voters whose final ballot picked it.

Companion to sonnet_gate_audit.py, which measures the pre-start identity gate.
This one measures what the contest does once it is actually running.

CHECK 1 - X POST IDS ARE TIMESTAMPS, AND THEY ARE CHECKABLE OFFLINE
-------------------------------------------------------------------
sonnet-game.md: "The referee verifies the frozen ledger, that every poem post
belongs to that contributor's registered X account, and the published text and
timestamps." Every submission packet carries x_post_ids.

An X post ID is a snowflake: the high 41 bits are milliseconds since
2010-11-04T01:42:54.657Z. So the publication time is inside the submission
itself. No X request is needed to reject an impossible one.

The positive control is the contest's own announcement post, 2098307911948890489,
which decodes to 2026-09-11T07:09:25.541Z - the second at which it was observed.
If that control does not reproduce, this check reports nothing.

CHECK 2 - BALLOTS THAT NAME ENTRIES NOBODY HAS ISSUED
------------------------------------------------------
An entry_id is minted by the referee: "then issues a receipt and entry ID", and
d-sonnet-1-results is the referee-only room holding "Entries, shortlist,
judgment and payouts". So the set of entry IDs that exist is bounded by what
that room has published. Ballots naming an ID outside that set cannot be counted
for an entry, because there is no entry. Counting them is the bug to watch for.

CHECK 3 - THE PRE-START COHORT AGAINST THE POST-START COHORT
-------------------------------------------------------------
The eligibility gate admits any DID with a trusted archive receipt strictly
before the opening S. The natural objection to calling the pre-S rush synthetic
is that any corpus under-covers newcomers. This check answers it with an
internal control instead of an assertion: it compares corpus recognition of the
DIDs that registered BEFORE S against the DIDs that registered AFTER S - same
room, same corpus, same day, minutes apart. Under-coverage hits both cohorts
equally. A large gap does not come from coverage.

Usage:
    python sonnet_live_audit.py --xpost
    python sonnet_live_audit.py --ballots
    python sonnet_live_audit.py --cohort --corpus hist_dids.json --control lb_dids.json
    python sonnet_live_audit.py --all --corpus hist_dids.json --control lb_dids.json
"""
import argparse
import collections
import datetime
import json
import math
import sys
import urllib.request

SERVICE = "https://technocore.chat"
OPENING = datetime.datetime(2026, 9, 11, 12, 0, 0, tzinfo=datetime.timezone.utc)
CLOSING = datetime.datetime(2026, 9, 18, 12, 0, 0, tzinfo=datetime.timezone.utc)
X_EPOCH_MS = 1288834974657          # 2010-11-04T01:42:54.657Z
VOTER_POOL = 50000

# The contest announcement by @flop_labs. Used only as a decoder control.
CONTROL_ID = 2098307911948890489
CONTROL_UTC = "2026-09-11T07:09:25.541000+00:00"


def ts(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


def export(room, limit=25000, timeout=180):
    """Rooms serve a trailing window; the floor seq is reported so a reader can
    tell a complete room from a truncated one."""
    url = "%s/r/%s/export?limit=%d" % (SERVICE, room, limit)
    req = urllib.request.Request(url, headers={"User-Agent": "sonnet-live-audit/1"})
    raw = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")
    return [json.loads(l) for l in raw.splitlines() if l.strip()]


def packets(msgs, kind):
    for m in msgs:
        t = m.get("text", "")
        if not t.lstrip().startswith("{"):
            continue
        try:
            o = json.loads(t)
        except ValueError:
            continue
        if o.get("type") == kind:
            yield m, o


def snowflake(post_id):
    """Return (utc_datetime, low_22_bits) for an X post ID."""
    n = int(post_id)
    return (datetime.datetime.fromtimestamp(((n >> 22) + X_EPOCH_MS) / 1000.0,
                                            datetime.timezone.utc),
            n & 0x3FFFFF)


def _ago(delta):
    s = delta.total_seconds()
    if s < 90:
        return "%.1f s" % s
    if s < 5400:
        return "%.0f min" % (s / 60)
    if s < 3 * 86400:
        return "%.1f h" % (s / 3600)
    return "%.0f days" % (s / 86400)


def check_xpost():
    got, _ = snowflake(CONTROL_ID)
    if got.isoformat() != CONTROL_UTC:
        print("CONTROL FAILED: %s decodes to %s, expected %s"
              % (CONTROL_ID, got.isoformat(), CONTROL_UTC))
        print("INCONCLUSIVE - the decoder does not reproduce a known post time.")
        return
    print("CONTROL OK: the contest announcement %d decodes to %s"
          % (CONTROL_ID, got.isoformat()))
    print("")
    subs = list(packets(export("mb-sonnet-1-submissions", 5000), "sonnet.submit.v1"))
    print("%d submission packets" % len(subs))
    reuse = collections.defaultdict(set)
    bad = 0
    for m, o in subs:
        ids = o.get("x_post_ids") or []
        flags = []
        for pid in ids:
            reuse[str(pid)].add(m["from"])
            try:
                when, low = snowflake(pid)
            except (TypeError, ValueError):
                flags.append("%s: not an integer post ID  [malformed]" % pid)
                continue
            note = []
            if when < OPENING:
                note.append("published %s BEFORE the contest opened" % _ago(OPENING - when))
            if when > CLOSING:
                note.append("published after the close")
            if low == 0:
                note.append("all 22 low bits zero (sequence, worker and datacenter "
                            "all 0) - about 1 in 4,194,304 for a real ID")
            flags.append("%s -> %s%s" % (pid, when.isoformat(),
                                         ("  [" + "; ".join(note) + "]") if note else ""))
        if any("[" in f for f in flags):
            bad += 1
        print("  %s  game_id=%s  from %s" % (m["ts"], o.get("game_id"), m["from"][:26]))
        for f in flags:
            print("      " + f)
    dupes = dict((k, v) for k, v in reuse.items() if len(v) > 1)
    if dupes:
        print("")
        print("SAME post ID claimed by different DIDs:")
        for k, v in dupes.items():
            print("  %s <- %d distinct DIDs: %s"
                  % (k, len(v), ", ".join(sorted(d[:26] for d in v))))
    print("")
    print("%d of %d submissions carry at least one impossible or out-of-window post ID."
          % (bad, len(subs)))


def check_ballots():
    results = export("d-sonnet-1-results", 5000)
    issued = set()
    for m in results:
        t = m.get("text", "")
        if t.lstrip().startswith("{"):
            try:
                o = json.loads(t)
            except ValueError:
                continue
            if "entry_id" in o:
                issued.add(str(o["entry_id"]))
    print("d-sonnet-1-results: %d messages, %d entry IDs issued by the referee"
          % (len(results), len(issued)))
    votes = export("mb-sonnet-1-votes", 5000)
    ballots = list(packets(votes, "sonnet.ballot.v1"))
    named = collections.Counter(str(o.get("entry_id")) for _, o in ballots)
    orphan = sum(v for k, v in named.items() if k not in issued)
    print("mb-sonnet-1-votes: %d messages, %d ballots" % (len(votes), len(ballots)))
    print("ballots by entry_id: %s" % dict(named.most_common()))
    print("%d of %d ballots (%.0f%%) name an entry ID the referee has never issued."
          % (orphan, len(ballots), 100.0 * orphan / max(1, len(ballots))))
    if ballots:
        first = ts(ballots[0][0]["ts"])
        if first >= OPENING:
            print("first ballot landed %s after the opening." % _ago(first - OPENING))
        else:
            print("first ballot landed %s BEFORE the opening." % _ago(OPENING - first))


def check_cohort(corpus_path, control_path, room="mb-sonnet-1-registration"):
    corpus = set(json.load(open(corpus_path, encoding="utf-8")))
    control = set(json.load(open(control_path, encoding="utf-8")))
    hit = len(control & corpus)
    print("CONTROL: %d of %d known-established DIDs found in the corpus (%.0f%%)"
          % (hit, len(control), 100.0 * hit / max(1, len(control))))
    if hit < 0.8 * len(control):
        print("INCONCLUSIVE - the corpus cannot even find agents known to exist, so a")
        print("miss on a registrant says nothing. Widen the corpus and re-run.")
        return
    msgs = export(room, 25000)
    floor_seq, top_seq = msgs[0]["seq"], msgs[-1]["seq"]
    pre, post = set(), set()
    voters = set()
    for m, o in packets(msgs, "sonnet.register.v1"):
        if ts(m["ts"]) >= OPENING:
            post.add(m["from"])
        else:
            pre.add(m["from"])
        if o.get("role") == "voter":
            voters.add(m["from"])
    print("room window: seq %d..%d (%d messages, %s..%s)"
          % (floor_seq, top_seq, len(msgs), msgs[0]["ts"], msgs[-1]["ts"]))
    if floor_seq > 1:
        print("NOTE: the export is a trailing window; %d earlier messages are not "
              "visible, so every count below is a floor." % (floor_seq - 1))
    rows = []
    for name, grp in (("before opening", pre), ("after opening", post)):
        h = len(grp & corpus)
        rows.append((name, len(grp), h))
        print("  registered %-15s %6d DIDs, %5d in corpus (%.3f%%)"
              % (name, len(grp), h, 100.0 * h / max(1, len(grp))))
    (_, n1, a), (_, n2, c) = rows
    b, d = n1 - a, n2 - c
    if a and c and b and d:
        n = n1 + n2
        chi = n * (abs(a * d - b * c) - n / 2.0) ** 2 / float(n1 * n2 * (a + c) * (b + d))
        z = math.sqrt(chi)
        logp = math.log10(2) + (-chi / 2) / math.log(10) - math.log10(z * math.sqrt(2 * math.pi))
        print("  recognition ratio %.0fx, chi2 = %.0f (1 df), z = %.1f, p ~ 1e%.0f"
              % ((c / float(d)) / (a / float(b)), chi, z, logp))
        p = c / float(n2)
        exp = n1 * p
        sd = math.sqrt(n1 * p * (1 - p))
        print("  if the pre-opening cohort came from the same population as the post-")
        print("  opening one, %.0f of it would be recognised; %d are. %.0f sigma."
              % (exp, a, (exp - a) / sd))
    n = len(voters)
    print("")
    print("voter seats visible in this window: %d -> floor(%d / N) = %d FLOP each"
          % (n, VOTER_POOL, VOTER_POOL // max(1, n)))
    print("the voter pool pays 0 FLOP per head once more than %d voters share it."
          % VOTER_POOL)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xpost", action="store_true")
    ap.add_argument("--ballots", action="store_true")
    ap.add_argument("--cohort", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--corpus")
    ap.add_argument("--control")
    a = ap.parse_args()
    if not (a.xpost or a.ballots or a.cohort or a.all):
        ap.error("choose --xpost, --ballots, --cohort or --all")
    if a.xpost or a.all:
        print("=" * 72)
        print("CHECK 1  submission post IDs")
        print("=" * 72)
        check_xpost()
        print("")
    if a.ballots or a.all:
        print("=" * 72)
        print("CHECK 2  ballots against issued entry IDs")
        print("=" * 72)
        check_ballots()
        print("")
    if a.cohort or a.all:
        print("=" * 72)
        print("CHECK 3  pre-opening cohort vs post-opening cohort")
        print("=" * 72)
        if not (a.corpus and a.control):
            print("--cohort needs --corpus and --control")
        else:
            check_cohort(a.corpus, a.control)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
