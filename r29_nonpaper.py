#!/usr/bin/env python3
"""Round 29: the value-bearing rail finally moved. Re-measure lock->reveal.

AGENT.md step 7 says a non-paper lock is the highest-priority event. Between
round 28 (03:17 JST) and now there were exactly 1 -> 3. This measures each of
them end to end and compares against the paper baseline the catalogue was
built on, and checks the one thing an HTLC must have: a hashlock in the LOCK
frame that the later preimage can be checked against.
"""
import json, urllib.request, collections, hashlib, sys, datetime

ORIGIN = "https://technocore.chat"

def get(u, timeout=60, tries=4):
    import time
    for a in range(tries):
        try:
            return urllib.request.urlopen(u, timeout=timeout).read().decode("utf-8", "replace")
        except Exception:
            if a == tries - 1:
                raise
            time.sleep(3 * (a + 1))

def frames(room):
    d = json.loads(get("%s/r/%s?format=json" % (ORIGIN, room)))
    out = []
    for m in d.get("messages", []):
        t = m.get("text", "")
        if not t.startswith("tclk1 "):
            continue
        try:
            fr = json.loads(t[6:])
        except Exception:
            continue
        out.append((m.get("ts"), m.get("from"), fr))
    return out

def ts(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))

st = json.load(open("tclk_rail_state.json", encoding="utf-8"))
np_locks = st["nonpaper_locks"]
print("=== non-paper locks: %d ===" % len(np_locks))

report = []
for rec in np_locks:
    room = rec["room"]
    fs = frames(room)
    kinds = [f[2].get("type") for f in fs]
    lock = next((f for f in fs if f[2].get("type") == "lock"), None)
    rev = next((f for f in fs if f[2].get("type") == "reveal"), None)
    gap = None
    if lock and rev:
        gap = (ts(rev[0]) - ts(lock[0])).total_seconds()
    # hashlock present?
    hl_fields = [k for k in (lock[2] if lock else {}) if k.lower() in
                 ("hash", "hashlock", "h", "digest", "commit", "commitment", "preimage_hash")]
    # does the revealed secret hash to anything in the lock frame?
    checkable = False
    if lock and rev and rev[2].get("secret"):
        sec = rev[2]["secret"]
        cand = set()
        raw = sec[2:] if sec.startswith("0x") else sec
        for h in (hashlib.sha256(sec.encode()).hexdigest(),
                  hashlib.sha256(bytes.fromhex(raw)).hexdigest() if len(raw) % 2 == 0 else "",
                  hashlib.sha3_256(bytes.fromhex(raw)).hexdigest() if len(raw) % 2 == 0 else ""):
            if h:
                cand.add(h); cand.add("0x" + h)
        blob = json.dumps(lock[2])
        checkable = any(c in blob for c in cand)
    r = {
        "contract": rec["contract"][:18] + "...",
        "room": room, "rail": rec["rail"],
        "lock_ts": lock[0] if lock else None,
        "locker": (lock[1] or "")[-12:] if lock else None,
        "revealer": (rev[1] or "")[-12:] if rev else None,
        "same_did": (lock and rev and lock[1] == rev[1]),
        "gap_sec": gap,
        "frames": kinds,
        "n_frames": len(fs),
        "lock_fields": sorted(lock[2].keys()) if lock else None,
        "amount": lock[2].get("amount") if lock else None,
        "asset": lock[2].get("asset") if lock else None,
        "hashlock_fields": hl_fields,
        "preimage_checkable": checkable,
        "has_receipt": "receipt" in kinds,
    }
    report.append(r)
    print(json.dumps(r, ensure_ascii=False, indent=1))

# ---- paper baseline over every room we have a lock for ----
print("\n=== paper baseline (rooms with a paper lock) ===")
seen = st["seen_locks"]
paper_rooms = [v["room"] for v in seen.values() if str(v.get("rail", "")).lower() == "paper"]
paper_rooms = sorted(set(paper_rooms))
gaps, nohash, noamount, receipts, checked = [], 0, 0, 0, 0
for room in paper_rooms[:60]:
    try:
        fs = frames(room)
    except Exception:
        continue
    lock = next((f for f in fs if f[2].get("type") == "lock"), None)
    rev = next((f for f in fs if f[2].get("type") == "reveal"), None)
    if not lock:
        continue
    checked += 1
    if not any(k.lower() in ("hash", "hashlock", "h", "digest", "commit", "commitment") for k in lock[2]):
        nohash += 1
    if lock[2].get("amount") is None:
        noamount += 1
    if any(f[2].get("type") == "receipt" for f in fs):
        receipts += 1
    if rev:
        gaps.append((ts(rev[0]) - ts(lock[0])).total_seconds())

gaps.sort()
print("paper rooms checked: %d, with reveal: %d" % (checked, len(gaps)))
if gaps:
    print("lock->reveal sec  min %.1f  median %.1f  max %.1f" %
          (gaps[0], gaps[len(gaps)//2], gaps[-1]))
print("locks with NO hashlock field: %d/%d" % (nohash, checked))
print("locks with NO amount:         %d/%d" % (noamount, checked))
print("rooms reaching receipt:       %d/%d" % (receipts, checked))

json.dump({"nonpaper": report, "paper_baseline": {
    "rooms_checked": checked, "with_reveal": len(gaps),
    "gaps_sec": gaps, "no_hashlock": nohash, "no_amount": noamount,
    "receipts": receipts}}, open("r29_nonpaper.json", "w"), indent=1)
