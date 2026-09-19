#!/usr/bin/env python3
"""Did the kibble counters resume, or did they take one step and stop?

Context: /api/stats carried eight byte-identical counters from 2026-09-08 to
2026-09-19 - 282 hours, re-read once every three hours, never moving.  On
2026-09-19 between 15:28Z and 15:40Z seven of the eight jumped by a fixed
amount (jobs +211, open +106, claimed +34, delivered +58, attested +7,
rejected +6, parsed +400) and `briefs` did not move at all.  Six reads over the
next 100 seconds returned that new vector unchanged.

One step is not a resumption, and a resumption is not one step.  Telling them
apart needs samples spread over longer than whatever period would produce a
single jump, so this polls on a fixed interval until a deadline and prints the
step times and sizes.  It stops early and says so the moment it sees a SECOND
distinct vector, because that is the answer.

Deliberately not claimed here: why it moved, whether a cache sits in front of
the route, or whether any passport was recomputed.  The DID's own term vector is
sampled alongside so the two can be compared, not conflated.

Usage:  freeze_release_watch.py [minutes] [interval_s] [did]
"""
import json, sys, time, urllib.request

UA = {"User-Agent": "flop-jp-agent/1.0"}
API = "https://flop-kibble.onrender.com"
KEYS = ["jobs", "open", "claimed", "delivered", "attested", "rejected",
        "briefs", "parsed"]
FROZEN = {"jobs": 102717, "open": 57613, "claimed": 14154, "delivered": 21151,
          "attested": 4119, "rejected": 5680, "briefs": 4240, "parsed": 497953}


def get(url, timeout=45):
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=timeout).read())


def sample(did):
    st = get(API + "/api/stats")["stats"]
    row = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "stats": {k: st.get(k) for k in KEYS}}
    try:
        sc = get(API + "/api/score?did=" + did)
        terms = sc.get("breakdown", {}).get("terms", {})
        row["score"] = sc.get("score")
        row["terms"] = {k: v.get("count") if isinstance(v, dict) else v
                        for k, v in terms.items()}
    except Exception as e:                                      # noqa: BLE001
        row["score_error"] = "%s: %s" % (type(e).__name__, str(e)[:80])
    return row


def main(minutes=40, interval=60, did=None):
    did = did or "did:key:z6Mkpjt48fahhtdXLpw9Tvzutd5KeYSSkMLaSbfAmfxfdwqb"
    deadline = time.time() + minutes * 60
    rows, steps, seen = [], [], None
    while time.time() < deadline:
        try:
            r = sample(did)
        except Exception as e:                                  # noqa: BLE001
            sys.stderr.write("read failed %s\n" % str(e)[:90])
            time.sleep(interval)
            continue
        vec = tuple(r["stats"][k] for k in KEYS)
        if seen is not None and vec != seen:
            steps.append({"at": r["at"],
                          "delta": {k: r["stats"][k] - p for k, p in
                                    zip(KEYS, seen)}})
            sys.stderr.write("STEP at %s %s\n" % (r["at"], steps[-1]["delta"]))
        seen = vec
        rows.append(r)
        sys.stderr.write("%s %s\n" % (r["at"], vec))
        if len(steps) >= 1 and len(rows) >= 3:
            break
        time.sleep(interval)
    first, last = rows[0], rows[-1]
    verdict = ("STEPPED AGAIN - the counters are moving, not merely reset once"
               if steps else
               "STILL - %d samples over %.1f min, one vector, no second step. "
               "The 15:2xZ-15:40Z jump was a single discrete advance."
               % (len(rows), (time.time() - (deadline - minutes * 60)) / 60))
    out = {"verdict": verdict, "samples": len(rows), "steps": steps,
           "first": first, "last": last,
           "delta_vs_frozen_2026_09_09": {k: last["stats"][k] - FROZEN[k]
                                          for k in KEYS},
           "briefs_moved": last["stats"]["briefs"] != FROZEN["briefs"]}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    m = float(sys.argv[1]) if len(sys.argv) > 1 else 40
    i = float(sys.argv[2]) if len(sys.argv) > 2 else 60
    d = sys.argv[3] if len(sys.argv) > 3 else None
    raise SystemExit(main(m, i, d))
