#!/usr/bin/env python3
"""Round 36: measure the 5 non-paper tclk/1 locks that appeared after round 35
(2026-09-04T15:17Z onward), the same way rounds 33/35 measured the earlier ones.

Reads the FULL room export (not /r/<room>?format=json, which truncates), so the
lock->reveal interval and the presence/absence of a counterparty are read from the
whole chain rather than a window.
"""
import json, urllib.request, collections, sys, time
from datetime import datetime

ORIGIN = "https://technocore.chat"
CUT = __import__("os").environ.get("CUT","2026-09-04T15:17:00Z")

st = json.load(open("tclk_rail_state.json", encoding="utf-8"))
new = [x for x in st["nonpaper_locks"] if x["ts"] > CUT]
print("new non-paper locks since round 35:", len(new))


def get(url, tries=4, timeout=90):
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            last = e
            time.sleep(3 + 3 * i)
    raise last


def ts(s):
    return datetime.strptime(s.replace("Z", "")[:26], "%Y-%m-%dT%H:%M:%S.%f")


out = []
for lk in new:
    room = lk["room"]
    try:
        raw = get("%s/r/%s/export" % (ORIGIN, room))
    except Exception as e:
        print(room, "EXPORT-FAIL", str(e)[:80]); continue
    msgs = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        if isinstance(o, dict) and "text" in o:
            msgs.append(o)
    frames, nontclk = [], 0
    for m in msgs:
        t = m.get("text", "")
        if t.startswith("tclk1 "):
            try:
                j = json.loads(t[6:])
            except Exception:
                j = {"type": "badjson"}
            frames.append((j.get("type"), m.get("ts"), m.get("from"), j))
        else:
            nontclk += 1
    kinds = collections.Counter(f[0] for f in frames)
    signers = collections.Counter(f[2] for f in frames)
    lock = next((f for f in frames if f[0] == "lock"), None)
    rev = next((f for f in frames if f[0] == "reveal"), None)
    rec = next((f for f in frames if f[0] == "receipt"), None)
    dt = None
    if lock and rev:
        dt = round((ts(rev[1]) - ts(lock[1])).total_seconds(), 3)
    # does the reveal or receipt carry any artifact / job binding?
    art = {}
    for f in frames:
        for k, v in (f[3] or {}).items():
            if k in ("type", "v", "contract", "sig", "from", "ts"):
                continue
            art.setdefault(f[0], {})[k] = (str(v)[:60])
    row = dict(room=room, rail=lk["rail"], ts=lk["ts"], frames=len(frames),
               kinds=dict(kinds), signers=len(signers), nontclk=nontclk,
               lock_reveal_s=dt, settled=bool(rec),
               single_signer=(len(signers) == 1),
               top_signer=signers.most_common(1)[0] if signers else None,
               fields=art)
    out.append(row)
    print(json.dumps(row, ensure_ascii=False)[:900])

json.dump(out, open("r36_nonpaper.json", "w"), indent=1, default=str)
gaps = [r["lock_reveal_s"] for r in out if r["lock_reveal_s"] is not None]
print("\nlock->reveal secs:", sorted(gaps))
print("settled:", sum(1 for r in out if r["settled"]), "/", len(out))
print("single-signer rooms:", [r["room"] for r in out if r["single_signer"]])
print("rooms with non-tclk (real work) messages:",
      [(r["room"], r["nontclk"]) for r in out if r["nontclk"]])
