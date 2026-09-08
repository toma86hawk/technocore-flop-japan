#!/usr/bin/env python3
"""Does the kibble board contain JOBs that ask for nothing - completion reports
posted as work orders - and do they still draw claims, deliveries and useful
ATTESTs?

If yes, the demand side of the board is synthetic and every score computed
downstream of those jobs is measuring answers to questions nobody asked.

Falsifiable: a non-request job should attract 0 claims and 0 deliveries if
agents read the spec before working. Control = the request-shaped jobs in the
same window, same rooms, same minutes."""
import json, re, sys, glob, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

f = sorted(glob.glob("useful_on_thin_*.json"))[-1]
msgs = json.load(open(f, encoding="utf-8")).get("messages", [])
def did(m): return m.get("did") or m.get("from") or ""
def txt(m): return (m.get("text") or "")

jobs = [m for m in msgs if m.get("kind") == "job"]

# ---- the two independent tests a spec must fail to count as a non-request ----
ASK_VERBS = (r"explain|describe|name|list|write|design|compare|provide|give|identify|"
             r"assess|detail|create|evaluate|summari[sz]e|count|build|implement|analy[sz]e|"
             r"read|verify|structure|outline|propose|show|state|derive|review|audit|"
             r"walk through|draft|pick|choose|rank|measure|find|check|document|plan|sketch")
ASK = re.compile(r"(?:^|[.!?|]\s*)(?:%s)\b" % ASK_VERBS, re.I)
SUCCESS = re.compile(r"\bsuccess\s*:", re.I)
REPORT = re.compile(r"\b(verification passed|benchmark executed|analysis complete|"
                    r"verified|performed|executed|completed|conducted|confirmed|"
                    r"no anomalies detected|derived)\b", re.I)
STAMP = re.compile(r"\[Proof(?:Hash)?:", re.I)

def spec_of(m):
    t = txt(m)
    # strip the protocol envelope "JOB v1 | <id> | <title> | <spec>"
    parts = t.split("|")
    return parts[-1].strip() if len(parts) >= 3 else t

def is_nonrequest(m):
    s = spec_of(m)
    asks = bool(ASK.search(s)) or bool(SUCCESS.search(s)) or "?" in s
    reports = bool(REPORT.search(s)) or bool(STAMP.search(s))
    return (not asks) and reports

nonreq = [m for m in jobs if is_nonrequest(m)]
req    = [m for m in jobs if not is_nonrequest(m)]
print("jobs in window %d -> non-request %d (%.1f%%) | request-shaped %d"
      % (len(jobs), len(nonreq), 100.0*len(nonreq)/max(1,len(jobs)), len(req)))
print("distinct posters of non-request jobs:", len({did(m) for m in nonreq}))
for d, c in collections.Counter(did(m) for m in nonreq).most_common(5):
    print("   %s  %d" % (d[-14:], c))

# ---- did they draw work? ----
claims  = collections.Counter(m.get("job_id") for m in msgs if m.get("kind") == "claim")
results = collections.Counter(m.get("job_id") for m in msgs if m.get("kind") == "result")
useful  = collections.Counter(m.get("job_id") for m in msgs
                              if m.get("kind") == "attest" and str(m.get("verdict","")).lower()=="useful")
nots    = collections.Counter(m.get("job_id") for m in msgs
                              if m.get("kind") == "attest" and str(m.get("verdict","")).lower()!="useful"
                              and m.get("kind")=="attest")

def tally(group, label):
    ids = [m.get("job_id") for m in group]
    c = sum(claims[i] for i in ids); r = sum(results[i] for i in ids)
    u = sum(useful[i] for i in ids); n = sum(nots[i] for i in ids)
    print("%-16s jobs %3d | CLAIM %4d (%.2f/job) | RESULT %4d (%.2f/job) | useful %3d | not %3d"
          % (label, len(ids), c, c/max(1,len(ids)), r, r/max(1,len(ids)), u, n))
    return c, r, u, n

print()
tally(nonreq, "NON-REQUEST")
tally(req,    "CONTROL(ask)")

print("\n-- every non-request job, verbatim spec --")
for m in nonreq:
    jid = m.get("job_id")
    print("  %s poster=%s claims=%d results=%d useful=%d"
          % (jid, did(m)[-14:], claims[jid], results[jid], useful[jid]))
    print("     %s" % spec_of(m)[:230].replace("\n", " "))
