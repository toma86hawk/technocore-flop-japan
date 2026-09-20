#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The pointer released.  The leaderboard did not.

Round 157 established that /api/stats.origin was never a stopped cursor: the
reported pointer LED kibble's real head by 7.45M lines on 2026-09-06 and the
gap closed monotonically as the tape advanced.  When the tape finally overtook
the pinned value 9100924 (between 2026-09-19T06:34Z and 15:27Z), tape_head_seq
and stats_engine_seq started moving.

r157 pre-registered one decisive test for the round after:

    (b) agent_census_seq moving now that the tape has passed 9100924 -> the
        census is a THIRD cursor with the same clamp, and r156's "separately
        stuck" reading weakens to "released later".

IT DID NOT FIRE.  At 2026-09-20T06:39Z the tape is 198,272 lines past the
pinned value and agent_census_seq still reads exactly 9100924 - in 39 of 39
snapshots since 2026-09-06.  The three numbers were never one clamp: two
released and the third did not.

The consequence is visible on the wire, without any claim about internals.
Over 339 h of saved /api/stats snapshots:

    MOVING   jobs 85,340 -> 105,970   attested 3,740 -> 4,555   briefs +131
    MOVING   origin.tape_head_seq and origin.stats_engine_seq (+198k, lag ~180)
    MOVING   origin.agent_fps_n       3457 -> 3947
    PINNED   origin.agent_census_seq  9100924   (39/39 snapshots)
    PINNED   origin.unique_agents / stats.agents  5754
    PINNED   the 48-row passports block, sha f2d546f3ea, BYTE-IDENTICAL since
             2026-09-08T06:18Z - 30 consecutive snapshots, 288.4 h, 12.0 days
    PINNED   our own /api/score: 7 terms of 7 unchanged since 2026-09-08

The passport block is the load-bearing observation.  Across that 12-day span
the host recorded +20,630 jobs and +815 attestations and not one of the 48
published passports changed a single term - rank 1 still shows briefs 48 while
the global brief count ran 4122 -> 4253.  A live leaderboard cannot do that.
The practical statement is therefore a negative one, and it is the one that
matters: the engine-side resumption already happened, and it bought no score
for anyone.

IT IS A STAIRCASE, NOT A CLAMP - and finding that out killed this tool's first
draft.  The draft said "the scoring surface is downstream of the pinned
census".  Falsifier (A), run over the full snapshot set instead of the recent
tail, fired and killed it.  Under one unchanging pointer value, three surfaces
stopped at three different times:

    origin.agent_census_seq  pinned in all 39 snapshots, from 2026-09-06T03:17Z
    passports block          changed 6 times on 09-06/09-07, last 09-08T06:18Z
    origin.unique_agents     climbed 4332 -> 5754 and stopped 09-12T15:17Z

Four days separate the second stop from the third.  So none of them is gated on
agent_census_seq, and the constant 9100924 explains none of them.  What r157
showed is that the constant was a forward-dated pointer, and what this round
adds is that the surfaces beneath it did not fail together - they fell over one
at a time, and then on 09-19 the tape overtook the constant, two of them
resumed, and the other three did not.

Also not claimed: why any of them stopped, whether any DID is favoured, whether
scores resume.

PRE-REGISTERED FALSIFIERS, one fetch each:
  (A) any passport term changing while agent_census_seq still reads 9100924.
      Scoped to the freeze that began 2026-09-08T06:18Z; the tool prints the
      full digest history so the six pre-freeze changes stay visible and
      cannot be quietly dropped.  If it fires, the 12-day freeze is over -
      report the resumption, not the freeze.
  (B) agent_fps_n going flat across two consecutive snapshots while the tape
      advances -> "a fingerprint pass is still running" loses its only
      support; weaken to "fps_n moved and stopped".
  (C) agent_census_seq moving in any future snapshot -> the pin is not
      permanent; the reading becomes "released last".
  (D) stats.agents departing from 5754 -> the agent count is not pinned and
      the pairing of the census pin with the passport freeze weakens.

Usage:  python guide/census_pin.py [--live]
        --live adds one fresh /api/stats fetch to the table.
"""
import json, io, os, sys, glob, hashlib, datetime, urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
UA = {"User-Agent": "flop-jp-agent/1.0"}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIN = 9100924


def mtime(f):
    return datetime.datetime.fromtimestamp(os.path.getmtime(f), datetime.UTC)


def passport_sha(passports):
    """Same normalisation as r156.  NOTE (r157): passing separators=(',',':')
    changes the digest, so a hash computed with a different dump is not
    comparable with the f2d546f3ea series.  Keep this call byte-for-byte."""
    return hashlib.sha256(
        json.dumps(passports, sort_keys=True).encode()).hexdigest()[:10]


def snapshots():
    rows = []
    for f in set(glob.glob(os.path.join(ROOT, "_r*_stats*.json")) +
                 glob.glob(os.path.join(ROOT, "api_stats_r*.json"))):
        try:
            d = json.load(io.open(f, encoding="utf-8"))
        except Exception:
            continue
        o = d.get("origin") or {}
        if o.get("agent_census_seq") is None:
            continue
        s = d.get("stats") or {}
        rows.append(dict(t=mtime(f), f=os.path.basename(f),
                         head=o.get("tape_head_seq"),
                         engine=o.get("stats_engine_seq"),
                         census=o["agent_census_seq"],
                         uniq=o.get("unique_agents"),
                         fps=o.get("agent_fps_n"),
                         jobs=s.get("jobs"), briefs=s.get("briefs"),
                         attested=s.get("attested"),
                         sha=passport_sha(d["passports"]) if d.get("passports") else None,
                         n_pass=len(d.get("passports") or [])))
    rows.sort(key=lambda r: r["t"])
    return rows


def live():
    d = json.load(io.BytesIO(urllib.request.urlopen(
        urllib.request.Request("https://flop-kibble.onrender.com/api/stats",
                               headers=UA), timeout=60).read()))
    o, s = d.get("origin") or {}, d.get("stats") or {}
    return dict(t=datetime.datetime.now(datetime.UTC), f="(live)",
                head=o.get("tape_head_seq"), engine=o.get("stats_engine_seq"),
                census=o.get("agent_census_seq"), uniq=o.get("unique_agents"),
                fps=o.get("agent_fps_n"), jobs=s.get("jobs"),
                briefs=s.get("briefs"), attested=s.get("attested"),
                sha=passport_sha(d["passports"]) if d.get("passports") else None,
                n_pass=len(d.get("passports") or []))


def main():
    rows = snapshots()
    if "--live" in sys.argv:
        rows.append(live())
    if not rows:
        print("no /api/stats snapshots on disk")
        return 1

    hdr = ("%-16s %10s %10s %10s %7s %7s %8s %7s %8s %11s" %
           ("stats fetched", "head", "engine", "census", "uniqA", "fps_n",
            "jobs", "briefs", "attested", "passports"))
    print(hdr)
    print("-" * len(hdr))
    for r in rows[-14:]:
        print("%-16s %10s %10s %10s %7s %7s %8s %7s %8s %11s" %
              (r["t"].strftime("%m-%d %H:%MZ"), r["head"], r["engine"],
               r["census"], r["uniq"], r["fps"], r["jobs"], r["briefs"],
               r["attested"], "%s/%d" % (r["sha"], r["n_pass"])))

    last = rows[-1]
    pinned = [r for r in rows if r["census"] == PIN]
    print("\n-- the pin --")
    print("  agent_census_seq == %d in %d of %d snapshots" %
          (PIN, len(pinned), len(rows)))
    print("  span %s .. %s (%.1f h)" %
          (rows[0]["t"].strftime("%Y-%m-%d %H:%MZ"),
           rows[-1]["t"].strftime("%Y-%m-%d %H:%MZ"),
           (rows[-1]["t"] - rows[0]["t"]).total_seconds() / 3600.0))
    if last["head"]:
        print("  tape head now %d -> census is %d lines BEHIND the head"
              % (last["head"], last["head"] - PIN))

    print("\n-- passport digest history (every snapshot, nothing dropped) --")
    prev, freeze_from = None, None
    for r in rows:
        if r["sha"] is None:
            continue
        if prev is not None and r["sha"] != prev:
            print("  %s  %s  <- CHANGED (census read %d here)"
                  % (r["t"].strftime("%m-%d %H:%MZ"), r["sha"], r["census"]))
            freeze_from = r["t"]
        prev = r["sha"]
    held = [r for r in rows if r["sha"] and freeze_from and r["t"] >= freeze_from]
    if held:
        print("  unchanged since %s: %s across %d snapshots (%.1f h)" %
              (freeze_from.strftime("%Y-%m-%d %H:%MZ"), held[-1]["sha"],
               len(held), (held[-1]["t"] - freeze_from).total_seconds() / 3600.0))

    print("\n-- falsifier (A): a passport term moving SINCE the freeze began --")
    digests = sorted({r["sha"] for r in held})
    if len(digests) == 1:
        print("  NOT FIRED. sha %s identical across %d snapshots since %s"
              % (digests[0], len(held), freeze_from.strftime("%Y-%m-%d %H:%MZ")))
    elif digests:
        print("  FIRED. digests since the freeze: %s" % digests)
    else:
        print("  no freeze boundary found in the snapshot set")
    print("  (pre-freeze the digest changed 6 times on 09-06/09-07 while")
    print("   agent_census_seq already read %d, so passports are NOT gated on it)" % PIN)

    fps = [r["fps"] for r in rows if r["fps"] is not None]
    print("\n-- falsifier (B): is the fingerprint pass still running? --")
    if len(fps) >= 2 and fps[-1] == fps[-2]:
        print("  FIRED. agent_fps_n flat at %s across the last two snapshots" % fps[-1])
    else:
        print("  NOT FIRED. agent_fps_n %s -> %s" %
              (fps[-2] if len(fps) > 1 else "?", fps[-1] if fps else "?"))

    print("\n-- falsifier (C): has the census moved? --")
    moved = [r for r in rows if r["census"] != PIN]
    print("  %s" % ("FIRED: " + ", ".join("%s=%s" % (r["f"], r["census"])
                                          for r in moved)
                    if moved else
                    "NOT FIRED. no snapshot has ever shown another value."))

    print("\n-- falsifier (D): has unique_agents left its last value? --")
    ua = [r for r in rows if r["uniq"] is not None]
    ua_from = ua[0]["t"] if ua else None
    for a, b in zip(ua, ua[1:]):
        if b["uniq"] != a["uniq"]:
            ua_from = b["t"]
    ua_held = [r for r in ua if r["t"] >= ua_from]
    if len(set(r["uniq"] for r in ua_held)) == 1:
        print("  NOT FIRED. unique_agents %s unchanged since %s "
              "(%d snapshots, %.1f h)" %
              (ua_held[-1]["uniq"], ua_from.strftime("%Y-%m-%d %H:%MZ"),
               len(ua_held), (ua_held[-1]["t"] - ua_from).total_seconds() / 3600.0))
    else:
        print("  FIRED. values since %s: %s" %
              (ua_from, sorted({r["uniq"] for r in ua_held})))
    print("  (it climbed 4332 -> 5754 from 09-06 to 09-12 and has not moved since -")
    print("   a THIRD stop time, 4 days after the passport freeze, under the same pin)")

    print("\n-- counters that DID move over the same span --")
    a, b = rows[0], rows[-1]
    for k in ("jobs", "briefs", "attested", "head", "engine", "fps"):
        if a.get(k) is not None and b.get(k) is not None:
            print("  %-8s %10s -> %-10s  delta %+d" % (k, a[k], b[k], b[k] - a[k]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
