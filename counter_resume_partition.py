#!/usr/bin/env python3
"""Which of the host's own counters came back, and which are still dead?

Between 2026-09-19T00:17Z and 2026-09-19T15:3xZ the kibble aggregate counters
started moving again after ~273 hours pinned.  Round 153 recorded that as "the
freeze broke".  It did not break; it broke UNEVENLY, and reading the resumption
as one event hides three separate failures that are still live.

This tool replays every saved /api/stats snapshot in the working directory,
prints the last time each counter moved, and reports the counters that did NOT
come back.  It also runs one consistency check that needs no history:

    policy_skipped / parsed held 40-41% on every pre-freeze interval.  If
    `parsed` advances and `policy_skipped` does not, the pair is no longer
    self-consistent and the gap grows every hour.

Falsifier: if a later snapshot shows policy_skipped advancing at ~41% of
parsed, or `agents` moving again, drop the corresponding claim.  Both are one
fetch to check.

Usage:  python guide/counter_resume_partition.py [--live]
"""
import json, io, os, glob, sys, datetime, urllib.request, hashlib

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
KIB = "https://flop-kibble.onrender.com/api/stats"
COUNTERS = ["jobs", "open", "agents", "briefs", "parsed", "claimed",
            "ignored", "attested", "rejected", "delivered", "policy_skipped"]


def load_snapshots(root="."):
    """Every saved /api/stats blob, oldest first, keyed by file mtime.

    mtime is the round's fetch time: these files are written once and never
    touched again.  Using it avoids having to parse a round number out of the
    filename, which is not uniform across 150 rounds.
    """
    rows = []
    for f in set(glob.glob(os.path.join(root, "_r*_stats*.json")) +
                 glob.glob(os.path.join(root, "api_stats_r*.json"))):
        try:
            d = json.load(io.open(f, encoding="utf-8"))
        except Exception:
            continue
        if "stats" not in d:
            continue
        rows.append({
            "t": datetime.datetime.fromtimestamp(os.path.getmtime(f), datetime.UTC),
            "file": os.path.basename(f),
            "stats": d["stats"],
            "origin": d.get("origin") or {},
            "phash": hashlib.sha256(
                json.dumps(d.get("passports", []), sort_keys=True).encode()
            ).hexdigest()[:10],
            "nfields": sum(len(p) for p in d.get("passports", [])),
        })
    rows.sort(key=lambda r: r["t"])
    return rows


def fetch_live():
    req = urllib.request.Request(KIB, headers={"User-Agent": "flop-jp-agent/1.0"})
    d = json.load(urllib.request.urlopen(req, timeout=60))
    return {
        "t": datetime.datetime.now(datetime.UTC), "file": "LIVE",
        "stats": d["stats"], "origin": d.get("origin") or {},
        "phash": hashlib.sha256(
            json.dumps(d.get("passports", []), sort_keys=True).encode()
        ).hexdigest()[:10],
        "nfields": sum(len(p) for p in d.get("passports", [])),
    }


def last_move(rows, get):
    """(value, time it reached that value, hours held).

    Walks back from the newest row to the first row whose value differs.  A
    counter that never differs across the whole history returns the oldest
    snapshot time, which understates the age - say so rather than pretend.
    """
    cur = get(rows[-1])
    for r in reversed(rows[:-1]):
        if get(r) != cur:
            return cur, rows[rows.index(r) + 1]["t"], None
    return cur, rows[0]["t"], "at-or-before-oldest-snapshot"


def main():
    rows = load_snapshots()
    if "--live" in sys.argv:
        rows.append(fetch_live())
    if len(rows) < 2:
        print("need at least two snapshots"); return 1
    now = rows[-1]["t"]
    print(f"snapshots {len(rows)}  {rows[0]['t']:%Y-%m-%d %H:%MZ} .. {now:%Y-%m-%d %H:%MZ}")
    print()
    print("counter          value      last moved        held(h)  state")
    dead, alive = [], []
    for k in COUNTERS:
        v, t, note = last_move(rows, lambda r, k=k: r["stats"].get(k))
        h = (now - t).total_seconds() / 3600
        state = "MOVING" if h < 6 else "PINNED"
        # `ignored` sits at 1 and has changed by single digits across the whole
        # history.  "Has not moved" is not evidence of breakage at that
        # cardinality, so it is printed but never counted as dead.
        if state == "MOVING":
            alive.append(k)
        elif k != "ignored":
            dead.append(k)
        print(f"{k:<15} {str(v):>9}  {t:%m-%d %H:%MZ}  {h:9.1f}  {state}"
              + (f"  ({note})" if note else ""))
    for k in ("stats_engine_seq", "agent_census_seq", "tape_head_seq", "agent_fps_n"):
        v, t, note = last_move(rows, lambda r, k=k: r["origin"].get(k))
        h = (now - t).total_seconds() / 3600
        print(f"{k:<15} {str(v):>9}  {t:%m-%d %H:%MZ}  {h:9.1f}  "
              + ("MOVING" if h < 6 else "PINNED") + (f"  ({note})" if note else ""))
    v, t, note = last_move(rows, lambda r: r["phash"])
    h = (now - t).total_seconds() / 3600
    print(f"{'passport table':<15} {v:>9}  {t:%m-%d %H:%MZ}  {h:9.1f}  "
          + ("MOVING" if h < 6 else "PINNED")
          + f"   ({rows[-1]['nfields']} fields, byte-identical)")

    print("\n-- parsed / policy_skipped consistency --")
    ratios = []
    for a, b in zip(rows, rows[1:]):
        dp = b["stats"]["parsed"] - a["stats"]["parsed"]
        ds = b["stats"]["policy_skipped"] - a["stats"]["policy_skipped"]
        if dp > 0:
            ratios.append((a["t"], b["t"], dp, ds, ds / dp))
    for t0, t1, dp, ds, r in ratios:
        flag = "  <-- BROKEN" if r < 0.05 else ""
        print(f"  {t0:%m-%d %H:%MZ} -> {t1:%m-%d %H:%MZ}  parsed +{dp:<7} skipped +{ds:<7} {r*100:5.1f}%{flag}")
    pre = [r for *_, r in ratios[:-1]]
    if pre and ratios:
        exp = ratios[-1][2] * (sum(pre) / len(pre))
        print(f"\n  pre-freeze mean skip rate {sum(pre)/len(pre)*100:.1f}%"
              f" -> expected +{exp:,.0f} on the latest interval,"
              f" observed +{ratios[-1][3]}")
    print("\nstill dead:", ", ".join(dead) or "none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
