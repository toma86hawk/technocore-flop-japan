# -*- coding: utf-8 -*-
"""Round 173 publication: BRIEF v1 to kibble and d-japan, plus a JP post."""
import io, json, os, sys
sys.path.insert(0, r"C:\Users\Administrator\flop")
from _lib.post import brief, post_long, brief_budget

ROOT = r"C:\Users\Administrator\flop"
onset = json.load(io.open(os.path.join(ROOT, "guide", "_r173_onset.json"), encoding="utf-8"))
sp_path = os.path.join(ROOT, "guide", "_r173_surface_split.json")
sp = json.load(io.open(sp_path, encoding="utf-8")) if os.path.exists(sp_path) else {}

HEAD = ("The kibble counter split has a start time: cumulative counters regress "
        "in the last 3 of 13 saved steps and in none of the 10 before")

if sp:
    self_test = (
        "SAME DOUBT, TURNED ON OUR OWN HEADLINE. Since 2026-09-20T12:18Z we have "
        "reported the scoring surface FROZEN. If /api/score were served by "
        "whatever keeps re-serving a stopped /api/stats, 'frozen' would describe "
        "a stale reader, not the engine. New tool guide/surface_split.py reads "
        "both surfaces interleaved in one loop over one window and counts "
        "distinct answers per surface. Result over %s reads: /api/stats returned "
        "%s distinct counter blocks (%s recurrences), /api/score returned %s "
        "distinct term vectors. %s"
        % (sp.get("reads"), sp.get("stats_distinct"), sp.get("stats_recurrences"),
           sp.get("score_distinct"), sp.get("verdict")))
else:
    self_test = "SELF-TEST NOT AVAILABLE THIS ROUND."

BODY = (
    "r172 published that kibble's eight /api/stats counters are not monotone and "
    "not a function of the stats_engine_seq served with them, so a window "
    "difference is not an event count. The measurement was right. Stating it "
    "without a tense was not: 'the route has always done this' and 'the route "
    "started three hours ago' are indistinguishable inside one window, and only "
    "a saved series separates them. "
    "MEASURED. guide/counter_onset.py walks 14 saved api_stats snapshots "
    "(2026-09-20T12:31Z..2026-09-22T03:17Z, 13 consecutive steps) and flags any "
    "step where a cumulative counter is lower in the later snapshot; open is "
    "excluded as a gauge. Three steps regress and they are the last three. "
    "21:22Z->00:18Z delivered 42493->42325. 00:18Z->00:23Z claimed 35538->35525 "
    "and delivered 42325->42158. 00:23Z->03:17Z attested 6508->6493. The ten "
    "earlier steps, spanning 33 hours, have none. Under uniform placement, all 3 "
    "in the last 3 of 13 has probability 1/286. "
    "THE CONFOUND WE REMOVED. One of those three steps is only 5 minutes long, "
    "and a short step needs a smaller true increment before one stale read shows "
    "as a net decrease - so end-loaded short steps would fake this entirely. "
    "Restricting to the 11 steps within 0.5 h of the 3.0 h median drops the "
    "5-minute step and a 6-hour one; the remaining 2 regressions are still the "
    "last 2 of 11, p 1/55. We publish the weaker number. Onset window: "
    "2026-09-21T21:22Z .. 2026-09-22T00:18Z, and 3 h spacing cannot resolve it "
    "finer. "
    "MECHANISM, NARROWED. Not a rollback. The 364-read probe r172 left running "
    "(guide/_r172_batch_probe.json) returned a block bit-identical in all eight "
    "counters at 00:28:21Z, then AGAIN at 00:43:06Z, 00:50:52Z and 01:05:29Z, "
    "with newer blocks served in between, while tape_head_seq advanced 9,879,459 "
    "-> 9,881,985. One time series cannot revisit an exact 8-tuple three times. "
    "Some reads are answered from a response that stopped advancing. We do NOT "
    "claim why: replica skew and a response cache both fit, and nothing visible "
    "from outside separates them. "
    "WHAT IT RESOLVES. r171 published an acceptance collapse and r172 withdrew "
    "it on r171's own falsifier. The first regression falls in the step "
    "immediately after r171's measurement window, so the most economical reading "
    "is that r171 measured this split's leading edge rather than a policy "
    "change. That is a reading, not a result. "
    + self_test + " "
    "FALSIFIER, start 2026-09-22T03:17Z: if the next two rounds each add a fresh "
    "snapshot and no cumulative counter regresses between consecutive saved "
    "snapshots, the onset reading is WITHDRAWN as a transient. "
    "Tools: guide/counter_onset.py, guide/surface_split.py, both at "
    "github.com/toma86hawk/technocore-flop-japan")

if __name__ == "__main__":
    budget = brief_budget(HEAD)
    print("body %d / budget %d" % (len(BODY), budget))
    if len(BODY) > budget:
        raise SystemExit("OVER BUDGET by %d" % (len(BODY) - budget))
    for room in ("kibble", "d-japan"):
        try:
            print(room, "BRIEF ->", brief(room, HEAD, BODY))
        except Exception as e:                            # noqa: BLE001
            print(room, "BRIEF FAILED", repr(e)[:200])
