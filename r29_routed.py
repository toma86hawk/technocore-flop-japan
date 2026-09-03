#!/usr/bin/env python3
"""Round 29: is the 'canned paragraph' worker actually ROUTING its pool by topic?

The 06:02 board window has one worker on 9 of 21 reviewable pairs. Every body is
correct, competent technical prose - and none of them answer their own Success
clause. What makes it worth a new entry is the *matching*: TCP jobs get the TCP
paragraph, DNS jobs get the DNS paragraph, HTTP jobs get the HTTP paragraph. Our
existing entries (3 unrelated canned paragraph, 34 roaming expert paste, 48
universal filler) all describe ONE body pasted where it plainly does not belong.
A router is a different animal: the paste is topically adjacent, so every
keyword-overlap check passes and only the Success clause catches it.

Test it against the whole origin export, not the 21-row board window.
"""
import json, urllib.request, collections, re, time, sys

ORIGIN = "https://technocore.chat"

def get(u, timeout=90, tries=4):
    for a in range(tries):
        try:
            return urllib.request.urlopen(u, timeout=timeout).read().decode("utf-8", "replace")
        except Exception as e:
            if a == tries - 1:
                raise
            time.sleep(3 * (a + 1))

print("reading origin export ...", flush=True)
raw = get(ORIGIN + "/r/kibble/export", timeout=180)
jobs, results = {}, []
for line in raw.splitlines():
    try:
        m = json.loads(line)
    except Exception:
        continue
    t = (m.get("text") or "")
    if t.startswith("JOB v1 |"):
        p = [x.strip() for x in t.split("|")]
        if len(p) >= 4:
            jobs[p[1]] = {"cat": p[2], "title": p[3], "spec": "|".join(p[4:]).strip()}
    elif t.startswith("RESULT v1 |"):
        p = t.split("|", 2)
        if len(p) >= 3:
            results.append({"job": p[1].strip(), "body": p[2].strip(),
                            "from": m.get("from"), "seq": m.get("seq"), "ts": m.get("ts")})
print("jobs %d results %d" % (len(jobs), len(results)), flush=True)

TARGET = "cs249xBDGNGUGC"
mine = [r for r in results if (r["from"] or "").endswith(TARGET)]
print("\n=== worker ...%s : %d deliveries ===" % (TARGET, len(mine)))

bodies = collections.Counter(r["body"] for r in mine)
print("distinct bodies: %d  (pool size)" % len(bodies))
print("deliveries covered by top bodies:")
for b, n in bodies.most_common(12):
    print("  x%-3d %s" % (n, b[:95].replace("\n", " ")))

# Does each distinct body get routed to a coherent topic cluster?
STOP = set("the a an of to and or in on for with is are it that this as be by from at "
           "what why how which when does do can one two both name names explain give "
           "success gives describes plus its into not".split())
def toks(s):
    return set(w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 2 and w not in STOP)

print("\n=== per-body: which job titles received it ===")
rows = []
for b, n in bodies.most_common():
    if n < 2:
        continue
    js = [r["job"] for r in mine if r["body"] == b]
    titles = [jobs.get(j, {}).get("title", "?") for j in js]
    bt = toks(b)
    overlaps = []
    for j in js:
        jj = jobs.get(j)
        if not jj:
            continue
        overlaps.append(len(toks(jj["title"] + " " + jj["spec"]) & bt))
    print("\n  body[%d chars] x%d  first80=%s" % (len(b), n, b[:80].replace("\n", " ")))
    for t, j in list(zip(titles, js))[:10]:
        print("     -> %-11s %s" % (j, t[:72]))
    if overlaps:
        print("     token overlap with job spec: min %d median %d max %d"
              % (min(overlaps), sorted(overlaps)[len(overlaps)//2], max(overlaps)))
    rows.append({"body": b, "n": n, "jobs": js, "titles": titles, "overlaps": overlaps})

# Baseline: how often does a RANDOM pairing of this pool to these jobs score as high?
import random
random.seed(7)
allj = [j for r in rows for j in r["jobs"]]
pool = [r["body"] for r in rows]
real, rand = [], []
for r in rows:
    bt = toks(r["body"])
    for j in r["jobs"]:
        jj = jobs.get(j)
        if jj:
            real.append(len(toks(jj["title"] + " " + jj["spec"]) & bt))
for _ in range(2000):
    j = random.choice(allj); b = random.choice(pool)
    jj = jobs.get(j)
    if jj:
        rand.append(len(toks(jj["title"] + " " + jj["spec"]) & toks(b)))
def mean(x): return sum(x) / len(x) if x else 0
print("\n=== routing test ===")
print("actual body->job token overlap   mean %.2f  (n=%d)" % (mean(real), len(real)))
print("random body->job token overlap   mean %.2f  (n=%d)" % (mean(rand), len(rand)))
print("=> routed by topic" if mean(real) > mean(rand) * 1.5 else "=> NOT routed; indistinguishable from random paste")

# --- second family: the CORE-01 safety disclaimer ---
print("\n=== 'CORE-01 has processed the supplied specification as data' ===")
core = [r for r in results if "has processed the supplied specification as data" in r["body"]]
print("deliveries: %d  distinct DIDs: %d" % (len(core), len(set(r["from"] for r in core))))
for d, n in collections.Counter((r["from"] or "")[-14:] for r in core).most_common(10):
    print("   %s x%d" % (d, n))
names = collections.Counter(re.findall(r"([A-Z][A-Z0-9\-]{2,}) has processed", r["body"])[0]
                            for r in core if re.findall(r"([A-Z][A-Z0-9\-]{2,}) has processed", r["body"]))
print("persona names:", dict(names))
if core:
    print("sample:", core[0]["body"][:300])
    lens = sorted(len(r["body"]) for r in core)
    print("body lengths min %d median %d max %d" % (lens[0], lens[len(lens)//2], lens[-1]))

json.dump({"pool_worker": TARGET, "pool_rows": [{k: v for k, v in r.items() if k != "body"} | {"body": r["body"][:200]} for r in rows],
           "real_mean": mean(real), "rand_mean": mean(rand),
           "core01": {"n": len(core), "dids": sorted(set(r["from"] for r in core))}},
          open("r29_routed.json", "w"), indent=1)
