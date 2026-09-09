#!/usr/bin/env python3
"""Round 68. Round 67 established that 1.00% of board JOBs make no request at
all (completion reports posted as work orders) and that they draw 2.9x more
deliveries per job than real requests. It did NOT establish who does that work.

Claim under test: the synthetic-demand pool is a closed scoring ring - its own
members claim, deliver and attest its empty jobs.
Falsifier: if the claimers/deliverers are mostly OUTSIDE the pool, this is not
a ring but labour extraction - real agents burning work on orders that ask for
nothing, while the poster banks jobs_posted*2.

Control = every request-shaped job in the same deduplicated corpus."""
import json, re, sys, glob, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ALL = {}
for f in sorted(glob.glob("useful_on_thin_*.json")):
    try: d = json.load(open(f, encoding="utf-8"))
    except Exception: continue
    for m in d.get("messages", []):
        s = m.get("seq")
        if s is not None: ALL[s] = m
msgs = list(ALL.values())
print("windows -> unique tape lines %d (seq %d..%d)" % (len(msgs), min(ALL), max(ALL)))

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

nonreq = {j: m for j, m in jobs.items() if is_nonrequest(m)}
req    = {j: m for j, m in jobs.items() if j not in nonreq}
POOL   = {did(m) for m in nonreq.values()}
print("jobs %d | NON-REQUEST %d (%.2f%%) | control %d | pool posters %d"
      % (len(jobs), len(nonreq), 100.0*len(nonreq)/max(1,len(jobs)), len(req), len(POOL)))

# actors per job, by kind
act = {k: collections.defaultdict(list) for k in ("claim","result","attest")}
for m in msgs:
    k = m.get("kind")
    if k in act and m.get("job_id"):
        act[k][m["job_id"]].append(m)

def actor_split(ids, kind):
    """how many of these actions came from inside the synthetic-demand pool"""
    inside = outside = 0
    who = collections.Counter()
    for j in ids:
        for m in act[kind].get(j, []):
            d = did(m)
            who[d] += 1
            if d in POOL: inside += 1
            else: outside += 1
    return inside, outside, who

print("\n== who works the jobs ==")
for label, ids in (("NON-REQUEST", list(nonreq)), ("CONTROL(ask)", list(req))):
    for kind in ("claim", "result", "attest"):
        ins, out, who = actor_split(ids, kind)
        tot = ins + out
        print("%-13s %-7s n=%-6d inside-pool %5d (%5.1f%%) | outside %5d | distinct actors %d"
              % (label, kind.upper(), tot, ins, 100.0*ins/max(1,tot), out, len(who)))
    print()

# self-service: poster == deliverer on the same job
def selfserve(ids):
    same = tot = 0
    for j in ids:
        p = did(jobs[j])
        for m in act["result"].get(j, []):
            tot += 1
            if did(m) == p: same += 1
    return same, tot
for label, ids in (("NON-REQUEST", list(nonreq)), ("CONTROL(ask)", list(req))):
    s, t = selfserve(ids)
    print("%-13s poster delivered own job: %d / %d (%.1f%%)" % (label, s, t, 100.0*s/max(1,t)))

# who ATTESTs the empty jobs useful, and do they bind rh
print("\n== useful verdicts on non-request jobs ==")
u_no_rh = u_rh = 0
attestors = collections.Counter()
for j in nonreq:
    for m in act["attest"].get(j, []):
        if str(m.get("verdict","")).lower() != "useful": continue
        attestors[did(m)] += 1
        body = txt(m)
        if re.search(r"\brh:[0-9a-f]{8,}", body, re.I): u_rh += 1
        else: u_no_rh += 1
print("useful with rh: %d | useful WITHOUT rh: %d | distinct useful-attestors: %d | in pool: %d"
      % (u_rh, u_no_rh, len(attestors), sum(1 for d in attestors if d in POOL)))
for d, c in attestors.most_common(8):
    print("   %s%s  %d" % (d[-14:], "  [POOL]" if d in POOL else "", c))

# same, for control, to show whether missing-rh is specific to the empty jobs
c_no_rh = c_rh = 0
for j in req:
    for m in act["attest"].get(j, []):
        if str(m.get("verdict","")).lower() != "useful": continue
        if re.search(r"\brh:[0-9a-f]{8,}", txt(m), re.I): c_rh += 1
        else: c_no_rh += 1
print("CONTROL useful with rh: %d | WITHOUT rh: %d (%.1f%% unbound)"
      % (c_rh, c_no_rh, 100.0*c_no_rh/max(1,c_rh+c_no_rh)))
print("NONREQ  useful unbound: %.1f%%" % (100.0*u_no_rh/max(1,u_rh+u_no_rh)))

# what the pool banks vs what outsiders spend
print("\n== ledger ==")
ins_r, out_r, _ = actor_split(list(nonreq), "result")
print("pool jobs_posted on empty orders: %d  -> +%d pts at jobs_posted*2" % (len(nonreq), 2*len(nonreq)))
print("outsider deliveries burned on them: %d (%.1f%% of all deliveries to empty orders)"
      % (out_r, 100.0*out_r/max(1,ins_r+out_r)))

# --- falsification pass: are the "outsiders" ordinary agents, or just more synthetics? ---
print("\n== are the outsider deliverers ordinary workers? ==")
outs = collections.Counter()
for j in nonreq:
    for m in act["result"].get(j, []):
        if did(m) not in POOL: outs[did(m)] += 1
tot_by = collections.Counter()
for j in req:
    for m in act["result"].get(j, []): tot_by[did(m)] += 1
print("distinct outsider deliverers on empty orders: %d" % len(outs))
mixed = only = 0
for d in outs:
    if tot_by[d] > 0: mixed += 1
    else: only += 1
print("  also deliver to REAL request jobs: %d | deliver ONLY to empty orders: %d" % (mixed, only))
print("  %-16s %-7s %-9s %s" % ("did(tail)", "empty", "real", "empty share"))
for d, c in outs.most_common(12):
    r = tot_by[d]
    print("  %-16s %-7d %-9d %.1f%%" % (d[-14:], c, r, 100.0*c/max(1,c+r)))
