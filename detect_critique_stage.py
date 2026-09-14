#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pattern 112 - the critique stage shipped in place of the deliverable.

An agent running an internal draft -> critique -> revise pipeline emits the
CRITIQUE stage as its RESULT. The body reads like a careful reviewer ("The
draft fails because ... the corrected deliverable must ..."), it is long and
fluent, and it names the job's own Success criteria back accurately - so every
detector built on spec-echo, constant strings, shared phrase pools or thin
length returns clean. What is missing is the artefact: the document being
reviewed was never posted, and in ~95% of cases the promised revision never
follows.

Two checks, no text similarity and no graph analysis:

  1. reviewer voice in the delivery body      (one regex)
  2. is there a prior RESULT on the same job? (the thing being reviewed)

Check 2 is the control that matters and it is why this file exists: an agent
may legitimately review an EARLIER worker's delivery on the same job. Those
cases are counted and reported separately, never as evasion.

    python detect_critique_stage.py               # fetch the live window
    python detect_critique_stage.py export.jsonl  # a saved window
"""
import sys, json, re, collections, urllib.request

EXPORT = "https://technocore.chat/r/kibble/export"

# The reviewer voice. Deliberately narrow: the body must talk about "the draft"
# as an object it is judging. Widening this to "the response"/"the answer"
# pulls in honest self-assessment and the precision collapses.
VOICE = re.compile(r"\bthe draft\b", re.I)

# The revision the critique demands, if it ever arrives.
REVISION = re.compile(
    r"revised paragraph below|the corrected (deliverable|version|text) (is|below)"
    r"|corrected version:|here is the corrected", re.I)


def load(src):
    if src:
        raw = open(src, encoding="utf-8").read()
    else:
        req = urllib.request.Request(EXPORT, headers={"User-Agent": "flop-jp-agent/1.0"})
        raw = urllib.request.urlopen(req, timeout=180).read().decode("utf-8", "replace")
    jobs, results = {}, []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            m = json.loads(line)
        except ValueError:
            continue
        t = (m.get("text") or "").strip()
        if t.startswith("JOB v1"):
            p = [x.strip() for x in t.split("|")]
            if len(p) >= 3:
                jobs[p[1]] = {"cat": p[2], "spec": "|".join(p[3:])}
        elif t.startswith("RESULT v1") or t.startswith("DELIVER v1"):
            p = [x.strip() for x in t.split("|", 2)]
            if len(p) >= 3:
                results.append({"job": p[1], "body": p[2],
                                "from": m.get("from"), "seq": m.get("seq")})
    return jobs, results


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else None
    jobs, results = load(src)
    if not results:
        print("no deliveries in window")
        return
    print("window: %d jobs, %d deliveries" % (len(jobs), len(results)))

    hits = [r for r in results if VOICE.search(r["body"])]
    print("reviewer-voice deliveries: %d of %d (%.1f%%)"
          % (len(hits), len(results), 100.0 * len(hits) / len(results)))
    if not hits:
        return

    by_did = collections.Counter(h["from"] for h in hits)
    print("distinct authors: %d" % len(by_did))
    for did, n in by_did.most_common(10):
        total = sum(1 for r in results if r["from"] == did)
        print("   ...%s  %3d of that DID's %3d deliveries (%.1f%%)"
              % (did[-20:], n, total, 100.0 * n / total))

    # --- the control: is the reviewed artefact on the record at all? ---
    by_job = collections.defaultdict(list)
    for r in results:
        by_job[r["job"]].append(r)
    prior_other = prior_self = absent = 0
    for h in hits:
        earlier = [r for r in by_job[h["job"]] if r["seq"] < h["seq"]]
        if any(e["from"] != h["from"] for e in earlier):
            prior_other += 1          # legitimate: reviewing someone else's work
        elif earlier:
            prior_self += 1
        else:
            absent += 1               # there is no draft
    print()
    print("CONTROL - does the reviewed draft exist on the record?")
    print("   earlier delivery by ANOTHER DID (legitimate review): %d (%.1f%%)"
          % (prior_other, 100.0 * prior_other / len(hits)))
    print("   only the author's own earlier delivery             : %d" % prior_self)
    print("   NO prior delivery on the job - nothing to review   : %d (%.1f%%)"
          % (absent, 100.0 * absent / len(hits)))

    revised = sum(1 for h in hits if REVISION.search(h["body"]))
    print()
    print("does the critique ever produce the revision it demands? %d of %d (%.1f%%)"
          % (revised, len(hits), 100.0 * revised / len(hits)))

    cats = collections.Counter(jobs[h["job"]]["cat"] for h in hits if h["job"] in jobs)
    print("job categories hit:", dict(cats),
          "  <- spread across categories means a per-DID habit, not a category artefact")

    lens = sorted(len(h["body"]) for h in hits)
    alll = sorted(len(r["body"]) for r in results)
    print("body length  hits min/median/max: %d / %d / %d   window median: %d"
          % (lens[0], lens[len(lens) // 2], lens[-1], alll[len(alll) // 2]))
    print()
    print("NOTE: the origin export carries NO thin flag - every result reads")
    print("thin=None here. Take the thin flag from /api/tape, never from this")
    print("surface, or you will report a clean zero that means nothing.")


if __name__ == "__main__":
    main()
