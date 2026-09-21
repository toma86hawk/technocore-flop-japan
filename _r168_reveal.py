# -*- coding: utf-8 -*-
"""Round 168: measure lock->reveal for ONLY the non-paper locks that are new
since the last published measurement (2026-09-20T21:40:31Z), so the run is
bounded and the sample is disjoint from r163's."""
import json, sys, io, urllib.request
from datetime import datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

CUT = "2026-09-20T21:40:31.999999Z"
ST = json.load(open(r"C:\Users\Administrator\flop\tclk_rail_state.json", encoding="utf-8"))
NEW = [l for l in ST["nonpaper_locks"] if l["ts"] > CUT]
print("new non-paper locks since %s: %d" % (CUT[:19], len(NEW)))


def room(r):
    req = urllib.request.Request("https://technocore.chat/r/%s/export" % r,
                                 headers={"User-Agent": "flop-jp-agent/1.0"})
    raw = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    out = []
    for ln in raw.splitlines():
        ln = ln.strip()
        if ln:
            try:
                out.append(json.loads(ln))
            except Exception:
                pass
    return out


def frame(t):
    t = str(t)
    if t.startswith("tclk1 "):
        try:
            return json.loads(t[6:])
        except Exception:
            return None
    return None


def p(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


rows = []
for L in NEW:
    try:
        ms = room(L["room"])
    except Exception as e:
        print(L["room"], "ERR", repr(e)[:60]); continue
    dids, seq, work = set(), {}, 0
    for m in ms:
        dids.add(m.get("from"))
        fr = frame(m.get("text"))
        if fr and fr.get("type"):
            seq.setdefault(fr["type"], m.get("ts"))
        else:
            work += 1
    lk, rv = seq.get("lock"), seq.get("reveal")
    dt = (p(rv) - p(lk)).total_seconds() if lk and rv else None
    rows.append({"room": L["room"], "ts": L["ts"], "msgs": len(ms), "n_dids": len(dids),
                 "lock_to_reveal_s": dt, "nontclk_msgs": work, "types": list(seq)})
    print("%-26s msgs=%d dids=%d lock->reveal=%s types=%s work=%d"
          % (L["room"], len(ms), len(dids), dt, list(seq), work))

json.dump(rows, open(r"C:\Users\Administrator\flop\guide\_r168_reveal.json", "w"), indent=1)
ok = [r for r in rows if r["lock_to_reveal_s"] is not None]
print("\nmeasured %d rooms" % len(rows))
print("exactly 2 msgs / 2 dids / 0 work msgs: %d of %d"
      % (sum(1 for r in rows if r["msgs"] == 2 and r["n_dids"] == 2 and r["nontclk_msgs"] == 0), len(rows)))
if ok:
    v = sorted(r["lock_to_reveal_s"] for r in ok)
    print("lock->reveal s:", v)
    print("min %.3f median %.3f max %.3f" % (v[0], v[len(v) // 2], v[-1]))
