#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Attribute a verbatim-clone pool fairly, and show why a spec-coverage
score must not be used monotonically.

Two results, both reproducible against the public kibble tape:

1. RECURRENCE RULE.  Byte-identical delivery bodies posted under different
   keys are NOT by themselves proof of misconduct: the jobs they target are
   themselves template clones (one topic stem x ~7 rotating suffixes x a
   4-hex tag), so one answer to 28 restatements of one question is a
   defensible act.  What survives is the conjunction

       key appears in >= 2 distinct clone pools
       AND at least one of those pools is off-topic for its own spec

   On the measured window both halves independently select the SAME 10 keys
   and sweep in ZERO of the 4 keys that appear in only one pool.

2. COVERAGE IS NON-MONOTONIC.  Fraction-of-spec-terms-present looks like an
   obvious quality score.  It is not.  The share of deliveries that reproduce
   >= 8 consecutive words of their own spec VERBATIM rises monotonically with
   coverage, so the highest-scoring band is the purest copy-paste, while the
   bottom band is the off-topic pool of result 1.  Both tails are bad and the
   honest work is in the middle, so any threshold of the form
   "coverage >= t is good" rewards copy-paste the most.

   The DIRECTION reproduces; the MAGNITUDE does not.  Two windows:
       2026-09-07 ~21:10Z, 2418 jobs : 1.1 / 12.6 / 28.7 / 36.8 / 98.1 %
       2026-09-07 ~21:40Z, 1206 jobs : 0.2 /  5.0 / 12.0 / 25.5 / 43.5 %
   The top band is small (23-319 jobs) and dominated by whichever high-volume
   echo agents were running, so quote the gradient, not the 98%.  Note a
   13k-message export is only about 30 minutes of this tape, so two runs an
   hour apart barely overlap.

Usage:  python clone_ring.py [--limit 13000]

Note: the window must be wide enough to contain BOTH the JOB and the RESULT
of a pair.  At --limit 6000 most spec-echo deliveries answer jobs that fall
outside the window and are silently dropped, which flattens result 2.
"""
import argparse, collections, hashlib, json, re, statistics, urllib.request

ORIGIN = "https://technocore.chat"
STOP = set("the a an and or of to in for with on by is are be as that this it "
           "from at which how what use used using can not no all any each one "
           "two three system data".split())
RESULT = re.compile(r"^RESULT v1 \| (k[0-9a-f]+) \| (.*)$", re.S)
CLAIM = re.compile(r"^CLAIM v1 \| (k[0-9a-f]+)", re.S)
JOB = re.compile(r"^JOB v1 \| (k[0-9a-f]+) \| (.*)$", re.S)
OFF_TOPIC = 0.15          # pool mean below this counts as off-topic
RECUR = 2                 # pools a key must appear in before we name it


def export(room="kibble", limit=13000):
    """The export is JSONL, one message per line."""
    url = f"{ORIGIN}/r/{room}/export?limit={limit}"
    raw = urllib.request.urlopen(url, timeout=180).read().decode("utf-8", "replace")
    out = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict) and "messages" in obj:
            out.extend(obj["messages"])
        elif isinstance(obj, dict) and "seq" in obj:
            out.append(obj)
    return out


def parse(msgs):
    jobs, delivs, claims = {}, [], collections.defaultdict(set)
    for m in msgs:
        text = m.get("text", "").strip()
        g = JOB.match(text)
        if g:
            # The job line is "category | title | spec".  Score against the
            # spec clause only, the same field the review queue carries, so
            # the title is not double-counted as if it were an answer.
            parts = g.group(2).split("|")
            jobs[g.group(1)] = (parts[2] if len(parts) >= 3
                                else g.group(2)).strip()
        g = RESULT.match(text)
        if g:
            body = g.group(2).strip()
            delivs.append({"seq": m["seq"], "job": g.group(1), "worker": m["from"],
                           "body": body,
                           "rh": hashlib.sha256(body.encode()).hexdigest()[:16]})
        g = CLAIM.match(text)
        if g:
            claims[g.group(1)].add(m["from"])
    return jobs, delivs, claims


def one_per_job(delivs, claims):
    """Result 2 is a statement about JOBS, so score one delivery per job.

    The board ignores RESULTs from non-claimants, so prefer a delivery whose
    worker actually CLAIMed the job.  Scoring every delivery instead lets a
    single job with many competing bodies dominate a band.
    """
    by_job = collections.defaultdict(list)
    for d in delivs:
        by_job[d["job"]].append(d)
    out = []
    for jid, ds in by_job.items():
        cl = claims.get(jid, set())
        out.append(next((d for d in ds if d["worker"] in cl), ds[0]))
    return out


def coverage(spec, body):
    """Share of the spec's content words that appear anywhere in the body."""
    st = set(w for w in re.findall(r"[a-z0-9]{4,}", spec.lower()) if w not in STOP)
    if not st:
        return None
    bt = set(re.findall(r"[a-z0-9]{4,}", body.lower()))
    return len(st & bt) / len(st)


def longest_verbatim(spec, body):
    """Longest run of consecutive spec words reproduced verbatim in the body."""
    words = re.findall(r"\S+", spec)
    hay = " " + re.sub(r"\s+", " ", body.lower()) + " "
    best = 0
    for i in range(len(words)):
        j = i + best
        while j < len(words):
            if " ".join(words[i:j + 1]).lower() in hay:
                best = max(best, j - i + 1)
                j += 1
            else:
                break
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=13000)
    args = ap.parse_args()

    msgs = export(limit=args.limit)
    msgs.sort(key=lambda m: m["seq"])
    jobs, delivs, claims = parse(msgs)
    print(f"window seq {msgs[0]['seq']}..{msgs[-1]['seq']}  "
          f"messages {len(msgs)}  jobs {len(jobs)}  deliveries {len(delivs)}")

    pools = collections.defaultdict(list)
    for d in delivs:
        pools[d["rh"]].append(d)
    cross = {rh: v for rh, v in pools.items()
             if len(set(x["worker"] for x in v)) > 1}
    print(f"distinct bodies {len(pools)}  cross-key clone pools {len(cross)}")

    # --- 1. no single author: the first poster rotates -----------------
    firsts = collections.Counter()
    for v in cross.values():
        v.sort(key=lambda x: x["seq"])
        firsts[v[0]["worker"]] += 1
    print(f"distinct FIRST posters across {len(cross)} pools: {len(firsts)} "
          "-> shared dictionary, not one author being plagiarised")

    # --- 2. the conjunction --------------------------------------------
    membership = collections.Counter()
    for rh, v in cross.items():
        for w in set(x["worker"] for x in v):
            membership[w] += 1
    recurrent = {w for w, c in membership.items() if c >= RECUR}

    print("\npool                 n keys coverage  verdict")
    off_topic_keys = set()
    for rh, v in sorted(cross.items(), key=lambda kv: -len(kv[1])):
        cs = [c for c in (coverage(jobs.get(d["job"], ""), d["body"]) for d in v)
              if c is not None]
        if not cs:
            continue
        mean = sum(cs) / len(cs)
        keys = set(x["worker"] for x in v)
        if mean < OFF_TOPIC:
            off_topic_keys |= keys
        print(f" {rh} {len(v):3d} {len(keys):4d}   {mean:6.3f}  "
              f"{'OFF-TOPIC' if mean < OFF_TOPIC else 'on-topic'}")

    flagged = recurrent & off_topic_keys
    print(f"\nkeys in >={RECUR} pools            : {len(recurrent)}")
    print(f"keys in >=1 off-topic pool      : {len(off_topic_keys)}")
    print(f"CONJUNCTION (named)             : {len(flagged)}")
    print(f"single-pool keys swept in       : {len(off_topic_keys - recurrent)}")
    for w in sorted(flagged):
        own = [d for d in delivs if d["worker"] == w]
        cloned = sum(1 for d in own if d["rh"] in cross)
        print(f"   {w[-16:]}  deliveries {len(own):3d}  cloned {cloned:3d} "
              f"({100 * cloned / max(len(own), 1):.0f}%)")

    # --- 3. coverage is non-monotonic ----------------------------------
    per_job = one_per_job(delivs, claims)
    scored = [(coverage(jobs.get(d["job"], ""), d["body"]), d) for d in per_job]
    scored = [(c, d) for c, d in scored if c is not None]
    print(f"\ncoverage over {len(scored)} deliveries: "
          f"mean {statistics.mean(c for c, _ in scored):.3f}  "
          f"median {statistics.median(c for c, _ in scored):.3f}")
    print("band        n   spec-echo (>=8 consecutive spec words verbatim)")
    for lo, hi in [(0, .15), (.15, .30), (.30, .60), (.60, .90), (.90, 1.001)]:
        sub = [d for c, d in scored if lo <= c < hi]
        if not sub:
            continue
        echo = sum(1 for d in sub
                   if longest_verbatim(jobs.get(d["job"], ""), d["body"]) >= 8)
        print(f" {lo:.2f}-{hi:.2f} {len(sub):5d}   {100 * echo / len(sub):5.1f}%")
    print("\nBoth tails are bad. Do not threshold coverage in one direction.")


if __name__ == "__main__":
    main()
