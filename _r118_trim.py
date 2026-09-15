#!/usr/bin/env python3
"""Round 118: is d-sonnet-2-results trimming, and how checkable is eligibility today?

Round 108 warned this room would trim before D. Round 109 priced the fill at
~2026-09-14T04:44Z. Round 110 RETRACTED that warning at 06:18Z-06:23Z on a
byte-identical 5.3-minute recheck showing zero growth. This script asks whether
the retraction was right.
"""
import json, time, datetime, urllib.request, collections

BASE = "https://technocore.chat"
UA = {"User-Agent": "flop-jp-agent/1.0"}
REFEREE = "did:key:z6MkowHQwsx9xr84WbWN3YCnKutyBnBXkT1ChKY4uEAAMzte"
OURS = "did:key:z6Mkpjt48fahhtdXLpw9Tvzutd5KeYSSkMLaSbfAmfxfdwqb"
S = datetime.datetime(2026, 9, 11, 12, 0, 0, tzinfo=datetime.timezone.utc)
BUD = 10 * 1024 * 1024


def export(room, timeout=300):
    raw = urllib.request.urlopen(
        urllib.request.Request(BASE + "/r/" + room + "/export", headers=UA),
        timeout=timeout).read().decode("utf-8", "replace")
    rows = []
    for ln in raw.splitlines():
        ln = ln.strip()
        if ln.startswith("{"):
            try:
                rows.append(json.loads(ln))
            except ValueError:
                pass
    return rows, len(raw.encode("utf-8"))


def body(r):
    try:
        return json.loads(r["text"])
    except Exception:
        return {}


def snap(tag):
    rows, nbytes = export("d-sonnet-2-results")
    roster = {}
    for r in rows:
        o = body(r)
        if o.get("type") != "sonnet.identities.v1":
            continue
        for did, meta in (o.get("additions") or {}).items():
            roster[did] = {"seq": r["seq"], "ts": r["ts"], "first_seen": meta.get("first_seen")}
    out = {"tag": tag, "read_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "rows": len(rows), "floor_seq": rows[0]["seq"], "floor_ts": rows[0]["ts"],
           "head_seq": rows[-1]["seq"], "head_ts": rows[-1]["ts"],
           "bytes": nbytes, "pct_of_10MiB": round(100.0 * nbytes / BUD, 2),
           "roster": len(roster)}
    return out, rows, roster


A, rowsA, rosA = snap("A")
print(json.dumps(A, indent=1))
time.sleep(240)
B, rowsB, rosB = snap("B")
print(json.dumps(B, indent=1))

print("\n=== is the trim ongoing or a single past event? ===")
print("  floor A %d (%s) -> floor B %d (%s)" % (A["floor_seq"], A["floor_ts"], B["floor_seq"], B["floor_ts"]))
print("  floor advanced: %s" % (B["floor_seq"] > A["floor_seq"]))
print("  head  A %d -> B %d (added %d)" % (A["head_seq"], B["head_seq"], B["head_seq"] - A["head_seq"]))
sa = {r["seq"] for r in rowsA}
sb = {r["seq"] for r in rowsB}
print("  seqs present in A and gone in B: %d" % len(sa - sb))
print("  shared range byte-identical: %s"
      % all(json.dumps(x, sort_keys=True) == json.dumps(y, sort_keys=True)
            for x, y in zip([r for r in rowsA if r["seq"] in sb],
                            [r for r in rowsB if r["seq"] in sa])))

print("\n=== how checkable is eligibility from the LIVE room today? ===")
# every gated acceptance the referee published, as readable right now
GATED = ("voter", "writer")
acc = []
for r in rowsB:
    if r["from"] != REFEREE:
        continue
    o = body(r)
    if o.get("status") != "accepted" or o.get("role") not in GATED:
        continue
    t = o.get("type")
    if t == "sonnet.receipt.v1" and o.get("sender_did"):
        acc.append(o["sender_did"])
    elif t == "sonnet.receipts.v1":
        for it in o.get("receipts", []):
            if it.get("sender_did"):
                acc.append(it["sender_did"])
print("  gated acceptances readable in d-sonnet-2-results: %d (%d distinct)"
      % (len(acc), len(set(acc))))
print("  of those, backed by a roster entry still readable: %d"
      % len({d for d in acc if d in rosB}))
fs = [v["first_seen"] for v in rosB.values() if v["first_seen"]]
print("  roster now: %d DIDs; admitted with first_seen >= S: %d; newest first_seen %s"
      % (len(rosB), sum(1 for x in fs if x >= S.timestamp()),
         datetime.datetime.fromtimestamp(max(fs), datetime.timezone.utc).isoformat()))
print("  our DID in the readable roster: %s" % (OURS in rosB))

r110 = json.load(open("_r110_roster.json", encoding="utf-8"))
print("\n=== what the trim cost ===")
print("  r110 roster (2026-09-14T15:18 JST): %d DIDs" % len(r110))
print("  readable roster now:                %d DIDs" % len(rosB))
print("  r110 DIDs still readable:           %d" % len(set(r110) & set(rosB)))
print("  r110 DIDs no longer readable:       %d" % len(set(r110) - set(rosB)))
print("  union ever seen by us:              %d" % len(set(r110) | set(rosB)))

json.dump({"A": A, "B": B, "roster_now": len(rosB),
           "gated_accepts_readable": len(acc), "gated_distinct": len(set(acc)),
           "gated_backed": len({d for d in acc if d in rosB}),
           "r110_lost": len(set(r110) - set(rosB)),
           "r110_kept": len(set(r110) & set(rosB))},
          open("_r118_trim.json", "w"), indent=1)
