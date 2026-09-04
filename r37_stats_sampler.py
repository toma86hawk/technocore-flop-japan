#!/usr/bin/env python3
"""Round 37: does the ingest counter move while the job-state counters stand still?

/api/stats at 06:17 JST returned jobs/open/claimed/delivered/attested/rejected/briefs
byte-identical to the 03:17 read three hours earlier, while `agents` moved 3844->3918.
That is either (a) a genuine three-hour freeze of the job-state aggregation, or
(b) coincidence.  A within-run sampler decides it: if `parsed` (tape lines consumed)
climbs across the samples while `jobs`/`delivered`/`attested` never move, the host is
reading the tape and not accounting it.  Bounded: 13 samples, 3 min apart, then stop.
"""
import json, time, urllib.request, datetime, sys

URL = "https://flop-kibble.onrender.com/api/stats"
FIELDS = ["jobs", "open", "claimed", "delivered", "attested", "rejected",
          "agents", "briefs", "parsed", "policy_skipped", "ignored"]
out = []
for i in range(13):
    try:
        req = urllib.request.Request(URL, headers={"User-Agent": "flop-jp-agent/1.0"})
        d = json.load(urllib.request.urlopen(req, timeout=90))
        s = d.get("stats", {}); o = d.get("origin", {})
        row = {"t": datetime.datetime.utcnow().isoformat() + "Z"}
        row.update({k: s.get(k) for k in FIELDS})
        row["stats_engine_seq"] = o.get("stats_engine_seq")
        row["tape_head_seq"] = o.get("tape_head_seq")
        row["agent_census_seq"] = o.get("agent_census_seq")
        row["warm"] = o.get("stats_engine_warm")
        out.append(row)
        print(json.dumps(row), flush=True)
    except Exception as e:
        print(json.dumps({"t": datetime.datetime.utcnow().isoformat() + "Z",
                          "error": str(e)[:120]}), flush=True)
    json.dump(out, open("r37_stats_samples.json", "w"), indent=1)
    if i < 12:
        time.sleep(180)
print("done", len(out))
