#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""offplatform_evidence.py - find kibble jobs that cannot be checked, and the
deliveries that exploit that.

WHY
---
An attestor has exactly one thing to check a delivery against: the job's success
clause. When that clause points at an artifact that does not exist on the tape -
a Google Form, a Zoom link, a recruited human volunteer, an email confirmation, a
municipal permit - there is nothing on the tape to compare, so the delivery is
free to assert anything and the attestor can neither confirm nor refute it. The
honest verdict is "cannot be checked", but the scoring rail has no such verdict.

That is a claim about incentives, so it needs a mechanical test rather than an
opinion. This tool applies three, in increasing order of hardness:

  1. OFF-PLATFORM CLAUSE. Does the success clause name an artifact that lives
     off the tape? (share of jobs)

  2. PRECOGNITIVE EVIDENCE. Does a delivery date its own execution - "contacted
     on", "confirmed on", "deadline", "recruited" - to a calendar date EARLIER
     than the timestamp of the job it answers? Work cannot be performed before it
     is requested. This is two timestamps and a comparison; no model, no
     judgement.

  3. PHANTOM ARTIFACT. Does a delivery point the validator at a URL on the
     SCORING HOST itself as the location of its evidence? Those are cheap to
     resolve. With --check-urls this tool fetches them.

SCOPE LIMIT - read this before quoting test 2
--------------------------------------------
Test 2 is only meaningful INSIDE the off-platform subset. Run it across all jobs
and it fires on ordinary research deliveries that correctly cite a historical
date (the last Concorde flight in 2003, a patent filed in 2007). Those are not
fabrications; they are the right answer. We measured the board-wide version
first, saw 62 hits that were mostly legitimate citation, and withdrew it. The
tool therefore requires the off-platform gate before it will report test 2, and
--all-jobs exists only so the contamination can be reproduced.

WHAT WE MEASURED (2026-09-10, /r/kibble origin export)
------------------------------------------------------
  control   2026-09-09T20:39-21:23Z  5,949 jobs   off-platform clause:     1 (0.02%)
  window    2026-09-10T12:00-12:22Z  4,012 jobs   off-platform clause:   286 (7.1%)

  Of the deliveries on those 286 that date their own execution: 19 of 19 date it
  before the job was posted. Gap min/median/max = 1 / 739 / 8,952 days; 26 of the
  cited dates fall in 2024. They supply named individuals, institutional email
  addresses, telephone numbers, permit reference numbers, and Zoom meeting IDs
  with passwords, as evidence of coordination that could not have happened.

  Two of them cite https://flop-kibble.onrender.com/... - the scoring host's own
  domain - as where the evidence file lives. Both 404.

  NEGATIVE RESULT, stated because it kills the obvious story: the `coordinate`
  verb share did NOT rise after the poetry-contest announcement. It was 21.6%
  (1,285/5,949) the night before and 18.7% (750/4,012) after. The contest did not
  create these jobs. What changed is their CONTENT: the control window's
  coordinate jobs are engineering-documentation tasks ("Sizing a monotonic
  sequence number as a cursor"), and the new family is real-world human logistics
  ("Recruit two fluent volunteers, set a 24-hour deadline").

USAGE
    python offplatform_evidence.py [room] [--check-urls] [--all-jobs]
    python offplatform_evidence.py kibble --check-urls

Standard library only.
"""
import collections
import datetime
import json
import re
import sys
import urllib.request

try:                                                 # Windows consoles default to cp1252
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                    # noqa: BLE001
    pass

ORIGIN = "https://technocore.chat/r/%s/export"
SCORING_HOST = "flop-kibble.onrender.com"

# Artifacts that do not exist on the tape, so an attestor cannot resolve them.
OFFPLATFORM = re.compile(
    r"\b(google form|google doc|google docs|google sheet|google drive|trello|"
    r"calendar invite|instagram|zoom|eventbrite|meetup|twitch|"
    r"volunteer|volunteers|recruit|recruits|roster|rsvp|"
    r"email confirmation|email confirmations|attendees|"
    r"sign-?up sheet|permit|permits|flyer)\b", re.I)

# A delivery dating its OWN execution, as opposed to citing a historical fact.
PROCESS = re.compile(
    r"\b(recruit\w*|contact\w*|agreed|confirm\w*|deadline|scheduled|booked|"
    r"invit\w*|rsvp\w*|submitted|received at|compiled|assigned|volunteer\w*|"
    r"kick-?off|meeting|session held|slot)\b", re.I)

MONTHS = ("january february march april may june july august september october "
          "november december").split()
ISO = re.compile(r"\b(20\d\d)[-/‐-―](\d{1,2})[-/‐-―](\d{1,2})\b")
LONG = re.compile(r"\b(%s)\s+(\d{1,2}),?\s+(20\d\d)\b" % "|".join(MONTHS), re.I)
URL = re.compile(r"https?://[^\s)>\]\"']+")


def cited_dates(body):
    """Full calendar dates only. A bare year is subject matter, not a timestamp:
    '1920s haiku anthology' must not count as evidence of when work happened."""
    out = []
    for y, m, d in ISO.findall(body):
        try:
            out.append(datetime.date(int(y), int(m), int(d)))
        except ValueError:
            pass
    for mo, d, y in LONG.findall(body):
        try:
            out.append(datetime.date(int(y), MONTHS.index(mo.lower()) + 1, int(d)))
        except ValueError:
            pass
    return out


def fetch(room):
    req = urllib.request.Request(ORIGIN % room,
                                 headers={"User-Agent": "offplatform-evidence/1.0"})
    with urllib.request.urlopen(req, timeout=180) as r:
        raw = r.read().decode("utf-8", "replace")
    out = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def parse(msgs):
    jobs, delivers = {}, collections.defaultdict(list)
    for m in msgs:
        t = (m.get("text") or "").strip()
        p = [x.strip() for x in t.split("|")]
        if t.startswith("JOB v1 |") and len(p) >= 4:
            jobs[p[1]] = {"verb": p[2], "title": p[3],
                          "spec": p[4] if len(p) > 4 else "",
                          "who": m.get("from"), "ts": m.get("ts")}
        elif (t.startswith("RESULT v1 |") or t.startswith("DELIVER v1 |")) and len(p) >= 3:
            delivers[p[1]].append({"who": m.get("from"), "ts": m.get("ts"),
                                   "body": "|".join(p[2:]).strip()})
    return jobs, delivers


def head(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "offplatform-evidence/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:                                # noqa: BLE001
        return 0


def main(argv):
    room = "kibble"
    check_urls = "--check-urls" in argv
    all_jobs = "--all-jobs" in argv
    for a in argv[1:]:
        if not a.startswith("--"):
            room = a

    msgs = fetch(room)
    if not msgs:
        print("no messages from %s" % (ORIGIN % room))
        return 1
    jobs, delivers = parse(msgs)
    print("room r/%s   window %s -> %s   messages %d   jobs %d"
          % (room, msgs[0].get("ts"), msgs[-1].get("ts"), len(msgs), len(jobs)))

    # --- test 1 -----------------------------------------------------------
    off = {k: v for k, v in jobs.items() if OFFPLATFORM.search(v["spec"])}
    print("\n[1] success clause names an off-platform artifact: %d / %d (%.2f%%)"
          % (len(off), len(jobs), 100.0 * len(off) / max(1, len(jobs))))
    verbs = collections.Counter(v["verb"] for v in off.values())
    print("    verbs: %s" % verbs.most_common(6))

    scope = jobs if all_jobs else off
    if all_jobs:
        print("\n    --all-jobs: test 2 below is CONTAMINATED by legitimate historical")
        print("    citation. This mode exists to reproduce that, not to be quoted.")

    # --- test 2 -----------------------------------------------------------
    hits = []
    for k, j in scope.items():
        try:
            jd = datetime.date(*map(int, j["ts"][:10].split("-")))
        except Exception:                            # noqa: BLE001
            continue
        for d in delivers.get(k, []):
            if not PROCESS.search(d["body"]):
                continue
            ds = cited_dates(d["body"])
            if ds and min(ds) < jd:
                hits.append({"job": k, "job_ts": j["ts"], "spec": j["spec"],
                             "who": d["who"], "cited": min(ds),
                             "gap": (jd - min(ds)).days, "body": d["body"]})
    print("\n[2] delivery dates its own execution BEFORE the job was posted: %d" % len(hits))
    if hits:
        gaps = sorted(h["gap"] for h in hits)
        print("    gap in days  min/median/max : %d / %d / %d"
              % (gaps[0], gaps[len(gaps) // 2], gaps[-1]))
        print("    year cited   : %s"
              % sorted(collections.Counter(h["cited"].year for h in hits).items()))
        print("    distinct DIDs: %d" % len({h["who"] for h in hits}))
        for h in sorted(hits, key=lambda x: -x["gap"])[:5]:
            print("\n    %s posted %s, evidence dated %s (%d days early)"
                  % (h["job"], h["job_ts"][:19], h["cited"], h["gap"]))
            print("      spec: %s" % h["spec"][:140])
            print("      body: %s" % h["body"][:200].replace("\n", " "))

    # --- test 3 -----------------------------------------------------------
    phantom = []
    for k in scope:
        for d in delivers.get(k, []):
            for u in URL.findall(d["body"]):
                if SCORING_HOST in u:
                    phantom.append({"job": k, "who": d["who"], "url": u.rstrip(".,;")})
    print("\n[3] delivery cites the SCORING HOST as the home of its evidence: %d" % len(phantom))
    for p in phantom[:10]:
        status = head(p["url"]) if check_urls else None
        print("    %s  %s%s" % (p["job"], p["url"],
                                ("  -> HTTP %s" % status) if check_urls else ""))
    if phantom and not check_urls:
        print("    (pass --check-urls to resolve them)")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
