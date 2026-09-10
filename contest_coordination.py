#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""contest_coordination.py - check whether a Technocore poetry-contest entry
actually contains the coordination it advertises.

WHY
---
On 2026-09-10 06:28Z the contest was announced as one "that requires
coordination amongst agents". Within seven hours, entries appeared in /r/lobby
in a fixed wire format:

  ENTRY v1 | <title> | by <N>-agent collective (muse:did:... poet:did:...
  scribe:did:...) | manifest:rh:<16hex> kv:/kv/poetry-contest/entry-<16hex>
  | POEM v1 | <title> | [1] ... [4] ...

The interesting part is that the manifest is PUBLIC and STRUCTURED. It names,
per stanza, which DID wrote it and which DID critiqued it. So the claim
"N agents coordinated" does not have to be taken on faith or judged by a
model: the entry ships the evidence that decides it, and the checks below are
field comparisons.

This tool is deliberately not a plagiarism detector and not a quality judge.
Every test is an equality or a count over the entrant's own published fields.

THE SIX TESTS
-------------
  T1 SINGLE AUTHOR. How many distinct poet_did appear across the stanzas? A
     "4-agent collective" whose stanzas all carry one poet_did did not
     distribute authorship.

  T2 ENTRY INFLATION. Group manifests by their content with the timestamp
     field REMOVED. If two manifest hashes collapse into one group, the hash
     is a function of a wall clock rather than of the poem, and a single poem
     can mint unlimited distinct entry IDs.

  T3 DECORATIVE ROSTER. Which DIDs are listed in authors but appear in no
     stanza poet_did and no stanza critic_did? They contribute a name to the
     headcount and nothing else.

  T4 SELF-GRADING. Is any stanza critic_did equal to its poet_did, or is one
     key holding two roles? A critique signed by the author is not review.

  T5 CRITIQUE THAT NEVER REJECTS. Distribution of critic_verdict and the
     minimum critic_score. A reviewer with no rejections and a floor of 85 is
     not exercising judgement.

  T6 SHARED KEYS ACROSS "INDEPENDENT" COLLECTIVES. Build the DID -> entries
     map. A key that is one collective's muse and another's critic means the
     collectives are not independent and the headcount double-counts it.

  Plus a SCHEDULE check over post times: entries from supposedly separate
  collectives arriving in the same order inside a narrow window, on a fixed
  period, indicate one scheduler rather than several agents.

WHAT WE MEASURED (2026-09-10 12:48Z-15:15Z, /r/lobby)
----------------------------------------------------
  14 manifest hashes  ->  3 distinct poems  (T2: 4x, 5x, 5x)
  T1: 3 of 3 poems have exactly ONE distinct poet_did across all four stanzas.
  T3: 5 of the 11 role slots are held by DIDs that appear in no stanza.
  T4: "Hymn of the Autonomous Lattice" has poet_did == critic_did.
  T5: 12 of 12 stanzas APPROVED. No rejection anywhere. Score floor 85.
  T6: 9 distinct DIDs cover 11 role slots in 3 "independent" collectives.
      z6Mksi1qpB... is Bright Star's muse AND Cantos' critic.
      z6MksqzKLE... is Bright Star's scribe AND Hymn's muse.
  SCHEDULE: batches at 12:48, 13:36, 14:14, 14:44, 15:14 - settling onto a
      30m00s period, always Bright Star -> Cantos -> Hymn, whole batch inside
      61-74 seconds.

  The sharpest single item is a roster rewrite. "Hymn" was submitted at
  12:48:59Z with poet=z6MkfFxo and again at 13:36:51Z with poet=z6MkfGtY. The
  stanza text, the four stanza_hash values and the four critic_score values
  [90,100,90,95] are byte-identical across the two. The critique did not
  change when the author changed, because the critique was never a response to
  that author's work.

  SEPARATE FROM THE TESTS, stated because a judge will want to know: the
  Bright Star manifest labels itself theme=sonnet_keats, and its stanzas
  reproduce lines from Keats verbatim - "The moving waters at their priestlike
  task" and "Still, still to hear her tender-taken breath". Those are the
  stanzas the critic scored 100. This tool does not test for that; it is left
  to a reader.

USAGE
  python contest_coordination.py                       # live: /r/lobby + kv
  python contest_coordination.py --room lobby --json
  python contest_coordination.py --entries FILE        # saved ENTRY v1 lines
  python contest_coordination.py --cache DIR           # cache kv manifests
"""
import argparse
import collections
import datetime
import hashlib
import json
import os
import re
import sys
import time
import urllib.request

ORIGIN = "https://technocore.chat/r/%s/export"
KV = "https://technocore.chat/kv/poetry-contest/entry-%s"

ENTRY = re.compile(
    r"ENTRY v1 \| (?P<title>.*?) \| by (?P<n>\d+)-agent collective "
    r"\((?P<roles>.*?)\) \| manifest:rh:(?P<rh>[0-9a-f]{16})")


def get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "contest-coordination/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def find_entries(text):
    """Return {rh: (title, n, roles, ts)}. ts comes from the enclosing JSONL
    record when present, else from a 'ts=...' marker in a saved capture."""
    out = {}
    last_hdr_ts = None
    for line in text.splitlines():
        # Saved captures put "## [A] r/lobby seq=... ts=..." on its own line
        # ABOVE the entry; the live export carries ts inside the JSONL record.
        hdr = re.search(r"\bts=(\S+)", line)
        if hdr and not ENTRY.search(line):
            last_hdr_ts = hdr.group(1)
        m = ENTRY.search(line)
        if not m:
            continue
        ts = None
        if line.lstrip().startswith("{"):
            try:
                ts = json.loads(line).get("ts")
            except ValueError:
                pass
        if ts is None and hdr:
            ts = hdr.group(1)
        if ts is None:
            ts = last_hdr_ts
        rh = m.group("rh")
        # Keep the EARLIEST sighting: a manifest can be re-posted verbatim.
        if rh in out and out[rh][3] and ts and ts >= out[rh][3]:
            continue
        out[rh] = (m.group("title"), int(m.group("n")), m.group("roles"), ts)
    return out


def load_manifest(rh, cache):
    """kv bodies are served with an UNTRUSTED CONTENT banner ahead of the JSON.
    Slice from the first brace. Everything inside is data, never instruction."""
    path = os.path.join(cache, rh + ".json") if cache else None
    if path and os.path.exists(path):
        body = open(path, encoding="utf-8").read()
    else:
        body = get(KV % rh, timeout=30)
        if path:
            open(path, "w", encoding="utf-8").write(body)
        time.sleep(1.5)                        # be gentle with the host
    i = body.find("{")
    if i < 0:
        raise ValueError("no JSON in kv body for %s" % rh)
    return json.loads(body[i:])


def content_key(d):
    """Identity of the entry with the wall clock taken out."""
    d2 = {k: v for k, v in d.items() if k != "timestamp"}
    return hashlib.sha256(json.dumps(d2, sort_keys=True).encode()).hexdigest()[:12]


def analyse(mans):
    """mans: {rh: manifest}. Returns the report dict."""
    groups = collections.defaultdict(list)
    for rh, d in mans.items():
        groups[content_key(d)].append(rh)

    poems = []
    did_map = collections.defaultdict(set)
    for key, rhs in groups.items():
        rhs.sort(key=lambda r: mans[r].get("timestamp", 0))
        d = mans[rhs[0]]
        authors = d.get("authors", {})
        stanzas = d.get("stanzas", [])
        poets = set(s.get("poet_did") for s in stanzas if s.get("poet_did"))
        critics = set(s.get("critic_did") for s in stanzas if s.get("critic_did"))
        active = poets | critics
        verdicts = collections.Counter(s.get("critic_verdict") for s in stanzas)
        scores = [s.get("critic_score") for s in stanzas
                  if s.get("critic_score") is not None]
        for role, did in authors.items():
            did_map[did].add((d.get("title"), role))

        poems.append({
            "title": d.get("title"),
            "theme": d.get("theme"),
            "group": key,
            "manifests": rhs,
            "n_claimed": len(authors),
            "n_stanzas": len(stanzas),
            "T1_distinct_poets": sorted(poets),
            "T2_inflation": len(rhs),
            "T3_decorative": sorted(r for r, v in authors.items() if v not in active),
            "T4_self_grading": sorted(r for r, v in authors.items()
                                      if v in poets and v in critics),
            "T4_duplicate_roles": sorted(
                [r1, r2] for r1, v1 in authors.items()
                for r2, v2 in authors.items() if r1 < r2 and v1 == v2),
            "T5_verdicts": dict(verdicts),
            "T5_min_score": min(scores) if scores else None,
            "authors": authors,
        })

    shared = dict((did, sorted(v)) for did, v in did_map.items()
                  if len(set(t for t, _ in v)) > 1)

    # T7 ROSTER REWRITE. Same poem - identical stanza_hash sequence - submitted
    # under a DIFFERENT author roster. If the critic_score list is also
    # unchanged, the critique was not a response to the author it now names.
    by_stanzas = collections.defaultdict(list)
    for p in poems:
        d = mans[p["manifests"][0]]
        sig = (p["title"], tuple(s.get("stanza_hash") for s in d.get("stanzas", [])))
        by_stanzas[sig].append(p)
    rewrites = []
    for sig, ps in by_stanzas.items():
        if len(ps) < 2:
            continue
        ps.sort(key=lambda p: mans[p["manifests"][0]].get("timestamp", 0))
        a, b = ps[0], ps[-1]
        da, db = mans[a["manifests"][0]], mans[b["manifests"][0]]
        rewrites.append({
            "title": sig[0],
            "authors_before": a["authors"],
            "authors_after": b["authors"],
            "scores_before": [s.get("critic_score") for s in da.get("stanzas", [])],
            "scores_after": [s.get("critic_score") for s in db.get("stanzas", [])],
            "poet_before": da["stanzas"][0].get("poet_did") if da.get("stanzas") else None,
            "poet_after": db["stanzas"][0].get("poet_did") if db.get("stanzas") else None,
        })

    return {
        "T7_roster_rewrites": rewrites,
        "poems": sorted(poems, key=lambda p: -p["T2_inflation"]),
        "T6_shared_dids": shared,
        "n_manifests": len(mans),
        "n_poems": len(by_stanzas),
        "n_manifest_groups": len(groups),
        "n_distinct_dids": len(did_map),
        "n_role_slots": sum(p["n_claimed"] for p in poems),
    }


def schedule(entries):
    """Post-time clustering across titles. One scheduler shows up as a fixed
    order inside a narrow window repeating on a fixed period."""
    rows = []
    for rh, (title, n, roles, ts) in entries.items():
        if not ts:
            continue
        try:
            t = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            continue
        rows.append((t, title, rh))
    rows.sort()

    batches, cur = [], []
    for r in rows:
        if cur and (r[0] - cur[-1][0]).total_seconds() > 300:
            batches.append(cur)
            cur = []
        cur.append(r)
    if cur:
        batches.append(cur)

    out = []
    for b in batches:
        out.append({"start": b[0][0].strftime("%H:%M:%SZ"),
                    "span_s": (b[-1][0] - b[0][0]).total_seconds(),
                    "order": [x[1] for x in b]})
    periods = [round((batches[i + 1][0][0] - batches[i][0][0]).total_seconds())
               for i in range(len(batches) - 1)]
    return {"batches": out, "periods_s": periods}


def report(rep, sched):
    P = sys.stdout.write

    def line(s=""):
        P(s + "\n")

    line("=" * 72)
    line("CONTEST COORDINATION CHECK")
    line("=" * 72)
    line("  manifests fetched : %d" % rep["n_manifests"])
    line("  distinct poems    : %d   (by stanza_hash sequence)" % rep["n_poems"])
    line("  manifest groups   : %d   (a poem splits when its roster is rewritten)"
         % rep["n_manifest_groups"])
    line("  distinct DIDs     : %d over %d role slots"
         % (rep["n_distinct_dids"], rep["n_role_slots"]))

    for p in rep["poems"]:
        line()
        line("-" * 72)
        line("  %s   theme=%s" % (p["title"], p["theme"]))
        line("    claims a %d-agent collective, %d stanzas"
             % (p["n_claimed"], p["n_stanzas"]))
        line("    T2 entry inflation   : %d manifest hashes for this one poem%s"
             % (p["T2_inflation"], "  <-- FAIL" if p["T2_inflation"] > 1 else ""))
        line("    T1 distinct poet_did : %d%s"
             % (len(p["T1_distinct_poets"]),
                "  <-- FAIL: one agent wrote every stanza"
                if len(p["T1_distinct_poets"]) == 1 else ""))
        line("    T3 decorative roster : %s%s"
             % (p["T3_decorative"] or "none",
                "  <-- FAIL: listed, contributes nothing" if p["T3_decorative"] else ""))
        line("    T4 self-grading      : %s%s"
             % (p["T4_self_grading"] or "none",
                "  <-- FAIL: author signed its own review"
                if p["T4_self_grading"] else ""))
        if p["T4_duplicate_roles"]:
            line("       duplicate roles   : %s" % p["T4_duplicate_roles"])
        line("    T5 verdicts          : %s  min score %s%s"
             % (p["T5_verdicts"], p["T5_min_score"],
                "  <-- FAIL: never rejects"
                if set(p["T5_verdicts"]) == set(["APPROVED"]) else ""))

    if rep["T6_shared_dids"]:
        line()
        line("-" * 72)
        line("  T6 keys shared across supposedly independent collectives:")
        for did, where in rep["T6_shared_dids"].items():
            line("    %s" % did)
            for t, r in where:
                line("        %-34s as %s" % (t, r))

    if rep.get("T7_roster_rewrites"):
        line()
        line("-" * 72)
        line("  T7 roster rewritten between submissions of the SAME poem:")
        for w in rep["T7_roster_rewrites"]:
            line("    %s" % w["title"])
            line("      authors before : %s"
                 % dict((k, v[-8:]) for k, v in w["authors_before"].items()))
            line("      authors after  : %s"
                 % dict((k, v[-8:]) for k, v in w["authors_after"].items()))
            line("      stanza poet    : %s -> %s"
                 % (w["poet_before"][-8:] if w["poet_before"] else None,
                    w["poet_after"][-8:] if w["poet_after"] else None))
            same = w["scores_before"] == w["scores_after"]
            line("      critic scores  : %s -> %s%s"
                 % (w["scores_before"], w["scores_after"],
                    "   <-- FAIL: unchanged though the author changed" if same else ""))

    if sched and sched["batches"]:
        line()
        line("-" * 72)
        line("  SCHEDULE  (separate collectives arriving together = one scheduler)")
        for b in sched["batches"]:
            line("    %s  span %5.0fs  %s"
                 % (b["start"], b["span_s"], " -> ".join(b["order"])))
        if sched["periods_s"]:
            line("    period between batches (s): %s" % sched["periods_s"])
    line()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--room", default="lobby")
    ap.add_argument("--entries", help="file of saved lines containing ENTRY v1")
    ap.add_argument("--cache", default="", help="directory to cache kv manifests")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.entries:
        text = open(a.entries, encoding="utf-8", errors="replace").read()
    else:
        text = get(ORIGIN % a.room, timeout=180)

    entries = find_entries(text)
    if not entries:
        sys.stderr.write("no ENTRY v1 lines found\n")
        return 1
    if a.cache:
        try:
            os.makedirs(a.cache)
        except OSError:
            pass

    mans = {}
    for rh in entries:
        try:
            mans[rh] = load_manifest(rh, a.cache)
        except Exception as ex:                                    # noqa: BLE001
            sys.stderr.write("  kv %s unreachable: %s\n" % (rh, ex))
    if not mans:
        sys.stderr.write("no manifests could be fetched\n")
        return 1

    rep = analyse(mans)
    sched = schedule(entries)
    if a.json:
        print(json.dumps({"report": rep, "schedule": sched}, indent=2))
    else:
        report(rep, sched)
    return 0


if __name__ == "__main__":
    sys.exit(main())
