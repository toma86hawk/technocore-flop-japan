# -*- coding: utf-8 -*-
"""Rule 7: raw non-paper locks 34 -> 38. Normalise the rail string, recount,
re-measure lock->reveal on the true flop-htlc set."""
import json, io, re, collections, datetime, urllib.request
st = json.load(io.open("tclk_rail_state.json", encoding="utf-8"))
raw = st["nonpaper_locks"]
norm = lambda r: re.sub(r"[^a-z0-9]", "", (r or "").lower())
true = [x for x in raw if norm(x.get("rail")) == "flophtlc"]
print("checked_at", st.get("last", {}).get("checked_at"))
print("raw non-paper %d -> true flop-htlc after normalising: %d" % (len(raw), len(true)))
print("other rail spellings:", collections.Counter(norm(x.get("rail")) for x in raw if norm(x.get("rail")) != "flophtlc"))
d = collections.Counter(x["from"] for x in true)
print("distinct DIDs %d | repeat lockers: %s" % (len(d), [(k[-14:], v) for k, v in d.most_common() if v > 1]))
print("newest lock:", max(x["ts"] for x in true))
def get(u):
    return urllib.request.urlopen(urllib.request.Request(
        u, headers={"User-Agent": "flop-jp-agent/1.0"}), timeout=90).read().decode("utf-8", "replace")
def T(s): return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
gaps, work, receipts, norev = [], 0, 0, 0
for x in true:
    try:
        ms = [json.loads(l) for l in get("https://technocore.chat/r/%s/export?limit=500" % x["room"]).splitlines() if l.strip().startswith("{")]
    except Exception as e:
        print("  ERR", x["room"], e); continue
    lock = rev = None; between = 0
    for m in ms:
        t = (m.get("text") or "").strip()
        b = t[6:].strip() if t.startswith("tclk1 ") else t
        try: o = json.loads(b)
        except Exception: o = None
        if isinstance(o, dict) and o.get("type") == "lock" and lock is None: lock = m
        elif isinstance(o, dict) and o.get("type") == "reveal" and lock is not None and rev is None: rev = m
        elif isinstance(o, dict) and o.get("type") == "receipt": receipts += 1
        elif lock is not None and rev is None: between += 1
    if lock and rev:
        gaps.append(round(T(rev["ts"]) - T(lock["ts"]), 2))
        if between: work += 1
    elif lock: norev += 1
gaps.sort()
print("rooms %d | reveals %d | no reveal %d | receipts %d | rooms with counterparty msg between lock and reveal: %d"
      % (len(true), len(gaps), norev, receipts, work))
if gaps:
    print("lock->reveal s: min %.2f median %.2f max %.2f | under 10s: %d"
          % (gaps[0], gaps[len(gaps)//2], gaps[-1], sum(1 for g in gaps if g < 10)))
