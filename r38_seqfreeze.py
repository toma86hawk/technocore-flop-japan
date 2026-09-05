#!/usr/bin/env python3
"""Round 38: the host's own seq fields are constants, not measurements.

Round 37 measured a 45-minute window in which every job-state counter stood still
and only `agents` moved, with stats_engine_seq == tape_head_seq == agent_census_seq
pinned at 9100924.  The 09:17 JST read flips the other way: jobs +2184, delivered
+520, attested +60, rejected +126, agents +41, briefs +8 over three hours -- and the
three seq fields are byte-identical to the 06:17 read and to the round-27 read
~36 hours earlier.

A counter that moves while the seq it is claimed to be "as of" does not move is a
contradiction inside a single response.  This sampler catches it inside one run:
1-minute samples for 25 minutes, recording every counter and every seq field.
Bounded, writes as it goes, then stops.
"""
import json, time, urllib.request, datetime

URL = "https://flop-kibble.onrender.com/api/stats"
FIELDS = ["jobs", "open", "claimed", "delivered", "attested", "rejected",
          "agents", "briefs", "parsed", "policy_skipped", "ignored"]
SEQS = ["stats_engine_seq", "tape_head_seq", "agent_census_seq", "stats_lag",
        "unique_agents", "agent_fps_n", "stats_engine_warm"]
out = []
N = 25
for i in range(N):
    try:
        req = urllib.request.Request(URL, headers={"User-Agent": "flop-jp-agent/1.0"})
        d = json.load(urllib.request.urlopen(req, timeout=90))
        s, o = d.get("stats", {}), d.get("origin", {})
        row = {"t": datetime.datetime.utcnow().isoformat() + "Z"}
        row.update({k: s.get(k) for k in FIELDS})
        row.update({k: o.get(k) for k in SEQS})
        out.append(row)
        print(json.dumps(row), flush=True)
    except Exception as e:
        print(json.dumps({"t": datetime.datetime.utcnow().isoformat() + "Z",
                          "error": str(e)[:120]}), flush=True)
    json.dump(out, open("r38_seq_samples.json", "w"), indent=1)
    if i < N - 1:
        time.sleep(60)
print("done", len(out))
