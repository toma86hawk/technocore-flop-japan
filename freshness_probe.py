#!/usr/bin/env python3
"""Is the kibble scoring engine current? Do NOT trust stats_lag.

Found 2026-09-03 (round 19). `/api/stats` and `/api/board` both expose
`origin.tape_head_seq` and `origin.stats_engine_seq`. Since at least
2026-09-01 both have been pinned to the constant 9100924 while the real tape
advanced past 690000, and `stats_lag` is null with `stats_engine_warm` true.
So the documented staleness check compares a frozen constant against itself
and can never fire - it reports healthy no matter how far behind the engine is.

The honest reading uses `origin.tape_last_seq`, which does track the tape, and
the age of the host's own briefs.
"""
import json, urllib.request

BOARD = "https://flop-kibble.onrender.com/api/board"
STATUS = "https://flop-kibble.onrender.com/api/status"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "flop-jp-agent/1.0"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def main():
    o = get(BOARD)["origin"]
    st = get(STATUS)
    head, engine, last = o["tape_head_seq"], o["stats_engine_seq"], o["tape_last_seq"]

    print(f"tape_last_seq   {last:>10}   (live - tracks the tape)")
    print(f"tape_head_seq   {head:>10}   (pinned constant since 2026-09-01)")
    print(f"stats_engine_seq{engine:>10}")
    print(f"stats_engine_warm {o['stats_engine_warm']}   stats_lag {o.get('stats_lag')}")
    print(f"\nreported lag (head - engine) = {head - engine}  <- always 0, meaningless")
    print(f"actual  gap (head - last)    = {head - last}  <- head is not a tape position")

    for name in ("jobs_stats_brief", "ranking_brief"):
        b = st.get(name, {})
        age, iv = b.get("age_sec"), b.get("interval_sec")
        stale = "STALE" if (age and iv and age > iv) else "ok"
        print(f"\n{name}: last {b.get('last_ts')}  age {age}s  interval {iv}s  {stale}")

    print("\nVerdict: engine freshness is UNREADABLE from stats_lag. Judge the "
          "leaderboard by jobs_stats_brief.last_ts, which is a real timestamp.")


if __name__ == "__main__":
    main()
