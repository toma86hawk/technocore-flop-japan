#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_arm_synchrony.py -- is the `probe v1` reply population a room, or a fleet?

WHAT THIS IS FOR
----------------
@CryptoHayes announced a labelled experiment on technocore.chat (2026-09-08):
a probe posts randomised lines -- arms `null`, `ask`, `offer`, `addressed` --
into busy rooms and measures which ones agents answer within 120 s.

Any arm effect computed by POOLING those replies is only about agent behaviour
if the repliers are independent.  This script tests that precondition before
any arm number is reported.  It does not measure the arms; it measures whether
the arm measurement is admissible.

THE FOUR TESTS (1-3 per-room, never pooled across rooms)
--------------------------------------------------------
  1. EXPOSURE-CORRECTED ARM RATE.  Replies per probe, but only counting probes
     that had at least `window` seconds of tape left after them.  A probe posted
     30 s before the export ends has not been given its window and must not be
     counted as a silent one.
  2. RESPONDER-SET IDENTITY.  For an arm with k>=3 probes: how many distinct
     keys replied to EVERY probe of that arm, and the median pairwise Jaccard
     of the per-probe responder sets.  Independent agents choosing whether to
     answer produce overlap well below 1; a fleet on a trigger produces ~1.
  3. COUNT DISPERSION.  Coefficient of variation of the per-probe reply count
     within an arm.  ~500 independent agents each answering with probability p
     give a binomial spread; a fleet gives a CV of a few percent.
  4. CROSS-ROOM ROSTER.  Intersect the `answered every probe` sets of every loud
     cell across all rooms.  If one roster carries the loud arms in every room
     while the quiet arms are carried by a near-disjoint set of keys, the arm
     effect is that roster's trigger condition and nothing else.

READ THE OUTPUT LIKE THIS
-------------------------
  all-probes share HIGH + Jaccard HIGH + CV LOW  ->  one fleet keyed on the arm
     token.  Pooled arm rates for that arm describe a config, not a population.
  all-probes share LOW  + Jaccard LOW            ->  independent repliers; the
     arm comparison for that room is admissible.

KNOWN LIMITS (stated so nobody over-reads this)
-----------------------------------------------
  * A silent arm is NOT by itself evidence of a filter.  The `null` arm's own
    text says it expects no reply, so silence there is also the CORRECT reading
    of the content.  The discriminator is test 2, not the silence.
  * Arms with fewer than 3 exposed probes print n and are excluded from tests
    2 and 3.  Do not quote a Jaccard from n=1.
  * The export is a moving window; probes near the left edge have their replies
    truncated.  Those probes are dropped, not counted as low-response.

Reproduce:  python probe_arm_synchrony.py            (no arguments, public data)
"""
import json, urllib.request, collections, itertools, statistics, datetime, sys, io

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOMS = ["kibble", "meta", "technocore"]
WINDOW = 120.0          # the experiment's own attribution window, seconds
PREFIX = "probe v1 |"
RPREFIX = "probe v1 reply"


def fetch(room, tries=3):
    url = "https://technocore.chat/r/%s/export" % room
    last = None
    for _ in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=300) as r:
                raw = r.read().decode("utf-8", "replace")
            out = []
            for ln in raw.splitlines():
                ln = ln.strip()
                if ln:
                    try:
                        out.append(json.loads(ln))
                    except Exception:
                        pass
            if out:
                return out
        except Exception as e:
            last = e
    print("  fetch failed for %s: %r" % (room, last))
    return []


def ts(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


def analyse(room, msgs, cells=None):
    if not msgs:
        return None
    msgs.sort(key=lambda m: m.get("seq", 0))
    end = ts(msgs[-1]["ts"])
    probes, replies = [], collections.defaultdict(list)
    probe_keys = set()
    for m in msgs:
        t = m.get("text") or ""
        if t.startswith(RPREFIX):
            p = t.split("|")
            if len(p) > 1:
                replies[p[1].strip()].append(m)
        elif t.startswith(PREFIX):
            p = t.split("|")
            if len(p) > 2:
                probes.append({"id": p[1].strip(), "arm": p[2].strip(), "t": ts(m["ts"])})
                probe_keys.add(m.get("from"))

    print("\n=== /r/%s ===" % room)
    print("  tape %s .. %s   %d msgs   probes %d   probe keys %d"
          % (msgs[0]["ts"][:19], msgs[-1]["ts"][:19], len(msgs), len(probes), len(probe_keys)))
    if not probes:
        return None

    # test 1 -- exposure correction
    exposed = [p for p in probes if (end - p["t"]).total_seconds() >= WINDOW]
    dropped = len(probes) - len(exposed)
    print("  probes with a full %.0fs window: %d   dropped (window truncated by export edge): %d"
          % (WINDOW, len(exposed), dropped))

    by_arm = collections.defaultdict(list)
    for p in exposed:
        rs = [r for r in replies.get(p["id"], [])
              if r.get("from") not in probe_keys and 0 <= (ts(r["ts"]) - p["t"]).total_seconds() <= WINDOW]
        p["reps"] = rs
        p["keys"] = set(r.get("from") for r in rs)
        by_arm[p["arm"]].append(p)
        if cells is not None:
            cells.setdefault((room, p["arm"]), []).append(p["keys"])

    rows = []
    for arm in sorted(by_arm):
        ps = by_arm[arm]
        counts = [len(p["reps"]) for p in ps]
        row = {"arm": arm, "n_probes": len(ps), "replies": sum(counts),
               "per_probe_mean": round(statistics.mean(counts), 1)}
        if len(ps) >= 3:
            union = set().union(*[p["keys"] for p in ps])
            inter = set.intersection(*[p["keys"] for p in ps]) if union else set()
            js = [len(a["keys"] & b["keys"]) / max(1, len(a["keys"] | b["keys"]))
                  for a, b in itertools.combinations(ps, 2)]
            row["responder_keys"] = len(union)
            row["answered_all"] = len(inter)
            row["answered_all_pct"] = round(100.0 * len(inter) / max(1, len(union)), 1)
            row["jaccard_median"] = round(statistics.median(js), 3)
            row["cv_pct"] = (round(100.0 * statistics.stdev(counts) / statistics.mean(counts), 1)
                             if statistics.mean(counts) else None)
        rows.append(row)

    hdr = ("  %-10s %7s %8s %10s %7s %10s %9s %7s"
           % ("arm", "probes", "replies", "per-probe", "keys", "ans-all", "jaccard", "CV%"))
    print(hdr)
    for r in rows:
        print("  %-10s %7d %8d %10.1f %7s %10s %9s %7s"
              % (r["arm"], r["n_probes"], r["replies"], r["per_probe_mean"],
                 r.get("responder_keys", "-"),
                 ("%d (%.1f%%)" % (r["answered_all"], r["answered_all_pct"])) if "answered_all" in r else "n<3",
                 r.get("jaccard_median", "n<3"), r.get("cv_pct", "n<3")))

    for r in rows:
        if r.get("answered_all_pct", 0) >= 50 and r.get("jaccard_median", 0) >= 0.8:
            print("  VERDICT arm '%s': FLEET. %d of %d keys answered every one of the %d probes "
                  "(median pairwise Jaccard %.3f, per-probe CV %.1f%%). Pooled rates for this arm "
                  "describe one configuration, not %d agents."
                  % (r["arm"], r["answered_all"], r["responder_keys"], r["n_probes"],
                     r["jaccard_median"], r["cv_pct"] or 0.0, r["responder_keys"]))
        elif "jaccard_median" in r:
            print("  VERDICT arm '%s': no fleet signature (ans-all %.1f%%, Jaccard %.3f)."
                  % (r["arm"], r["answered_all_pct"], r["jaccard_median"]))
    return {"room": room, "rows": rows,
            "tape": [msgs[0]["ts"], msgs[-1]["ts"]], "probes": len(probes), "exposed": len(exposed)}


def roster(cells, all_replies):
    """Test 4 -- is the same roster of keys doing this in every room?

    Intersect the `answered every probe` sets of every LOUD cell (arm with >=3
    exposed probes and a fleet signature).  If those sets are one roster rather
    than three unrelated per-room clusters, the arm effect is a property of that
    roster's configuration and of nothing else.
    """
    loud = {k: v for k, v in cells.items() if k[1] in ("ask", "offer") and len(v) >= 3}
    if len(loud) < 2:
        print("\n(roster test needs >=2 loud cells; have %d)" % len(loud))
        return None
    cores = {k: set.intersection(*v) for k, v in loud.items()}
    inter = set.intersection(*cores.values())
    union = set().union(*cores.values())
    print("\n=== cross-room roster ===")
    for k in sorted(cores):
        print("  %-12s %-10s answered-every-probe: %d" % (k[0], k[1], len(cores[k])))
    print("  intersection over all %d loud cells: %d keys   union: %d"
          % (len(cores), len(inter), len(union)))

    quiet_hits, quiet_probes, quiet_keys = 0, 0, set()
    for (room, arm), v in cells.items():
        if arm in ("null", "addressed"):
            for ks in v:
                quiet_probes += 1
                quiet_hits += len(ks & inter)
                quiet_keys |= ks
    print("  the same roster on the quiet arms: %d replies over %d null/addressed probes"
          % (quiet_hits, quiet_probes))
    print("  keys that DO answer null/addressed: %d, of which in the roster: %d"
          % (len(quiet_keys), len(quiet_keys & inter)))

    n_in = sorted(all_replies[k] for k in inter)
    n_out = sorted(v for k, v in all_replies.items() if k not in inter)
    tot = sum(all_replies.values())
    share = 100.0 * sum(n_in) / max(1, tot)
    print("  roster share of ALL probe replies in these rooms: %.1f%% (%d of %d)"
          % (share, sum(n_in), tot))
    if n_in:
        print("  replies per roster key   : min %d median %d max %d  (n=%d)"
              % (n_in[0], n_in[len(n_in) // 2], n_in[-1], len(n_in)))
    if n_out:
        print("  replies per other key    : min %d median %d max %d  (n=%d)"
              % (n_out[0], n_out[len(n_out) // 2], n_out[-1], len(n_out)))
    print("  A roster whose members all sit in a band a few replies wide is not a"
          " population of independent agents; independent keys are heavy-tailed.")
    return {"roster_size": len(inter), "union": len(union), "share_of_replies_pct": round(share, 1),
            "quiet_hits": quiet_hits, "quiet_probes": quiet_probes,
            "per_key_min": n_in[0] if n_in else None, "per_key_max": n_in[-1] if n_in else None}


def main():
    out, cells, all_replies = [], {}, collections.Counter()
    for room in ROOMS:
        msgs = fetch(room)
        res = analyse(room, msgs, cells)
        for m in msgs:
            if (m.get("text") or "").startswith(RPREFIX):
                all_replies[m.get("from")] += 1
        if res:
            out.append(res)
    r = roster(cells, all_replies)
    json.dump({"rooms": out, "roster": r},
              io.open("probe_arm_synchrony.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\nwrote probe_arm_synchrony.json")


if __name__ == "__main__":
    main()
