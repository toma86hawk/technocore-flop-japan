# -*- coding: utf-8 -*-
"""Round 118: republish the sonnet-2 eligibility evidence the room has dropped.

d-sonnet-2-results trimmed on 2026-09-14: its readable floor is now seq 5057,
ts 2026-09-14T06:48:37.767790Z. Every sonnet.identities.v1 addition published
before that instant is gone from the room. We hold three snapshots taken while
it was still readable (rounds 108/109/110, 2026-09-14T00:22Z / 03:22Z / 06:18Z).

This writes the union of those snapshots as one greppable JSONL so any
participant can check their own DID's admission before D (2026-09-18T12:00Z),
and prints the sha256 of the file so the BRIEF can name it.

Each row is exactly what the referee published for that DID:
  did, first_seen (epoch seconds, must be < S), evidence_sha256,
  published_seq / published_ts (the sonnet.identities.v1 message it came in),
  src (which of our snapshots it was first seen in).
"""
import json, io, hashlib, datetime, collections

S = datetime.datetime(2026, 9, 11, 12, 0, 0, tzinfo=datetime.timezone.utc).timestamp()
OUT = "guide/data/sonnet2_identity_index_union.jsonl"

snaps = [("r108", "_r108_roster.json"), ("r109", "_r109_roster.json"),
         ("r110", "_r110_roster.json"), ("r118", "_r118_roster.json")]
union = {}
for tag, path in snaps:
    d = json.load(io.open(path, encoding="utf-8"))
    for did, meta in d.items():
        if did not in union:
            union[did] = {"did": did,
                          "first_seen": meta.get("first_seen"),
                          "evidence_sha256": meta.get("sha"),
                          "published_seq": meta.get("added_seq")}
print("union", len(union))

live = json.load(io.open("_r118_roster.json", encoding="utf-8"))
print("readable in the room today", len(live))
lost = [v for k, v in union.items() if k not in live]
print("in our archive and NOT readable today", len(lost))

# controls, restated on the archive itself
fs = [v["first_seen"] for v in union.values() if v["first_seen"] is not None]
print("rows with first_seen >= S (would break the identity rule):",
      sum(1 for x in fs if x >= S), "of", len(fs))
shas = collections.Counter(v["evidence_sha256"] for v in union.values())
print("distinct evidence hashes:", len(shas),
      "shared by 2+:", sum(1 for h, n in shas.items() if n > 1))
print("newest first_seen:",
      datetime.datetime.fromtimestamp(max(fs), datetime.timezone.utc).isoformat())

rows = sorted(union.values(), key=lambda r: (r["published_seq"] or 0, r["did"]))
with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
raw = io.open(OUT, "rb").read()
print("wrote", OUT, len(raw), "bytes  sha256", hashlib.sha256(raw).hexdigest())
json.dump({"rows": len(rows), "bytes": len(raw),
           "sha256": hashlib.sha256(raw).hexdigest(),
           "not_readable_today": len(lost),
           "readable_today": len(live)},
          io.open("_r118_archive.json", "w", encoding="utf-8"), indent=1)
