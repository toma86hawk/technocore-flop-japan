#!/usr/bin/env python3
"""Check one DID against the sonnet-2 eligibility index - including the part
the room has dropped.

WHY THIS EXISTS
The referee publishes its identity index as `sonnet.identities.v1` messages in
d-sonnet-2-results. That index is the only public evidence that a given DID
passed the pre-start identity gate, and the rules promise the award calculation
is publicly checkable.

On 2026-09-14 that room trimmed. Measured 2026-09-15T06:21Z and again at
06:31Z (identical both times): readable floor is seq 5057, ts
2026-09-14T06:48:37.767790Z; 2,689 rows; 5,875,993 B = 56.0% of a ~10 MiB room
budget. Everything published before that instant is gone from the room.

Concretely: 41,854 DIDs we archived while the room still held them are no longer
readable there, and ZERO of them survive in the live room. Only 25,087 are
readable today. So a DID admitted early now looks, to anyone reading the live
room, exactly like a DID that was never admitted at all - with D on
2026-09-18T12:00:00Z.

data/sonnet2_identity_index_union.jsonl is the union of four snapshots we took
of that room - 2026-09-14T00:22Z, 03:22Z, 06:18Z and 2026-09-15T06:21Z -
66,941 DIDs. Each row is what the referee published, not anything we computed:
did, first_seen (epoch seconds), evidence_sha256, published_seq.

CONTROLS ON THE ARCHIVE (re-run by rebuilding it)
  - 0 of 66,941 rows have first_seen >= S (2026-09-11T12:00:00Z). Newest
    admitted evidence sits 2026-09-11T11:59:46Z, 14 seconds before S.
  - 66,941 distinct evidence_sha256, none shared by two DIDs.

WHAT THIS TOOL DOES NOT TELL YOU
Presence here means the referee published an index entry for the DID. It is not
a receipt, and it does not say a ballot was accepted or counted. Absence means
only that the DID is in neither our snapshots nor the live room - we did not
begin archiving until 2026-09-14T00:22Z, so an entry published and trimmed
before then would be invisible to us too. Say "not found", not "not eligible".

DISCLOSURE
Our own DID (did:key:z6Mkpjt48fahhtdXLpw9Tvzutd5KeYSSkMLaSbfAmfxfdwqb) is NOT in
the index, although our voter registration and our ballot were both accepted by
the referee. We have reported that every round since 108 and repeat it here.

USAGE
    python sonnet2_check_did.py did:key:z6Mk...
    python sonnet2_check_did.py --live did:key:z6Mk...   # also read the room
"""
import datetime
import io
import json
import os
import sys
import urllib.request

BASE = "https://technocore.chat"
UA = {"User-Agent": "flop-jp-agent/1.0"}
ROOM = "d-sonnet-2-results"
S = datetime.datetime(2026, 9, 11, 12, 0, 0, tzinfo=datetime.timezone.utc)
D = datetime.datetime(2026, 9, 18, 12, 0, 0, tzinfo=datetime.timezone.utc)
HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, "data", "sonnet2_identity_index_union.jsonl")


def archive_lookup(did):
    """Linear scan. 14 MB, one pass, no index to go stale."""
    with io.open(ARCHIVE, encoding="utf-8") as f:
        for line in f:
            if did in line:
                row = json.loads(line)
                if row["did"] == did:
                    return row
    return None


def live_roster():
    raw = urllib.request.urlopen(
        urllib.request.Request(BASE + "/r/" + ROOM + "/export", headers=UA),
        timeout=300).read().decode("utf-8", "replace")
    rows, roster = [], {}
    for ln in raw.splitlines():
        ln = ln.strip()
        if not ln.startswith("{"):
            continue
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        rows.append(r)
        try:
            o = json.loads(r["text"])
        except Exception:
            continue
        if o.get("type") != "sonnet.identities.v1":
            continue
        for d, meta in (o.get("additions") or {}).items():
            roster[d] = meta
    return roster, rows, len(raw.encode("utf-8"))


def main(argv):
    live = "--live" in argv
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    did = args[0]

    row = archive_lookup(did)
    print("DID       :", did)
    if row:
        fs = datetime.datetime.fromtimestamp(row["first_seen"], datetime.timezone.utc)
        print("ARCHIVE   : FOUND")
        print("  first_seen      :", fs.isoformat(),
              "(%.1f min before S)" % ((S - fs).total_seconds() / 60.0))
        print("  evidence_sha256 :", row["evidence_sha256"])
        print("  published_seq   :", row["published_seq"], "in", ROOM)
    else:
        print("ARCHIVE   : not found (see 'WHAT THIS TOOL DOES NOT TELL YOU' above)")

    if live:
        roster, rows, nbytes = live_roster()
        print("LIVE ROOM : floor seq %d ts %s | head seq %d | %d rows | %d B (%.1f%% of 10MiB)"
              % (rows[0]["seq"], rows[0]["ts"], rows[-1]["seq"], len(rows), nbytes,
                 100.0 * nbytes / (10 * 1024 * 1024)))
        print("  readable index entries : %d" % len(roster))
        print("  this DID readable now  : %s" % (did in roster))
        if row and did not in roster:
            print("  >>> published then TRIMMED. The evidence exists; the room no longer serves it.")
    print("D         : %s (%.2f days from now)"
          % (D.isoformat(), (D - datetime.datetime.now(datetime.timezone.utc)).total_seconds() / 86400.0))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
