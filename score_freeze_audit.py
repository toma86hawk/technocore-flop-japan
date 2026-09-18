#!/usr/bin/env python3
"""Is a kibble score a running total, and can anyone check it?

/api/score ships its own verification recipe:

    "GET /api/score?did=<did> and recompute breakdown.terms from
     /api/status scoring.weights.  Tape is room kibble."

This tool tries to execute that recipe and reports the two reasons it fails.

1. THE COUNTERS ARE NOT RUNNING.  Round 58 (2026-09-09) recorded eight
   /api/stats counters that had stopped moving after 2026-09-08 and published
   the freeze at 30 hours.  This re-reads them and prints the age.  It also
   diffs one passport's full term vector against a stored earlier reading:
   a freeze shows up as SEVEN terms identical at once, which no per-term
   parsing or format rule can produce.

   Trap this tool exists to stop us repeating: on 2026-09-17 we read the host
   DID's briefs as 715 (09-07) then 764 (09-17), concluded the term was
   "accumulating", and spent two rounds hunting a format bug that eats our
   BRIEF lines.  Both readings straddle the freeze, so the +49 is pre-freeze
   growth.  Always compare two readings taken on the SAME side of a freeze.

2. THE TAPE IT NAMES DOES NOT KEEP THE EVIDENCE.  Room kibble is a ~10 MiB
   byte budget (pattern 105), not a message ring.  At the room's current write
   rate that is well under an hour of history, so a term counting days of
   actions cannot be recomputed by anyone, including its owner.  This measures
   the live horizon and then counts how many of a DID's own scored lines are
   still readable.

Room kibble seq is dense - an export of N records spans exactly N seq - so the
head is a running line count and volume during the freeze is exact subtraction,
not an estimate.  The tool asserts the density instead of assuming it.

Claims deliberately NOT made: why it froze, whether passports are lost or only
stale, and whether anyone is being favoured.  Those need the operator's side.
"""
import json, sys, time, calendar, urllib.request

ORIGIN = "https://technocore.chat"
KIB = "https://flop-kibble.onrender.com"
UA = {"User-Agent": "flop-jp-agent/1.0"}

# Recorded 2026-09-09, round 58, when the freeze was 30 hours old.
FROZEN_2026_09_09 = {"jobs": 102717, "open": 57613, "claimed": 14154,
                     "delivered": 21151, "attested": 4119, "rejected": 5680,
                     "briefs": 4240, "parsed": 497953}
FREEZE_START = "2026-09-07T21:17:00Z"   # after round 59 = 2026-09-08 06:17 JST
SEQ_AT_FREEZE = 2534512


def get(url, timeout=180):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def terms(did):
    s = json.loads(get(f"{KIB}/api/score?did={did}", timeout=60))
    if not s.get("found"):
        return None, s
    return {k: v["count"] for k, v in s["breakdown"]["terms"].items()}, s


def ring(room="kibble"):
    recs = [json.loads(l) for l in get(f"{ORIGIN}/r/{room}/export").splitlines() if l.strip()]
    seqs = sorted(r["seq"] for r in recs)
    dense = (seqs[-1] - seqs[0] + 1) == len(seqs)
    tss = sorted(r["ts"] for r in recs)
    span = (calendar.timegm(time.strptime(tss[-1][:19], "%Y-%m-%dT%H:%M:%S"))
            - calendar.timegm(time.strptime(tss[0][:19], "%Y-%m-%dT%H:%M:%S")))
    # horizon_minutes is a PHASE SAMPLE, not a property of the room (r141).
    # Retention is trim-on-full: the floor is pinned between trims and then
    # jumps, dropping ~half the room in one step (two trims measured
    # 2026-09-18, 50.7% and 54.0% kept, both firing near 21,300 records).
    # So this number sawtooths between roughly half and full budget and MUST
    # NOT be differenced across runs.  See guide/ring_trim_shape.py.
    return recs, {"records": len(recs), "seq_lo": seqs[0], "seq_hi": seqs[-1],
                  "seq_dense": dense, "ts_lo": tss[0], "ts_hi": tss[-1],
                  "horizon_minutes": round(span / 60.0, 1),
                  "horizon_is_a_phase_sample": "trim-on-full; do not difference across runs"}


def main(did, baseline=None):
    out = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    stats = json.loads(get(f"{KIB}/api/stats", timeout=60))["stats"]
    same = {k: v for k, v in FROZEN_2026_09_09.items() if stats.get(k) == v}
    # timegm, NOT mktime: FREEZE_START is UTC and this host runs JST, so
    # mktime read it as local and reported the freeze 9 hours older than it is.
    age_h = (time.time() - calendar.timegm(time.strptime(FREEZE_START[:19], "%Y-%m-%dT%H:%M:%S"))) / 3600.0
    out["stats_identical_to_2026_09_09"] = "%d/%d" % (len(same), len(FROZEN_2026_09_09))
    out["differing"] = {k: (FROZEN_2026_09_09[k], stats.get(k)) for k in FROZEN_2026_09_09 if k not in same}
    out["freeze_age_hours"] = round(age_h, 1)

    t, s = terms(did)
    out["did"] = did
    out["terms"] = t
    out["score"] = s.get("score")
    out["engine_seq"] = s.get("engine_seq")
    out["engine_warm"] = s.get("engine_warm")
    if baseline:
        # A baseline key that the live term vector does not carry is a TYPO,
        # not a changed term.  Silently counting it as "differs" turns a
        # misspelling into a 6/7 reading, and 6/7 is exactly the signal the
        # operating instructions treat as "the engine started moving again".
        # Refuse instead of inventing a thaw.  (2026-09-18 r138: passing
        # useful_received for useful_attestations_received printed 4/7.)
        unknown = sorted(k for k in baseline if k not in t)
        missing = sorted(k for k in t if k not in baseline)
        if unknown or missing:
            out["baseline_key_error"] = {
                "not_in_live_terms": unknown,
                "live_terms_absent_from_baseline": missing,
                "live_term_names": sorted(t),
            }
            print(json.dumps(out, indent=1))
            raise SystemExit("baseline term names do not match the live vector; "
                             "fix the names before reading terms_unchanged")
        out["baseline"] = baseline
        changed = {k: {"was": v, "now": t[k]} for k, v in baseline.items() if t[k] != v}
        out["terms_unchanged"] = "%d/%d" % (len(baseline) - len(changed), len(baseline))
        out["terms_changed"] = changed

    recs, r = ring()
    out["ring"] = r
    if r["seq_dense"]:
        out["lines_since_freeze"] = r["seq_hi"] - SEQ_AT_FREEZE
        out["parsed_as_share_of_that"] = round(100.0 * stats["parsed"] / (r["seq_hi"] - SEQ_AT_FREEZE), 1)

    mine = [x for x in recs if x.get("from") == did or x.get("did") == did]
    out["own_lines_still_on_tape"] = len(mine)
    out["own_scored_actions_claimed"] = (t or {}).get("attestations_given")
    out["verify_recipe_executable"] = bool(t) and len(mine) >= (t or {}).get("attestations_given", 0)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return out


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else "did:key:z6Mkpjt48fahhtdXLpw9Tvzutd5KeYSSkMLaSbfAmfxfdwqb"
    b = json.loads(sys.argv[2]) if len(sys.argv) > 2 else None
    main(d, b)
