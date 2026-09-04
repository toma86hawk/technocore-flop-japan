#!/usr/bin/env python3
"""r30: two measurements over the archived /api/board attest snapshots.

(A) SPLICE CHAIN. The host generator pairs a title from one catalog entry with
    a Success-spec from a different one. Test: when title and spec disagree,
    does the spec's instruction turn up as the TITLE of another live job? If
    yes the two cursors are running out of step and the fault is the pairing,
    not the catalog.

(B) RESIDUE CLUSTERING. result_hash fingerprints the whole body, so a worker
    that echoes the job's own title and spec before appending a canned tail
    lands a DIFFERENT rh on every job and walks straight past rh clustering.
    Fix: delete the sentences the job itself supplied, then hash what is left.
    The residue is the only text the worker actually wrote.
"""
import json, re, io, glob, collections, hashlib

STOP = {"explain", "how", "why", "works", "work", "a", "an", "the", "of", "in",
        "is", "are", "to", "and", "for", "on", "vs", "versus", "what", "when",
        "give", "list", "define", "review", "compare", "measure", "with", "its"}

def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()

def content(s):
    return set(norm(s).split()) - STOP

def head(spec):
    return re.split(r"\bSuccess\s*:", spec or "")[0].strip().rstrip(".").strip()

pairs, seen = [], set()
for f in sorted(glob.glob("attest_runs/2026-09-0*.json")):
    d = json.load(io.open(f, encoding="utf-8"))
    for q in d.get("queue") or []:
        k = (q["job_id"], q.get("rh"))
        if k not in seen:
            seen.add(k)
            pairs.append(q)
print("snapshots:", len(glob.glob('attest_runs/2026-09-0*.json')), " distinct job/result pairs:", len(pairs))

# ---------- (A) ----------
title_index = collections.defaultdict(list)
for p in pairs:
    c = frozenset(content(p["title"]))
    if c:
        title_index[c].append(p["job_id"])

mismatch, chain, placeholder = [], [], []
for p in pairs:
    t, sp = p["title"], p["spec"]
    if "{" in t or "{" in sp:
        placeholder.append((p["job_id"], t))
    tw, hw = content(t), content(head(sp))
    if not tw or not hw:
        continue
    if not (tw & hw):
        mismatch.append((p["job_id"], t, head(sp)))
        fh = frozenset(hw)
        if fh in title_index:
            chain.append((p["job_id"], t, head(sp), title_index[fh]))

print("\n(A) title/spec subject disagreement: %d / %d = %.1f%%" %
      (len(mismatch), len(pairs), 100.0*len(mismatch)/len(pairs)))
for jid, t, h in mismatch:
    print("   ", jid, "| T:", t[:60], "|| S:", h[:60])
print("\n  CHAIN: that spec's instruction is the TITLE of another live job -- %d of %d mismatches"
      % (len(chain), len(mismatch)))
for c in chain:
    print("    %s  T: %-46s  S == title of %s" % (c[0], c[1][:46], c[3]))
print("\n  unsubstituted {placeholder} left in job text: %d" % len(placeholder))
for jid, t in placeholder:
    print("   ", jid, t[:70])

# same title, two different specs -> proves the catalog entry is fine, the pairing is not
by_title = collections.defaultdict(set)
for p in pairs:
    by_title[frozenset(content(p["title"]))].add(head(p["spec"]))
forked = {t: s for t, s in by_title.items() if len(s) > 1}
print("\n  one title carrying >1 distinct spec: %d" % len(forked))
for t, s in list(forked.items())[:6]:
    print("    title=%s" % " ".join(sorted(t))[:50])
    for x in list(s)[:3]:
        print("       spec: %s" % x[:70])

# ---------- (B) ----------
def residue(body, title, spec):
    """Drop every sentence the job itself supplied."""
    job = content(title) | content(spec)
    out = []
    for sent in re.split(r"(?<=[.!?])\s+|\s*\|\s*", body):
        w = content(sent)
        if not w:
            continue
        # a sentence that is >=70% job-supplied vocabulary is an echo, not authorship
        if len(w & job) / len(w) >= 0.70:
            continue
        out.append(" ".join(sorted(w)))
    return " ".join(out)

rh_c, res_c = collections.Counter(), collections.Counter()
rows = []
for p in pairs:
    res = residue(p["result"], p["title"], p["spec"])
    rid = hashlib.sha256(res.encode()).hexdigest()[:12]
    rh_c[p["rh"]] += 1
    res_c[rid] += 1
    rows.append((p["job_id"], p["worker"], p["rh"], rid, res))

n = len(rows)
rh_dupe = sum(v for v in rh_c.values() if v > 1)
res_dupe = sum(v for v in res_c.values() if v > 1)
hidden = [r for r in rows if rh_c[r[2]] == 1 and res_c[r[3]] > 1]
print("\n(B) deliveries: %d" % n)
print("   distinct result_hash : %3d -> %d (%.1f%%) sit in a repeated cluster" % (len(rh_c), rh_dupe, 100.0*rh_dupe/n))
print("   distinct RESIDUE     : %3d -> %d (%.1f%%) sit in a repeated cluster" % (len(res_c), res_dupe, 100.0*res_dupe/n))
print("   *** rh calls unique, residue calls canned: %d deliveries (%.1f%%) ***" % (len(hidden), 100.0*len(hidden)/n))

print("\n   top residues:")
for rid, k in res_c.most_common(10):
    if k < 2:
        break
    ex = [r for r in rows if r[3] == rid]
    ws = collections.Counter(r[1] for r in ex)
    print("    x%-3d %s  rh distinct=%-3d workers=%d %s" % (
        k, rid, len({r[2] for r in ex}), len(ws), ["..."+w[-14:] for w in ws]))
    print("        %s" % (ex[0][4][:150] or "(empty: body is 100%% job-supplied text)"))
    print("        jobs: %s" % ", ".join(r[0] for r in ex[:8]))

print("\n   per-worker (>=3 deliveries):")
for w, c in sorted(collections.Counter(r[1] for r in rows).items(), key=lambda kv: -kv[1]):
    if c < 3:
        continue
    mine = [r for r in rows if r[1] == w]
    print("    ...%s deliveries=%-3d distinct rh=%-3d distinct residue=%-3d" % (
        w[-14:], c, len({r[2] for r in mine}), len({r[3] for r in mine})))

json.dump({"pairs": n, "mismatch": mismatch, "chain": chain, "placeholder": placeholder,
           "rh_distinct": len(rh_c), "res_distinct": len(res_c),
           "rh_dupe": rh_dupe, "res_dupe": res_dupe,
           "hidden_by_rh": [(r[0], r[1], r[2], r[3]) for r in hidden]},
          open("r30_splice_out.json", "w"), indent=1)
