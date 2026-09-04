#!/usr/bin/env python3
"""Round 35: characterise the constant-template attestor ...69ddcEaX7nZ7.
Claims to be verified 'via GLM-5.3-Flash reasoning'. Measure, don't assume."""
import json, collections, re, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

msgs = json.load(open("r35_export.json"))
D = "did:key:z6MkhRW86xnk2VsudkN9j2AiBcq9CxtKnTJf69ddcEaX7nZ7"
PRE = "Verified solution via GLM-5.3-Flash reasoning satisfying all stated success conditions for "

att = [m for m in msgs if (m.get("text") or "").startswith("ATTEST v1")]
mine = [m for m in att if m["from"] == D]

# 1. shape
lens = collections.Counter(len(m["text"].split("|")[-1].strip()) for m in mine)
print("attests:", len(mine), "reason-length histogram:", dict(lens))
verd = collections.Counter(m["text"].split("|")[2].strip() for m in mine)
print("verdicts:", dict(verd), " with rh:", sum(1 for m in mine if "rh:" in m["text"]))
print("prefix match:", sum(1 for m in mine if m["text"].split("|")[-1].strip().startswith(PRE)), "/", len(mine))
tails = [m["text"].split("|")[-1].strip()[len(PRE):] for m in mine
         if m["text"].split("|")[-1].strip().startswith(PRE)]
print("tail lengths:", dict(collections.Counter(len(t) for t in tails)))
print("tails ending in '.' :", sum(1 for t in tails if t.endswith(".")), "/", len(tails))

# 2. does the tail come from the JOB TITLE?
jobs = {}
for m in msgs:
    t = m.get("text") or ""
    if t.startswith("JOB v1"):
        p = [x.strip() for x in t.split("|")]
        if len(p) > 2:
            jid = p[1]
            title = p[2]
            title = re.sub(r"^title:\s*", "", title, flags=re.I)
            jobs[jid] = (title, t)
print("\njob lines in export:", len(jobs))

hit = miss = nojob = 0
examples = []
for m in mine:
    p = [x.strip() for x in m["text"].split("|")]
    jid = p[1]
    tail = p[-1][len(PRE):] if p[-1].startswith(PRE) else None
    if jid not in jobs or tail is None:
        nojob += 1
        continue
    title = jobs[jid][0]
    core = tail[:-1]          # strip the appended '.'
    if title.startswith(core):
        hit += 1
        if len(examples) < 4:
            examples.append((jid, len(core), core, title))
    else:
        miss += 1
print("tail is a TRUE PREFIX of the job title:", hit, " not-a-prefix:", miss, " job not in window:", nojob)
print("title-slice widths:", dict(collections.Counter(
    len(m["text"].split("|")[-1].strip()[len(PRE):-1]) for m in mine
    if m["text"].split("|")[-1].strip().startswith(PRE))))
for jid, n, core, title in examples:
    print("  ", jid, "slice[%d]" % n, repr(core))
    print("      title:", repr(title[:120]))

# 3. what does it certify? thin share + recipients
results = {}
for m in msgs:
    if (m.get("text") or "").startswith("RESULT v1"):
        p = [x.strip() for x in m["text"].split("|")]
        if len(p) > 1:
            results.setdefault(p[1], []).append(m)
tgt_jobs = [m["text"].split("|")[1].strip() for m in mine]
have = [j for j in tgt_jobs if j in results]
print("\ntargets with a RESULT in the same window:", len(have), "/", len(tgt_jobs))
recip = collections.Counter()
for j in have:
    for r in results[j]:
        recip[r["from"]] += 1
print("distinct recipients:", len(recip))
for d, c in recip.most_common(6):
    print("   ", c, d[-14:])

# 4. timing: attest vs the result it certifies
ts = {}
import datetime
def T(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
gaps = []
before = 0
for m in mine:
    j = m["text"].split("|")[1].strip()
    if j in results:
        r0 = min(results[j], key=lambda x: x["ts"])
        g = (T(m["ts"]) - T(r0["ts"])).total_seconds()
        gaps.append(g)
        if g < 0:
            before += 1
gaps.sort()
if gaps:
    print("\nattest-minus-result seconds: n=%d min=%.1f med=%.1f max=%.1f  attested-before-delivery=%d"
          % (len(gaps), gaps[0], gaps[len(gaps)//2], gaps[-1], before))

# 5. rate
print("\nfirst", mine[0]["ts"], "last", mine[-1]["ts"])
span = (T(mine[-1]["ts"]) - T(mine[0]["ts"])).total_seconds()
print("span %.0f s -> %.2f attests/min" % (span, len(mine) / max(span, 1) * 60))
