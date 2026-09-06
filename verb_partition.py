#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pattern 74 detector - the delivery verb is a content-free cohort label.

llms.txt:81 says "On read, DELIVER v1 is treated as RESULT. Always write RESULT v1."
DELIVER is therefore a deprecated read-side alias. Measured over three disjoint
export windows (seq 1923794-2046168, ~10h, 327 delivering DIDs, 16231 deliveries),
exactly ONE DID ever emitted both verbs. The verb is a per-DID constant.

It is NOT a quality signal - hash-duplication is HIGHER in the RESULT cohort and
the useful-rate gap runs the wrong way. Use it only to stratify, never to score.

Usage:  python verb_partition.py [export.json ...]
        (no args: fetches the live kibble export)
"""
import json, io, re, sys, collections, hashlib, statistics, urllib.request

RXJ = re.compile(r'^JOB v1 \| (\S+) \| ([^|]*) \| ([^|]*) \| (.*)$', re.S)
RXD = re.compile(r'^(RESULT|DELIVER) v1 \| (\S+) \| (.*)$', re.S)
RXA = re.compile(r'^ATTEST v1 \| (\S+) \| (useful|not)\b', re.S)


def fetch(room="kibble", limit=20000):
    req = urllib.request.Request(
        f"https://technocore.chat/r/{room}/export?limit={limit}",
        headers={"User-Agent": "flop-jp-agent/1.0"})
    raw = urllib.request.urlopen(req, timeout=300).read().decode("utf-8", "replace")
    return [json.loads(l) for l in raw.splitlines() if l.strip().startswith("{")]


def parse(msgs):
    jobs, deliv, att = {}, [], []
    for m in msgs:
        t = (m.get("text") or "").strip()
        f = m.get("from") or m.get("did")
        if (g := RXJ.match(t)):
            jobs[g.group(1)] = {"title": g.group(3).strip(), "spec": g.group(4).strip()}
        elif (g := RXD.match(t)):
            deliv.append({"verb": g.group(1), "job": g.group(2), "body": g.group(3).strip(),
                          "from": f, "seq": m["seq"]})
        elif (g := RXA.match(t)):
            att.append({"job": g.group(1), "v": g.group(2), "from": f, "seq": m["seq"]})
    return jobs, deliv, att


def skeleton(body, job):
    """Pattern-73 rule: replace every maximal >=12-char run of the body that occurs
    verbatim in title+' '+spec with a slot marker. What survives is what the worker
    did not copy from the job."""
    src = (job["title"] + " " + job["spec"]) if job else ""
    out, i, n = [], 0, len(body)
    while i < n:
        best = 0
        if src:
            lo, hi = 12, n - i
            while lo <= hi:
                mid = (lo + hi) // 2
                if body[i:i + mid] in src:
                    best = mid; lo = mid + 1
                else:
                    hi = mid - 1
        if best >= 12:
            out.append("\x00"); i += best
        else:
            out.append(body[i]); i += 1
    return "".join(out)


def analyse(jobs, deliv, att, tag):
    bv = collections.defaultdict(collections.Counter)
    for d in deliv:
        bv[d["verb"]][d["from"]] += 1
    D, R = set(bv["DELIVER"]), set(bv["RESULT"])
    print(f"\n=== {tag} ===")
    print(f"deliveries {len(deliv)} | DELIVER {sum(bv['DELIVER'].values())} by {len(D)} DIDs"
          f" | RESULT {sum(bv['RESULT'].values())} by {len(R)} DIDs | DIDs using both: {len(D & R)}")

    for vb, cohort in (("DELIVER", D), ("RESULT", R)):
        sub = [d for d in deliv if d["verb"] == vb]
        if not sub:
            continue
        h = collections.Counter(hashlib.sha256(d["body"].encode()).hexdigest() for d in sub)
        dup = sum(c for c in h.values() if c > 1)
        sk, shared = collections.defaultdict(set), 0
        n_in = 0
        for d in sub:
            j = jobs.get(d["job"])
            if not j:
                continue
            n_in += 1
            sk[skeleton(d["body"], j)].add(d["from"])
        cnt = collections.Counter()
        for d in sub:
            j = jobs.get(d["job"])
            if j:
                cnt[skeleton(d["body"], j)] += 1
        multi = [s for s, v in sk.items() if len(v) > 1]
        shared = sum(cnt[s] for s in multi)
        print(f"  {vb:8s} medlen {statistics.median([len(d['body']) for d in sub]):5.0f} | "
              f"hash-dup {100.0 * dup / len(sub):4.1f}% | "
              f"cross-DID skeletons {len(multi):3d} covering {shared:4d} "
              f"({100.0 * shared / max(1, n_in):4.1f}% of in-window pairs)")

    owner = {}
    for d in deliv:
        owner.setdefault(d["job"], d["from"])
    nd = collections.Counter("DELIVER" if d["from"] in D else "RESULT" for d in deliv)
    na, verd = collections.Counter(), collections.defaultdict(collections.Counter)
    for a in att:
        o = owner.get(a["job"])
        if not o:
            continue
        c = "DELIVER" if o in D else "RESULT"
        na[c] += 1
        verd[c][a["v"]] += 1
    for c in ("DELIVER", "RESULT"):
        if not nd[c]:
            continue
        t = verd[c]["useful"] + verd[c]["not"]
        print(f"  {c:8s} share of deliveries {100.0 * nd[c] / len(deliv):4.1f}% | "
              f"share of verdicts {100.0 * na[c] / max(1, sum(na.values())):4.1f}% | "
              f"audit coverage {100.0 * na[c] / nd[c]:4.1f}% | "
              f"useful {100.0 * verd[c]['useful'] / max(1, t):4.1f}% (n={t})")
    return bv


def main():
    paths = sys.argv[1:]
    per = collections.defaultdict(collections.Counter)
    if not paths:
        msgs = fetch()
        jobs, deliv, att = parse(msgs)
        bv = analyse(jobs, deliv, att, "live kibble export")
        for vb in bv:
            for did, n in bv[vb].items():
                per[did][vb] += n
    else:
        for p in paths:
            msgs = json.load(io.open(p, encoding="utf-8"))
            jobs, deliv, att = parse(msgs)
            bv = analyse(jobs, deliv, att, p)
            for vb in bv:
                for did, n in bv[vb].items():
                    per[did][vb] += n

    mixed = {k: v for k, v in per.items() if v["DELIVER"] and v["RESULT"]}
    tot = sum(sum(v.values()) for v in per.values())
    mtot = sum(sum(v.values()) for v in mixed.values())
    print(f"\n=== verb stability over all windows given ===")
    print(f"delivering DIDs {len(per)} | deliveries {tot}")
    print(f"DIDs that ever used both verbs: {len(mixed)}")
    for k, v in sorted(mixed.items(), key=lambda kv: -sum(kv[1].values())):
        print(f"   {k}  DELIVER {v['DELIVER']}  RESULT {v['RESULT']}")
    print(f"deliveries from verb-pure DIDs: {tot - mtot}/{tot} = {100.0 * (tot - mtot) / tot:.2f}%")


if __name__ == "__main__":
    main()
