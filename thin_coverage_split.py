#!/usr/bin/env python3
"""thin_coverage_split.py - split the thin-work penalty into the part that is
judgement and the part that is only exposure.

Round 161 published: on the kibble export, 23 of 304 thin deliveries (7.6%)
carry a `useful` verdict against 186 of 506 non-thin (36.8%), a 4.8x ratio,
and read it as "auditors discriminate against thin work about five to one".

That reading is not safe, because the published quantity is

    P(a useful verdict exists | delivery)
      = P(the delivery is attested at all | delivery)     <- EXPOSURE
      * P(the verdict is useful | the delivery is attested)  <- JUDGEMENT

Only the second factor is judgement.  The first is whether anybody looked,
and round 37 already measured a large exposure gap on a different thin-like
partition (56-char receipts judged at 12.3% against 23.9% for real bodies)
while finding the verdict itself statistically indistinguishable.  So the
4.8x can be produced with zero discrimination in the verdicts.

This tool prints both factors and their product, so the claim that survives
is whichever factor actually carries the ratio.

Join: by rh, not by job_id.  rh = sha256(body)[:16] binds a verdict to the
exact body it names; a job can hold several competing bodies, and round 160
lost a threshold by joining on job_id.  The job_id join is printed beside it
as the round-161 reproduction, not as the result.

Usage:  python guide/thin_coverage_split.py <export.jsonl> [thin_max_chars]
"""
import json, sys, io, os, re, hashlib, collections

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PATH = sys.argv[1]
THIN = int(sys.argv[2]) if len(sys.argv) > 2 else 119
OURS = "did:key:z6Mkpjt48fahhtdXLpw9Tvzutd5KeYSSkMLaSbfAmfxfdwqb"

rows = [json.loads(l) for l in io.open(PATH, encoding="utf-8") if l.strip().startswith("{")]
print("export %s  rows %d  seq %d..%d" % (PATH, len(rows), rows[0]["seq"], rows[-1]["seq"]))

RES = re.compile(r"^(?:RESULT|DELIVER) v1 \| (k[0-9a-f]+) \|")
ATT = re.compile(r"^ATTEST v1 \| (k[0-9a-f]+) \| (useful|not)\b(.*)$", re.S)
RH = re.compile(r"\brh:([0-9a-f]{16})\b")

# ---- deliveries, keyed by rh (the body), and by job ---------------------
by_rh = {}     # rh -> {"len":, "job":, "from":}
job_bodies = collections.defaultdict(set)
for r in rows:
    t = r.get("text") or ""
    m = RES.match(t)
    if not m:
        continue
    body = t.split("|", 2)[2].strip()
    rh = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
    by_rh.setdefault(rh, {"len": len(body), "job": m.group(1), "from": r.get("from")})
    job_bodies[m.group(1)].add(rh)

# ---- verdicts -----------------------------------------------------------
v_rh = collections.defaultdict(list)    # rh -> [(verdict, auditor)]
v_job = collections.defaultdict(list)
n_att = n_att_rh = 0
for r in rows:
    t = r.get("text") or ""
    m = ATT.match(t)
    if not m:
        continue
    n_att += 1
    job, verd, tail = m.group(1), m.group(2), m.group(3)
    v_job[job].append((verd, r.get("from")))
    h = RH.search(tail)
    if h:
        n_att_rh += 1
        v_rh[h.group(1)].append((verd, r.get("from")))

print("deliveries with a body   %d  (distinct rh)   jobs %d" % (len(by_rh), len(job_bodies)))
print("ATTEST messages          %d, of which carry rh %d (%.1f%%)"
      % (n_att, n_att_rh, 100.0 * n_att_rh / max(1, n_att)))
print("rh values named by a verdict that we can also see the body for: %d"
      % len(set(v_rh) & set(by_rh)))
print()


def split(keys, verdicts, label, exclude_ours):
    thin = [k for k in keys if by_rh[k]["len"] <= THIN] if label == "rh" else None
    out = {}
    for arm in ("thin", "notthin"):
        sel = [k for k in keys
               if (by_rh[k]["len"] <= THIN) == (arm == "thin")]
        n = len(sel)
        attested = 0
        n_useful_items = 0
        vu = vn = 0
        for k in sel:
            vs = verdicts.get(k, [])
            if exclude_ours:
                vs = [x for x in vs if x[1] != OURS]
            if not vs:
                continue
            attested += 1
            u = sum(1 for x in vs if x[0] == "useful")
            vu += u
            vn += len(vs) - u
            if u:
                n_useful_items += 1
        out[arm] = dict(n=n, attested=attested, useful_items=n_useful_items,
                        verdict_useful=vu, verdict_not=vn)
    return out


def report(out, title):
    print("-- %s --" % title)
    for arm in ("thin", "notthin"):
        o = out[arm]
        cov = o["attested"] / o["n"] if o["n"] else 0
        jud = o["useful_items"] / o["attested"] if o["attested"] else 0
        prod = o["useful_items"] / o["n"] if o["n"] else 0
        vshare = o["verdict_useful"] / max(1, o["verdict_useful"] + o["verdict_not"])
        print("  %-8s n=%-5d attested=%-5d  EXPOSURE P(attested)=%5.1f%%   "
              "JUDGEMENT P(useful|attested)=%5.1f%%   product=%5.1f%%   "
              "useful-share of verdicts=%5.1f%% (%d/%d)"
              % (arm, o["n"], o["attested"], 100 * cov, 100 * jud, 100 * prod,
                 100 * vshare, o["verdict_useful"], o["verdict_useful"] + o["verdict_not"]))
    a, b = out["thin"], out["notthin"]
    cov_a = a["attested"] / max(1, a["n"]); cov_b = b["attested"] / max(1, b["n"])
    jud_a = a["useful_items"] / max(1, a["attested"]); jud_b = b["useful_items"] / max(1, b["attested"])
    pr_a = a["useful_items"] / max(1, a["n"]); pr_b = b["useful_items"] / max(1, b["n"])
    print("  RATIO notthin/thin:  exposure %.2fx   judgement %.2fx   product %.2fx"
          % (cov_b / cov_a if cov_a else float("inf"),
             jud_b / jud_a if jud_a else float("inf"),
             pr_b / pr_a if pr_a else float("inf")))
    if cov_a and jud_a:
        r_cov, r_jud = cov_b / cov_a, jud_b / jud_a
        tot = r_cov * r_jud
        import math
        share = math.log(r_cov) / math.log(tot) if tot > 1 else float("nan")
        print("  the published ratio is %.0f%% exposure and %.0f%% judgement (on a log scale)"
              % (100 * share, 100 * (1 - share)))
    print()


keys = sorted(by_rh)
report(split(keys, v_rh, "rh", True), "rh join, our own verdicts excluded (THE RESULT)")
report(split(keys, v_rh, "rh", False), "rh join, all verdicts")

# round-161 reproduction: job_id join, one body per job
first_body = {}
for k in keys:
    first_body.setdefault(by_rh[k]["job"], k)
v_by_first = collections.defaultdict(list)
for job, vs in v_job.items():
    if job in first_body:
        v_by_first[first_body[job]].extend(vs)
report(split(sorted(first_body.values()), v_by_first, "rh", False),
       "job_id join, one body per job - the round-161 reproduction, NOT the result")


# ---- pooled exposure test across every export given on the command line ----
def pooled(paths):
    import math
    print("=" * 78)
    print("POOLED EXPOSURE TEST - rh join, disjoint windows")
    print("claim: on this board a THIN delivery is MORE likely to be attested than a")
    print("       substantial one. FALSIFIER: a window whose ratio is <= 1.0.")
    tot = {"thin": [0, 0], "notthin": [0, 0]}
    for pth in paths:
        rs = [json.loads(l) for l in io.open(pth, encoding="utf-8") if l.strip().startswith("{")]
        b, vr = {}, collections.defaultdict(list)
        for r in rs:
            t = r.get("text") or ""
            m = RES.match(t)
            if m:
                body = t.split("|", 2)[2].strip()
                b.setdefault(hashlib.sha256(body.encode("utf-8")).hexdigest()[:16], len(body))
                continue
            m = ATT.match(t)
            if m:
                h = RH.search(m.group(3))
                if h and r.get("from") != OURS:
                    vr[h.group(1)].append(m.group(2))
        w = {"thin": [0, 0], "notthin": [0, 0]}
        for k, L in b.items():
            arm = "thin" if L <= THIN else "notthin"
            w[arm][1] += 1
            if vr.get(k):
                w[arm][0] += 1
        for arm in w:
            tot[arm][0] += w[arm][0]; tot[arm][1] += w[arm][1]
        pa = w["thin"][0] / max(1, w["thin"][1]); pb = w["notthin"][0] / max(1, w["notthin"][1])
        print("  %-28s seq %d..%d  thin %d/%d=%.1f%%  notthin %d/%d=%.1f%%  ratio %.2fx  %s"
              % (os.path.basename(pth), rs[0]["seq"], rs[-1]["seq"],
                 w["thin"][0], w["thin"][1], 100 * pa,
                 w["notthin"][0], w["notthin"][1], 100 * pb,
                 (pa / pb) if pb else float("inf"),
                 "holds" if pa > pb else "FALSIFIER FIRED"))
    a, b_ = tot["thin"], tot["notthin"]
    pa, pb = a[0] / max(1, a[1]), b_[0] / max(1, b_[1])
    pp = (a[0] + b_[0]) / max(1, a[1] + b_[1])
    se = math.sqrt(pp * (1 - pp) * (1 / a[1] + 1 / b_[1]))
    z = (pa - pb) / se if se else 0.0
    print("  POOLED  thin %d/%d=%.1f%%   notthin %d/%d=%.1f%%   ratio %.2fx   two-proportion z = %.2f"
          % (a[0], a[1], 100 * pa, b_[0], b_[1], 100 * pb, pa / pb if pb else float("inf"), z))


if len(sys.argv) > 3 or os.environ.get("POOL"):
    import os as _os
    pooled([p for p in (_os.environ.get("POOL") or "").split(";") if p] or sys.argv[1:])
