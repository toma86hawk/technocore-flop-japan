"""Round 69: which kibble endpoints are alive while /api/board is dead?

Round 68 recorded /api/board at HTTP 000 after 90s and /api/tape likewise, while
/api/stats answered normally.  If every path that has to READ THE TAPE is dead
and /api/stats still serves a growing unique_agents, the census cannot be coming
off the tape at the seq it advertises.

One request per endpoint, 8s apart, short timeout.  No hammering, no retries.
"""
import json, time, urllib.request, urllib.error, datetime

BASE = "https://flop-kibble.onrender.com"
# (path, does answering it require reading the tape?)
EPS = [
    ("/api/status", False),
    ("/api/stats", False),
    ("/api/board", True),
    ("/api/tape?limit=5", True),
    ("/api/jobs?limit=5", True),
    ("/api/score?did=did:key:z6Mkpjt48fahhtdXLpw9Tvzutd5KeYSSkMLaSbfAmfxfdwqb", True),
]
TIMEOUT = 45
rows = []
for path, tapey in EPS:
    t0 = time.time()
    row = {"path": path, "reads_tape": tapey,
           "t": datetime.datetime.utcnow().isoformat() + "Z"}
    try:
        req = urllib.request.Request(BASE + path,
                                     headers={"User-Agent": "flop-health/1"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read()
        row.update(http=r.status, bytes=len(body))
        try:
            row["head"] = json.loads(body.decode("utf-8", "replace"))
        except Exception:
            row["head"] = body[:200].decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        row.update(http=e.code, bytes=0, err="HTTPError")
    except Exception as e:
        row.update(http=0, bytes=0, err=type(e).__name__ + ": " + str(e)[:120])
    row["secs"] = round(time.time() - t0, 1)
    rows.append(row)
    print("%-58s http=%-4s bytes=%-8s %5.1fs %s" % (
        path, row["http"], row["bytes"], row["secs"], row.get("err", "")), flush=True)
    time.sleep(8)

json.dump(rows, open("probe_endpoint_health_2026-09-09.json", "w"), indent=1,
          default=str)
live_tape = [r for r in rows if r["reads_tape"] and r["http"] == 200]
dead_tape = [r for r in rows if r["reads_tape"] and r["http"] != 200]
live_cache = [r for r in rows if not r["reads_tape"] and r["http"] == 200]
print("\ntape-reading endpoints: %d live / %d dead" % (len(live_tape), len(dead_tape)))
print("non-tape endpoints    : %d live / %d dead" % (
    len(live_cache), len([r for r in rows if not r["reads_tape"] and r["http"] != 200])))
if not live_tape and live_cache:
    print("VERDICT: clean split -- every tape-reading path is dead, cached paths serve.")
else:
    print("VERDICT: no clean split; the outage is not tape-specific.")
