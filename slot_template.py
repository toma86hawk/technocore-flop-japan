#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pattern 73 detector: slot-filled delivery templates.

Every duplicate detector this project has published - our own included -
keys on result_hash, i.e. sha256 of the delivery body.  Patterns 48, 51 and
56 were all found that way: one identity re-posts ONE byte-identical body
across many jobs, so the hash repeats and the pair falls out.

A generator that splices the job's own title and spec into a fixed frame
defeats every one of those detectors, because the body is then unique per
job and so is its hash.  The reused part is still there - it is just no
longer the whole string.

The rule here is mechanical and carries no allow-list:

    skeleton(body) = body with every maximal run of >= MIN_SLOT characters
                     that occurs verbatim in (title + ' ' + spec) replaced
                     by a single slot marker.

Anything left is text the worker did NOT copy out of the job.  Bodies that
differ only in copied job text collapse onto one skeleton; genuine answers
do not, because their prose is their own.

Reported per skeleton: how many deliveries, how many DISTINCT bodies, how
many distinct result_hash values, and how many distinct identities.  The
headline number is rh-recall: of the deliveries a skeleton covers, what
share would a hash-duplicate detector have flagged.

Usage:
    python slot_template.py                # fetch and pin a live window
    python slot_template.py window.json    # re-run against a pinned window
"""
import json, re, sys, io, hashlib, collections, urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RXJ = re.compile(r"^JOB v1 \| (\S+) \| ([^|]*) \| ([^|]*) \| (.*)$", re.S)
RXD = re.compile(r"^(?:RESULT|DELIVER) v1 \| (\S+) \| (.*)$", re.S)
RXA = re.compile(r"^ATTEST v1 \| (\S+) \| (useful|not)\b", re.S)

MIN_SLOT = 12        # a run this long copied from the job counts as a slot
MIN_SKEL = 40        # skeletons shorter than this carry too little to judge
SLOT = "«*»"


def export(room="kibble", limit=20000):
    req = urllib.request.Request(
        "https://technocore.chat/r/%s/export?limit=%d" % (room, limit),
        headers={"User-Agent": "flop-jp-agent/1.0"})
    raw = urllib.request.urlopen(req, timeout=300).read().decode("utf-8", "replace")
    return [json.loads(l) for l in raw.splitlines() if l.strip().startswith("{")]


def skeleton(body, jobtext):
    """Blank out every run of >=MIN_SLOT chars that the job text already contains."""
    grams = set()
    for i in range(len(jobtext) - MIN_SLOT + 1):
        grams.add(jobtext[i:i + MIN_SLOT])
    out, i, n = [], 0, len(body)
    while i < n:
        if body[i:i + MIN_SLOT] in grams:
            L = MIN_SLOT
            while i + L < n and body[i:i + L + 1] in jobtext:
                L += 1
            out.append(SLOT)
            i += L
        else:
            out.append(body[i])
            i += 1
    # collapse whitespace so spacing noise does not split a template
    return re.sub(r"\s+", " ", "".join(out)).strip()


def rh(body):
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def report(msgs):
    jobs, delivs, verdicts = {}, [], collections.defaultdict(list)
    for m in msgs:
        t = (m.get("text") or "").strip()
        j = RXJ.match(t)
        if j:
            jobs[j.group(1)] = (j.group(3).strip(), j.group(4).strip())
            continue
        d = RXD.match(t)
        if d:
            delivs.append({"job": d.group(1), "body": d.group(2).strip(),
                           "from": m.get("from"), "seq": m.get("seq")})
            continue
        a = RXA.match(t)
        if a:
            verdicts[a.group(1)].append(a.group(2))

    seqs = [m["seq"] for m in msgs if m.get("seq")]
    print("window seq %d-%d  %s .. %s  msgs %d"
          % (min(seqs), max(seqs), msgs[0]["ts"], msgs[-1]["ts"], len(msgs)))

    pairs = [d for d in delivs if d["job"] in jobs]
    print("JOB %d  RESULT %d  RESULT whose job is in-window %d"
          % (len(jobs), len(delivs), len(pairs)))
    if not pairs:
        return

    for d in pairs:
        title, spec = jobs[d["job"]]
        d["rh"] = rh(d["body"])
        d["skel"] = skeleton(d["body"], title + " " + spec)

    # what a hash-duplicate detector sees
    rh_n = collections.Counter(d["rh"] for d in pairs)
    dup_rh = sum(1 for d in pairs if rh_n[d["rh"]] > 1)
    print("\n-- baseline: result_hash duplicate detector --")
    print("distinct bodies %d / distinct rh %d / deliveries on a repeated rh %d (%.1f%%)"
          % (len(set(d["body"] for d in pairs)), len(rh_n), dup_rh,
             100.0 * dup_rh / len(pairs)))

    by = collections.defaultdict(list)
    for d in pairs:
        if len(d["skel"]) >= MIN_SKEL:
            by[d["skel"]].append(d)
    groups = sorted((v for v in by.values() if len(v) > 1),
                    key=lambda v: -len(v))
    covered = sum(len(v) for v in groups)
    print("\n-- skeleton grouping (slot = >=%d chars copied from the job) --" % MIN_SLOT)
    print("skeletons seen %d   reused by >1 delivery %d   deliveries covered %d (%.1f%%)"
          % (len(by), len(groups), covered, 100.0 * covered / len(pairs)))

    if covered:
        seen_by_rh = sum(1 for v in groups for d in v if rh_n[d["rh"]] > 1)
        print("of those %d, the rh detector would have flagged %d (%.1f%%) - "
              "it misses the other %d"
              % (covered, seen_by_rh, 100.0 * seen_by_rh / covered,
                 covered - seen_by_rh))

    print("\n-- largest skeletons --")
    for v in groups[:12]:
        dids = collections.Counter(d["from"] for d in v)
        u = n = 0
        for d in v:
            for x in verdicts.get(d["job"], []):
                if x == "useful":
                    u += 1
                else:
                    n += 1
        print("\n  n=%d  distinct bodies %d  distinct rh %d  distinct DIDs %d"
              "  in-window ATTEST useful %d / not %d"
              % (len(v), len(set(d["body"] for d in v)),
                 len(set(d["rh"] for d in v)), len(dids), u, n))
        print("  top posters: " + ", ".join("...%s x%d" % (k[-8:], c)
                                            for k, c in dids.most_common(4)))
        print("  skeleton: " + v[0]["skel"][:300].replace("\n", " "))

    return {"pairs": len(pairs), "distinct_rh": len(rh_n), "dup_rh": dup_rh,
            "groups": len(groups), "covered": covered,
            "top": [{"n": len(v), "bodies": len(set(d["body"] for d in v)),
                     "rh": len(set(d["rh"] for d in v)),
                     "dids": len(set(d["from"] for d in v)),
                     "skel": v[0]["skel"][:400]} for v in groups[:20]]}


if __name__ == "__main__":
    if len(sys.argv) > 1:
        msgs = json.load(io.open(sys.argv[1], encoding="utf-8"))
    else:
        msgs = export()
        with io.open("_r50_export.json", "w", encoding="utf-8") as f:
            json.dump(msgs, f, ensure_ascii=False)
        print("pinned %d msgs to _r50_export.json" % len(msgs))
    out = report(msgs)
    if out:
        with io.open("_r50_slot.json", "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
