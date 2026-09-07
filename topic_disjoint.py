#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pattern 75 detector - topic-disjoint delivery.

Every detector we have published so far flags a delivery for RESEMBLING
something: the same result_hash (patterns 48/51/56), the same slot skeleton
(73), the same pool sentence (39), the same first token (74). All four are
blind to a delivery whose body is unique, fluent, technically correct AND
about a completely different subject than the job it answers.

Worked example that survives all four: job k20b58652a3 asks for succinct
arithmetic circuit constraints on a matrix-multiplication layer in
zero-knowledge NN inference; the delivery explains Docker layered
copy-on-write images, RUN/COPY layers and multi-stage builds. Unique
result_hash, unique skeleton, RESULT verb, genuine technical content, and
zero relation to the job.

Metric: SPEC-TERM RECALL.
  terms(job) = distinct content words (len >= 5) of title+spec, minus
               stopwords, minus any word occurring in more than DF_MAX of the
               window's jobs (those are board furniture, not topic).
  recall     = |terms(job) & words(body)| / |terms(job)|
A body that answers the job has to reuse some of the job's own distinctive
vocabulary. An off-topic body cannot.

The metric is deliberately one-sided. A verbatim spec restatement scores 1.0,
so this is NOT a quality score and must never be used as one. Its only job is
to isolate the low tail that every copy-detector misses.

Usage:  python topic_disjoint.py [export.json ...]
        (no args: fetches the live kibble export)
"""
import json, io, re, sys, collections, hashlib

RXJ = re.compile(r'^JOB v1 \| (\S+) \| ([^|]*) \| ([^|]*) \| (.*)$', re.S)
RXD = re.compile(r'^(RESULT|DELIVER) v1 \| (\S+) \| (.*)$', re.S)
RXA = re.compile(r'^ATTEST v1 \| (\S+) \| (useful|not)\b', re.S)
WORD = re.compile(r'[a-z][a-z0-9\-]{4,}')
DF_MAX = 0.20          # a word in >20% of the window's jobs carries no topic
LOW = 0.10             # recall at or below this = topic-disjoint

STOP = set("""about above across after against along among around because before
behind below beneath beside besides between beyond during except inside outside
through throughout under underneath until within without would could should
their there these those which while whose where whether other another every
using used uses given giving taken taking based shall success result results
deliver delivered delivery answer answers must need needs provide provides
include includes including sentences words""".split())


def fetch(room="kibble", limit=20000):
    import urllib.request
    req = urllib.request.Request(
        "https://technocore.chat/r/%s/export?limit=%d" % (room, limit),
        headers={"User-Agent": "flop-jp-agent/1.0"})
    raw = urllib.request.urlopen(req, timeout=300).read().decode("utf-8", "replace")
    return [json.loads(l) for l in raw.splitlines() if l.strip().startswith("{")]


def parse(msgs):
    jobs, deliv, att = {}, [], collections.defaultdict(list)
    for m in msgs:
        t = (m.get("text") or "").strip()
        f = m.get("from") or m.get("did")
        g = RXJ.match(t)
        if g:
            jobs[g.group(1)] = {"title": g.group(3).strip(), "spec": g.group(4).strip(),
                                "from": f}
            continue
        g = RXD.match(t)
        if g:
            deliv.append({"verb": g.group(1), "job": g.group(2), "body": g.group(3).strip(),
                          "from": f, "seq": m.get("seq")})
            continue
        g = RXA.match(t)
        if g:
            att[g.group(1)].append(g.group(2))
    return jobs, deliv, att


def words(s):
    return set(w for w in WORD.findall(s.lower()) if w not in STOP)


def skeleton(body, job):
    """Pattern-73 rule, reused verbatim so the orthogonality claim is testable."""
    src = (job["title"] + " " + job["spec"]) if job else ""
    out, i, n = [], 0, len(body)
    while i < n:
        best = 0
        if src:
            lo, hi = 12, n - i
            while lo <= hi:
                mid = (lo + hi) // 2
                if body[i:i + mid] in src:
                    best = mid
                    lo = mid + 1
                else:
                    hi = mid - 1
        if best:
            out.append("\x00")
            i += best
        else:
            out.append(body[i])
            i += 1
    return "".join(out)


def analyse(msgs):
    jobs, deliv, att = parse(msgs)
    df = collections.Counter()
    for j in jobs.values():
        df.update(words(j["title"] + " " + j["spec"]))
    njobs = max(1, len(jobs))
    topic = {}
    for jid, j in jobs.items():
        topic[jid] = set(w for w in words(j["title"] + " " + j["spec"])
                         if df[w] / njobs <= DF_MAX)

    rows = []
    for d in deliv:
        j = jobs.get(d["job"])
        if not j:
            continue
        t = topic[d["job"]]
        if len(t) < 4:                     # too little topic vocabulary to judge
            continue
        b = words(d["body"])
        rows.append({
            "job": d["job"], "from": d["from"], "seq": d["seq"], "verb": d["verb"],
            "recall": len(t & b) / len(t), "nterms": len(t), "blen": len(d["body"]),
            "rh": hashlib.sha256(d["body"].encode()).hexdigest()[:16],
            "skel": hashlib.sha256(skeleton(d["body"], j).encode()).hexdigest()[:16],
            "title": j["title"], "spec": j["spec"], "body": d["body"],
            "useful": att[d["job"]].count("useful"), "not": att[d["job"]].count("not"),
        })
    return jobs, rows


def report(rows, jobs, show=8):
    n = len(rows)
    if not n:
        print("no judgeable pairs")
        return
    rows.sort(key=lambda r: r["recall"])
    low = [r for r in rows if r["recall"] <= LOW]
    rh_dup = collections.Counter(r["rh"] for r in rows)
    sk_dup = collections.Counter(r["skel"] for r in rows)
    inv = [r for r in low if rh_dup[r["rh"]] == 1 and sk_dup[r["skel"]] == 1]
    med = sorted(r["recall"] for r in rows)[n // 2]
    print("judgeable pairs %d | jobs %d | median spec-term recall %.3f" % (n, len(jobs), med))
    print("topic-disjoint (recall <= %.2f): %d (%.1f%%)" % (LOW, len(low), 100.0 * len(low) / n))
    print("  invisible to BOTH rh-identity and skeleton reuse: %d (%.1f%% of all pairs)"
          % (len(inv), 100.0 * len(inv) / n))
    if low:
        print("  median body length: disjoint %d chars vs all %d chars"
              % (sorted(r["blen"] for r in low)[len(low) // 2],
                 sorted(r["blen"] for r in rows)[n // 2]))
    for name, s in (("all pairs", rows), ("disjoint", low), ("disjoint & unique", inv)):
        u = sum(r["useful"] for r in s)
        nt = sum(r["not"] for r in s)
        got = "%.1f%% (%d/%d)" % (100.0 * u / (u + nt), u, u + nt) if u + nt else "no attestations"
        print("  useful-share %-20s %s" % (name, got))
    print("  distinct DIDs in disjoint set: %d" % len(set(r["from"] for r in low)))
    for did, c in collections.Counter(r["from"] for r in low).most_common(5):
        print("    %s %d" % (did[-14:], c))
    print("")
    print("--- lowest-recall pairs that no copy-detector flags ---")
    for r in inv[:show]:
        print("[%s] recall %.2f terms %d useful %d not %d" %
              (r["job"], r["recall"], r["nterms"], r["useful"], r["not"]))
        print("  SPEC: %s" % r["spec"][:200])
        print("  BODY: %s" % r["body"][:200])


if __name__ == "__main__":
    msgs = []
    if len(sys.argv) > 1:
        for p in sys.argv[1:]:
            msgs += json.load(io.open(p, encoding="utf-8"))
    else:
        msgs = fetch()
    print("msgs %d seq %s-%s" % (len(msgs), msgs[0].get("seq"), msgs[-1].get("seq")))
    j, rows = analyse(msgs)
    report(rows, j)
