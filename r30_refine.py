import json, re, io, glob, collections
STOP = {"explain","how","why","works","work","a","an","the","of","in","is","are","to","and",
        "for","on","vs","versus","what","when","give","list","define","review","compare",
        "measure","with","its","sentences","sentence","success","one","two","three","that",
        "it","or","be","from","at","by","as","this","each","can","not","use","using","under"}
def norm(s): return re.sub(r"[^a-z0-9]+"," ",(s or "").lower()).strip()
def content(s): return set(norm(s).split())-STOP
def head(sp): return re.split(r"\bSuccess\s*:", sp or "")[0].strip().rstrip(".").strip()

pairs, seen = [], set()
for f in sorted(glob.glob("attest_runs/2026-09-0*.json")):
    for q in (json.load(io.open(f,encoding="utf-8")).get("queue") or []):
        k=(q["job_id"],q.get("rh"))
        if k not in seen: seen.add(k); pairs.append(q)

# only judge jobs whose spec instruction actually has a subject (>=3 content words)
judged = [p for p in pairs if len(content(head(p["spec"]))) >= 3 and len(content(p["title"])) >= 2]
mis = [p for p in judged if not (content(p["title"]) & content(head(p["spec"])))]
print("judgeable jobs (spec instruction has >=3 content words): %d" % len(judged))
print("title shares ZERO content words with its own spec       : %d (%.1f%%)" % (len(mis), 100.0*len(mis)/len(judged)))

# class 2: same value drawn into both slots of one spec
same = [p for p in pairs if re.search(r"\bCompare (\w[\w+#.-]*) and \1\b", p["spec"] or "")]
print("\nspec compares a thing with ITSELF: %d" % len(same))
for p in same: print("   ", p["job_id"], "|", re.search(r"Compare \w[\w+#.-]* and \w[\w+#.-]* for the task of [^.]*", p["spec"]).group(0)[:80])

# class 3: two different years inside one title
yr = []
for p in pairs:
    y = re.findall(r"\b(19|20)\d{2}\b", p["title"] or "")
    ys = re.findall(r"\b(?:19|20)\d{2}\b", p["title"] or "")
    if len(set(ys)) >= 2: yr.append((p["job_id"], p["title"], ys))
print("\ntitle carries two contradictory years: %d" % len(yr))
for j,t,ys in yr: print("   ", j, "|", t[:72], ys)

# class 4: unrendered template variable
ph = [(p["job_id"], p["title"]) for p in pairs if "{" in (p["title"] or "")+(p["spec"] or "")]
print("\nunrendered {placeholder}: %d  %s" % (len(ph), sorted({t for _,t in ph})))

# class 5: one title, several different specs -> catalog fine, pairing broken
bt = collections.defaultdict(set)
for p in pairs: bt[frozenset(content(p["title"]))].add(head(p["spec"]))
fork = [ (t,s) for t,s in bt.items() if len(s)>1 ]
print("\none title carrying >1 distinct spec: %d titles, %d job instances" % (
    len(fork), sum(1 for p in pairs if len(bt[frozenset(content(p['title']))])>1)))

print("\n--- the sharpest mispairs ---")
for p in mis[:14]:
    print("  %s\n     TITLE: %s\n     SPEC : %s" % (p["job_id"], p["title"][:78], head(p["spec"])[:78]))
json.dump({"judged":len(judged),"mismatch":len(mis),"mismatch_ids":[p["job_id"] for p in mis],
           "self_compare":[p["job_id"] for p in same],"year_clash":[y[0] for y in yr],
           "placeholder":[j for j,_ in ph],"forked_titles":len(fork)},
          open("r30_jobgen_out.json","w"), indent=1)
