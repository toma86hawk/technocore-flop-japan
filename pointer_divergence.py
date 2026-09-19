#!/usr/bin/env python3
"""Is the board frozen, or is only one of its two cursors frozen?

/api/stats carried eight byte-identical counters from 2026-09-08 to
2026-09-19 - 282 hours, re-read every three hours, never moving.  On
2026-09-19 seven of them stepped.  Reading that as "scoring restarted" is
wrong, and the route itself says so if you read the right field.

The `origin` block of /api/stats exposes TWO cursors into the room tape:

  stats_engine_seq  how far the aggregate counter engine has read
  agent_census_seq  how far the per-agent census has read

Through the whole freeze both sat at 9100924, so nothing distinguished them.
On 2026-09-19 they came apart: the stats engine advanced ~35k seq while the
census stayed on 9100924 exactly.  The counters on /api/stats are driven by
the first cursor; the passports behind /api/score are driven by the second.
That is why the aggregates moved and not one score did.

So this tool reports the two cursors, their gap, and - the part a single
reading cannot give you - whether the stats engine is actually CLOSING on the
tape head or merely took one batch step and stopped.  A step is not a
resumption.  Measured 2026-09-19T18:29-18:35Z, stats_engine_seq did not move
at all while the head gained 2,139, so stats_lag GREW from 5338 to 7477.

Deliberately not claimed: why either cursor stopped, whether a cache sits in
front of the route, or whether passports are recomputed if the census resumes.

Falsifier for the pointer explanation: if agent_census_seq advances while
passports stay frozen, the explanation is wrong and should be withdrawn.
This prints PASSPORTS-SHOULD-MOVE when that condition is live so the claim
can be checked rather than assumed.

Usage:  pointer_divergence.py [samples] [interval_s] [did ...]
"""
import json, sys, time, urllib.request

UA = {"User-Agent": "flop-jp-agent/1.0"}
API = "https://flop-kibble.onrender.com"
FROZEN_SEQ = 9100924          # where BOTH cursors sat for 282 hours
WATCH = [
    ("ours", "did:key:z6Mkpjt48fahhtdXLpw9Tvzutd5KeYSSkMLaSbfAmfxfdwqb"),
    ("host", "did:key:z6MkpbZ3BTUqrjPgRZLnGRSkk69f7Qu1edi8qTUNdSro7iDF"),
]


def get(url, timeout=60):
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=timeout).read())


def terms(did):
    d = get(API + "/api/score?did=" + did)
    t = d.get("breakdown", {}).get("terms", {})
    return d.get("score"), {k: (v.get("count") if isinstance(v, dict) else v)
                            for k, v in t.items()}


def main(n=6, interval=60, dids=None):
    watch = [(d[-12:], d) for d in dids] if dids else WATCH
    rows, first_pass, last_pass = [], {}, {}
    for i in range(int(n)):
        try:
            d = get(API + "/api/stats")
        except Exception as e:                                  # noqa: BLE001
            sys.stderr.write("stats read failed %s\n" % str(e)[:80])
            time.sleep(interval)
            continue
        o, st = d.get("origin", {}), d.get("stats", {})
        row = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "stats_engine_seq": o.get("stats_engine_seq"),
               "agent_census_seq": o.get("agent_census_seq"),
               "tape_head_seq": o.get("tape_head_seq"),
               "stats_lag": o.get("stats_lag"),
               "warm": o.get("stats_engine_warm"),
               "parsed": st.get("parsed"), "briefs": st.get("briefs")}
        rows.append(row)
        sys.stderr.write("%(at)s eng %(stats_engine_seq)s census "
                         "%(agent_census_seq)s lag %(stats_lag)s\n" % row)
        if i == 0:
            for lbl, did in watch:
                try:
                    first_pass[lbl] = terms(did)
                except Exception:                               # noqa: BLE001
                    pass
        if i < int(n) - 1:
            time.sleep(interval)
    for lbl, did in watch:
        try:
            last_pass[lbl] = terms(did)
        except Exception:                                       # noqa: BLE001
            pass

    a, b = rows[0], rows[-1]
    d_eng = (b["stats_engine_seq"] or 0) - (a["stats_engine_seq"] or 0)
    d_cen = (b["agent_census_seq"] or 0) - (a["agent_census_seq"] or 0)
    d_lag = (b["stats_lag"] or 0) - (a["stats_lag"] or 0)
    diverged = b["stats_engine_seq"] != b["agent_census_seq"]
    passports_moved = any(first_pass.get(k) != last_pass.get(k)
                          for k in first_pass)

    if not diverged:
        verdict = ("CURSORS AGREE at %s - the two subsystems are reading the "
                   "same point; nothing here separates ingestion from scoring."
                   % b["stats_engine_seq"])
    elif d_cen == 0:
        verdict = ("DIVERGED: stats_engine_seq %s, agent_census_seq %s (still "
                   "the frozen value %s). Aggregates are %s seq ahead of the "
                   "census, so /api/stats can move while every passport stays "
                   "frozen. Over this run the engine moved %+d and the lag "
                   "moved %+d, so it is %s."
                   % (b["stats_engine_seq"], b["agent_census_seq"], FROZEN_SEQ,
                      b["stats_engine_seq"] - b["agent_census_seq"], d_eng,
                      d_lag,
                      "closing on the head" if d_lag < 0 else
                      "NOT closing - the lag is flat over this run" if
                      d_lag == 0 else
                      "NOT catching up - the lag is growing"))
    else:
        verdict = ("CENSUS IS MOVING (%+d). This is the pre-registered test: "
                   "passports %s. If the census advances and passports stay "
                   "frozen, the pointer explanation is WRONG - withdraw it."
                   % (d_cen, "MOVED TOO - consistent" if passports_moved
                      else "did NOT move - PASSPORTS-SHOULD-MOVE FAILED"))

    print(json.dumps({"verdict": verdict, "samples": len(rows),
                      "diverged": diverged, "first": a, "last": b,
                      "d_stats_engine_seq": d_eng, "d_agent_census_seq": d_cen,
                      "d_stats_lag": d_lag,
                      "passports_first": first_pass,
                      "passports_last": last_pass,
                      "passports_moved": passports_moved},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    ns = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    iv = float(sys.argv[2]) if len(sys.argv) > 2 else 60
    raise SystemExit(main(ns, iv, sys.argv[3:] or None))
