# -*- coding: utf-8 -*-
"""Before any coverage arithmetic: do /api/tape and the kibble export number rows
in the SAME space, and does the tape carry every kibble row in its own span?

Two innocent explanations have to die first, because both would make a low
rows/span ratio mean nothing:

  H_global : tape `seq` is a Technocore-wide counter while the export `seq` is
             room-local, so gaps are just other rooms' rows.
  H_mixed  : the tape is a multi-room feed and the kibble rows in it are sparse
             by construction, not by loss.

The test is an anchor join.  Take rows the tape returned, look them up in the
kibble export by (from, nonce) - the signed identity of a row, independent of
any numbering - and compare the seq the two sources give the SAME row.  If the
numbers agree, the spaces are the same and a missing seq is a missing row.
Then count, inside the tape's own span, how many export rows the tape omitted.

Usage: tape_seq_space_check.py <export.jsonl> [saved_tape.json | --live]
"""
import json, sys, os, urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

exp_path = sys.argv[1]
src = sys.argv[2] if len(sys.argv) > 2 else "--live"

export = [json.loads(l) for l in open(exp_path, encoding="utf-8") if l.strip()]
by_ident = {}
for r in export:
    by_ident[(r.get("from"), r.get("nonce"))] = r
exp_seqs = sorted(r["seq"] for r in export if r.get("seq") is not None)
print("export rows %d  seq %d..%d  span %d  coverage %.4f"
      % (len(export), exp_seqs[0], exp_seqs[-1], exp_seqs[-1] - exp_seqs[0] + 1,
         len(exp_seqs) / float(exp_seqs[-1] - exp_seqs[0] + 1)))

if src == "--live":
    with urllib.request.urlopen(
            "https://flop-kibble.onrender.com/api/tape?limit=1500", timeout=240) as r:
        tape = json.loads(r.read().decode())
else:
    tape = json.load(open(src, encoding="utf-8", errors="replace"))
msgs = tape.get("messages", [])
tseqs = [m.get("seq") for m in msgs if m.get("seq") is not None]
print("tape   rows %d  seq %d..%d  span %d  ratio %.4f"
      % (len(msgs), min(tseqs), max(tseqs), max(tseqs) - min(tseqs) + 1,
         len(tseqs) / float(max(tseqs) - min(tseqs) + 1)))

# ---- 1. same numbering space? anchor on (from, nonce) ----
matched = agree = disagree = 0
examples = []
for m in msgs:
    k = (m.get("from"), m.get("nonce"))
    if k[0] is None or k[1] is None:
        continue
    e = by_ident.get(k)
    if e is None:
        continue
    matched += 1
    if e.get("seq") == m.get("seq"):
        agree += 1
    else:
        disagree += 1
        if len(examples) < 5:
            examples.append({"tape_seq": m.get("seq"), "export_seq": e.get("seq")})
print("anchored rows found in both: %d  seq agrees: %d  disagrees: %d" % (matched, agree, disagree))
if examples:
    print("  disagreement examples:", json.dumps(examples))
if matched == 0:
    print("VERDICT: cannot anchor - no row appears in both sources. Coverage arithmetic is VOID.")
    sys.exit(0)
if disagree:
    print("VERDICT: the two sources number the SAME row differently -> different seq spaces.")
    print("         H_global survives. Coverage arithmetic on tape seq is VOID.")
    sys.exit(0)
print("VERDICT: same seq space (every anchored row carries the identical seq).")

# ---- 2. inside the tape's own span, what did the tape omit? ----
lo, hi = min(tseqs), max(tseqs)
exp_in = [r for r in export if r.get("seq") is not None and lo <= r["seq"] <= hi]
tape_seq_set = set(tseqs)
missing = [r for r in exp_in if r["seq"] not in tape_seq_set]
print()
print("inside tape span %d..%d:" % (lo, hi))
print("  export rows in span : %d" % len(exp_in))
print("  tape rows in span   : %d" % len(tseqs))
print("  export rows the tape OMITTED: %d (%.1f%%)"
      % (len(missing), 100.0 * len(missing) / max(1, len(exp_in))))
if missing:
    print("  omitted examples (seq, first 70 chars):")
    for r in missing[:5]:
        print("   ", r["seq"], (r.get("text") or "")[:70].replace("\n", " "))
    print("VERDICT: the tape is a SAMPLE of the kibble room - it drops rows it spans.")
else:
    print("VERDICT: the tape is COMPLETE over its own span. Low rows/span is other rooms' seq.")
