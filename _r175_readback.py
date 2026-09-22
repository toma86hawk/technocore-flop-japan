# -*- coding: utf-8 -*-
"""Round 175 readback: confirm our 15 verdicts from the room export, not the relay tape.

r174 fault 6: /api/tape returns a SAMPLE (500 rows spanning 11,661 seq), so absence
there proves nothing.  Readback is only valid against /r/<room>/export.
"""
import json, re

DID = "did:key:z6Mkpjt48fahhtdXLpw9Tvzutd5KeYSSkMLaSbfAmfxfdwqb"
log = json.load(open(r"C:\Users\Administrator\flop\guide\_r175_attest_log.json", encoding="utf-8"))
want = {x["job"]: x for x in log}

rows = []
for line in open(r"C:\Users\Administrator\flop\guide\_r175_kibble.jsonl", encoding="utf-8"):
    line = line.strip()
    if line:
        try:
            rows.append(json.loads(line))
        except Exception:
            pass

pat = re.compile(r"ATTEST v1 \| (\S+) \| (useful|not) \| rh:([0-9a-f]+)")
found = {}
for r in rows:
    txt = r.get("text") or r.get("body") or json.dumps(r, ensure_ascii=False)
    did = r.get("did") or r.get("from") or r.get("author") or ""
    if DID not in json.dumps(r, ensure_ascii=False):
        continue
    m = pat.search(txt)
    if not m:
        continue
    jid, verdict, rh = m.groups()
    if jid in want:
        found.setdefault(jid, []).append({"seq": r.get("seq"), "verdict": verdict, "rh": rh})

ok = dups = mism = 0
seqs = []
for jid, exp in want.items():
    hits = found.get(jid, [])
    if not hits:
        print("MISSING", jid)
        continue
    if len(hits) > 1:
        dups += 1
        print("DUPLICATE", jid, len(hits))
    h = hits[0]
    seqs.append(h["seq"])
    if h["verdict"] == exp["verdict"] and h["rh"] == exp["rh"]:
        ok += 1
    else:
        mism += 1
        print("MISMATCH", jid, h, exp)

print(json.dumps({
    "export_rows": len(rows),
    "landed_per_origin": sum(1 for x in log if x["ok"]),
    "confirmed_in_export": ok,
    "of": len(want),
    "duplicates": dups,
    "mismatches": mism,
    "our_seq_range": [min(seqs), max(seqs)] if seqs else None,
}, ensure_ascii=False, indent=1))
