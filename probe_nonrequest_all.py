#!/usr/bin/env python3
"""Same test as probe_nonrequest_jobs.py, run over every archived /api/tape
window (2026-09-03 .. 2026-09-09), deduplicated by tape seq so overlapping
windows cannot double-count.

Claim under test: the board accepts JOBs that make no request - completion
reports posted as work orders - and agents claim, deliver and attest them
anyway. Control = every request-shaped job in the same corpus."""
import json, re, sys, glob, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ALL = {}
files = sorted(glob.glob("useful_on_thin_*.json"))
for f in files:
    try: d = json.load(open(f, encoding="utf-8"))
    except Exception: continue
    for m in d.get("messages", []):
        s = m.get("seq")
        if s is not None: ALL[s] = m
msgs = list(ALL.values())
print("windows %d -> unique tape lines %d (seq %d..%d)"
      % (len(files), len(msgs), min(ALL), max(ALL)))

def did(m): return m.get("did") or m.get("from") or ""
def txt(m): return (m.get("text") or "")

ASK_VERBS = (r"explain|describe|name|list|write|design|compare|provide|give|identify|"
             r"assess|detail|create|evaluate|summari[sz]e|count|build|implement|analy[sz]e|"
             r"read|verify|structure|outline|propose|show|state|derive|review|audit|"
             r"walk through|draft|pick|choose|rank|measure|find|check|document|plan|sketch|"
             r"produce|return|report|explore|investigate|trace|map|enumerate|justify|argue")
ASK = re.compile(r"(?:^|[.!?|]\s*)(?:%s)\b" % ASK_VERBS, re.I)
SUCCESS = re.compile(r"\bsuccess\s*:", re.I)
REPORT = re.compile(r"\b(verification passed|benchmark executed|analysis complete|"
                    r"verified|performed|executed|completed|conducted|confirmed|"
                    r"no anomalies detected|derived|deliverable)\b", re.I)
STAMP = re.compile(r"\[Proof(?:Hash)?:", re.I)

def spec_of(m):
    p = txt(m).split("|")
    return p[-1].strip() if len(p) >= 3 else txt(m)

def is_nonrequest(m):
    s = spec_of(m)
    asks = bool(ASK.search(s)) or bool(SUCCESS.search(s)) or "?" in s
    return (not asks) and (bool(REPORT.search(s)) or bool(STAMP.search(s)))

jobs = {}
for m in msgs:
    if m.get("kind") == "job" and m.get("job_id"): jobs.setdefault(m["job_id"], m)
print("distinct jobs", len(jobs))

claims  = collections.Counter(m.get("job_id") for m in msgs if m.get("kind")=="claim")
results = collections.Counter(m.get("job_id") for m in msgs if m.get("kind")=="result")
useful  = collections.Counter(m.get("job_id") for m in msgs if m.get("kind")=="attest"
                              and str(m.get("verdict","")).lower()=="useful")
notc    = collections.Counter(m.get("job_id") for m in msgs if m.get("kind")=="attest"
                              and str(m.get("verdict","")).lower() not in ("useful",""))

nonreq = {j: m for j, m in jobs.items() if is_nonrequest(m)}
req    = {j: m for j, m in jobs.items() if j not in nonreq}
print("NON-REQUEST %d (%.2f%%) | control %d" % (len(nonreq), 100.0*len(nonreq)/max(1,len(jobs)), len(req)))
print("distinct posters of non-request jobs:", len({did(m) for m in nonreq.values()}))
for d,c in collections.Counter(did(m) for m in nonreq.values()).most_common(8):
    print("   %s  %d" % (d[-14:], c))

def tally(ids, label):
    c=sum(claims[i] for i in ids); r=sum(results[i] for i in ids)
    u=sum(useful[i] for i in ids); n=sum(notc[i] for i in ids)
    ansd=sum(1 for i in ids if results[i]>0)
    print("%-14s jobs %5d | CLAIM %5d (%.2f/job) | RESULT %5d (%.2f/job) | answered %5.1f%% | useful %4d | not %4d | u/(u+n) %s"
          % (label,len(ids),c,c/max(1,len(ids)),r,r/max(1,len(ids)),100.0*ansd/max(1,len(ids)),u,n,
             ("%.0f%%"%(100.0*u/(u+n))) if (u+n) else "n/a"))
print()
tally(list(nonreq), "NON-REQUEST")
tally(list(req),    "CONTROL(ask)")

print("\n-- non-request jobs --")
for j,m in sorted(nonreq.items(), key=lambda kv: -results[kv[0]])[:20]:
    print("  %s poster=%s claims=%d results=%d useful=%d not=%d"
          % (j, did(m)[-14:], claims[j], results[j], useful[j], notc[j]))
    print("     %s" % spec_of(m)[:190].replace("\n"," "))
