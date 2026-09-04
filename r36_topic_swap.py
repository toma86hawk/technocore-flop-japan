#!/usr/bin/env python3
"""Pattern 56 candidate: TOPIC SUBSTITUTION - a delivery that is long, specific and
factually correct, but about a different question than the one it was posted against.

Why it matters: every detector in the catalogue so far keys on the body being POOR -
thin, templated, a title echo, a spec re-quote, a reviewer-hint echo. A body that is
dense and true defeats all of them. Two of the fifteen deliveries read by hand this
round were exactly that: a correct RFC 9000 paragraph filed against a job asking about
TCP head-of-line blocking and UDP firewalls, and a correct strict-vs-ZIP-215 Ed25519
paragraph filed against a job asking for PageRank clustering over 12000 DIDs.

Measurement, over the 2554 (job, delivery) pairs collected off the room export:
  coverage  = share of the spec's content words that appear anywhere in the body
  density   = count of specific tokens in the body (numbers with units, RFC/section
              numbers, identifiers with _ or (), hex, CamelCase) that are NOT in the spec
  templated = body matches one of the known fixed wrappers
A pair is a topic-substitution candidate when coverage is low, density is high and the
body is not templated. The hand-labelled 15 from this round are used as a check set.
"""
import json, re, collections, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

STOP=set("""a an the and or of to in for on with by from as at is are be that this those these
it its into over under how what why which when where who whom while than then so if not no
one two three all any each both same such only own other more most some can could should would
may might must will shall do does did done have has had using use used via across between
success explain describe detail evaluate assess examine produce provide emit list derive
verify analyze analyse compute construct execute plan ensure name names naming text summary
result results job agent node data value values case cases you your we our they their he she""".split())
WORD=re.compile(r"[A-Za-z][A-Za-z0-9_\-\.]{2,}")
SPEC_TOKEN=re.compile(r"(?:\d+(?:\.\d+)?\s*(?:us|ms|ns|s|kb|mb|gb|bit|bits|byte|bytes|%)"
                      r"|RFC\s?\d+|\b\d{3,}\b|[A-Za-z_][A-Za-z0-9_]*\(\)|[A-Za-z]+_[A-Za-z_]+"
                      r"|0x[0-9a-fA-F]+|\b[A-Z]{2,}[a-z0-9]+[A-Z][A-Za-z0-9]*\b|\b[A-Z]{3,}\b)")
WRAPPERS=[
 "Conducted rigorous domain evaluation",
 "Execution invariants and semantic constraints verified",
 "Results are deterministic and reproducible across nodes",
 "[AI-RESEARCH]",
 "Technical analysis matching job requirements delivered",
 "Coordination completed. Success criteria mapped",
 "Verified solution via GLM",
 "Auto-delivered by VPS agent",
]

def words(s): return {w.lower() for w in WORD.findall(s or "") if w.lower() not in STOP}

q=json.load(open("attest_queue_offboard.json",encoding="utf-8"))
rows=[]
for x in q:
    body=(x.get("result") or "")
    spec=(x.get("spec") or "")+" "+(x.get("title") or "")
    sw=words(spec)
    if len(sw)<6 or len(body)<300: continue
    bw=words(body)
    cov=len(sw&bw)/len(sw)
    stoks={t.lower() for t in SPEC_TOKEN.findall(spec)}
    btoks={t.lower() for t in SPEC_TOKEN.findall(body)}
    dens=len(btoks-stoks)
    tmpl=any(w.lower() in body.lower() for w in WRAPPERS)
    rows.append(dict(job=x["job_id"],worker=x["worker"],cov=round(cov,3),dens=dens,
                     tmpl=tmpl,blen=len(body),cat=x.get("category")))

print("pairs scored:",len(rows))
cands=[r for r in rows if r["cov"]<0.25 and r["dens"]>=8 and not r["tmpl"]]
print("topic-substitution candidates (cov<0.25, dens>=8, not templated):",
      len(cands), "= %.1f%% of scored"%(100*len(cands)/len(rows)))
w=collections.Counter(r["worker"] for r in cands)
print("distinct workers:",len(w),"top:",[(k[-12:],v) for k,v in w.most_common(6)])
print("category mix:",collections.Counter(r["cat"] for r in cands).most_common())

# check set: this round's hand labels
lab={j:v for j,v,_ in [(p[0],p[1],None) for p in json.load(open("r36_attest_posted.json",encoding="utf-8"))]}
idx={r["job"]:r for r in rows}
print("\ncheck set (this round's hand-read 15):")
for j,v in lab.items():
    r=idx.get(j)
    print("  %s %-6s cov=%s dens=%s tmpl=%s len=%s"%(j,v,r["cov"] if r else "-",
          r["dens"] if r else "-", r["tmpl"] if r else "-", r["blen"] if r else "-"))

# templated-wrapper census, for the same corpus
tm=[r for r in rows if r["tmpl"]]
tw=collections.Counter(r["worker"] for r in tm)
print("\ntemplated bodies: %d (%.1f%%) across %d distinct DIDs; top %s"%(
    len(tm),100*len(tm)/len(rows),len(tw),[(k[-12:],v) for k,v in tw.most_common(5)]))
json.dump({"rows":rows,"cands":cands},open("r36_topic_swap.json","w"))

# ---- second pass: the check set says cov<=0.062 for confirmed substitution and
# >=0.37 for confirmed real work, so retune and report the distribution.
import statistics
rows2=rows
tm=[r for r in rows2 if r["tmpl"]]; nt=[r for r in rows2 if not r["tmpl"]]
print("\n--- coverage distribution ---")
for lbl,g in (("templated",tm),("non-templated",nt)):
    c=sorted(r["cov"] for r in g)
    print("%-14s n=%4d median=%.3f mean=%.3f p10=%.3f p90=%.3f"%(
        lbl,len(c),statistics.median(c),statistics.mean(c),c[int(.1*len(c))],c[int(.9*len(c))]))
low=[r for r in rows2 if r["cov"]<0.15]
print("\ncov<0.15 bodies:",len(low),"of",len(rows2),"(%.1f%%)"%(100*len(low)/len(rows2)))
sub=[r for r in low if not r["tmpl"] and r["dens"]>=3]
print("  of those, non-templated with dens>=3 (topic-substitution candidates):",len(sub))
ws=collections.Counter(r["worker"] for r in sub)
print("  distinct workers:",len(ws))
for k,v in ws.most_common(10): print("   ",k[-12:],v)
print("  categories:",collections.Counter(r["cat"] for r in sub).most_common())
print("  jobs:",[r["job"] for r in sub][:40])
json.dump(sub,open("r36_topic_swap_cands.json","w"),indent=1)
