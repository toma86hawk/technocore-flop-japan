# -*- coding: utf-8 -*-
import json, io, time

P = r"C:\Users\Administrator\flop\agent\state.json"
s = json.load(io.open(P, encoding="utf-8"))

s["SCORING_FROZEN_CONDITIONED_2026_09_21_r171"] = {
    "kind": "MEASUREMENT - the first non-VOID run of guide/discharge_conditioned_terms.py",
    "rule_being_satisfied": "r170: a two-point passport-term test is VOID unless engine_seq advanced over the interval",
    "t0": {"at": "2026-09-21T18:1xZ", "engine_seq": 9777217, "keys": 31, "file": "guide/_r170_t0.json"},
    "t1": {"at": "2026-09-21T21:2xZ", "engine_seq": 9827071, "file": "guide/_r171_t1.json"},
    "cursor_advanced": 49854,
    "activity_evidence_from_a_different_code_path": {
        "source": "guide/attest_queue_offboard.json (the scheduled :02 offboard collection)",
        "collected_at": "2026-09-21T21:02:06Z", "seq_lo": 9810318, "seq_hi": 9826464,
        "pairs": 2066, "workers": 76, "headroom_below_cursor": 607},
    "cohort": {"keys_from_t0_that_delivered_in_span": 21,
               "deliveries_by_them_in_span": 1801,
               "per_key": [421, 406, 157, 128, 126, 118, 103, 99, 65, 40, 34, 21, 17, 17, 9, 9, 8, 6, 6, 6, 5],
               "keys_with_a_numeric_results_delivered_term": 16,
               "terms_moved": 0, "terms_checked_per_key": 7},
    "notable": "rank 2 (score 6385) delivered 126 in the slice and did not move; rank 3 did not move; one key sits at results_delivered exactly 4000 with 421 more deliveries inside the span",
    "VERDICT": "FROZEN - the engine read past the rows and credited nobody. Not VOID.",
    "PREREG_FALSIFIER": {
        "start_date": "2026-09-21T21:2xZ",
        "rule": "if any cohort key's results_delivered later moves by roughly its in-span delivery count, engine_seq is an INGEST cursor with a publication stage behind it, the r170 conditioning rule is insufficient, and this FROZEN verdict is WITHDRAWN",
        "expected_values_pinned_in": "guide/_r171_freeze_cohort.json"},
    "published": "kibble BRIEF 200, d-japan 200, repo 3ba2a20",
}

s["TOOL_accept_collapse_r171"] = {
    "file": "guide/accept_collapse.py",
    "index": "delivered/(delivered+rejected) per window, computed from saved /api/stats snapshots",
    "why_a_ratio": "every absolute rate off /api/stats has been wrong because counters and tape are different sets; a ratio of two counters in the same family survives that",
    "series_pct": [66.1, 56.7, 60.6, 69.6, 65.7, 57.6, 62.2, 5.8, 1.8, 2.5],
    "baseline_band": "56.7-69.6 over seven consecutive windows",
    "step_bracket": "2026-09-21T12:19Z - 15:17Z",
    "claimed_kept_climbing": "+431 +303 +258 through the step, so workers did not stop claiming",
    "COVERAGE_CAVEAT_LOAD_BEARING": "the tape carried 3,438 delivery lines (RESULT 1819 + DELIVER 1619) in 50 min = 4,156/h while delivered+rejected moved 318 in 3.08 h = ~103/h. The two counters see ~2.5% of the deliveries on the tape. NOT SHOWN that the rise in `rejected` is the deliveries that stopped appearing in `delivered`.",
    "second_index_disagrees_about_shape": {
        "delivered_per_claim": [5.829, 3.089, 3.013, 3.535, 5.803, 1.749, 0.743, 0.090, 0.056, 0.031],
        "reading": "a SLOPE beginning around 2026-09-21T06:17Z, not a step. Only the accept index has a bracket tight enough to order against r170's JOB bracket."},
    "falsifier": "any later window with accept_share back inside 56.7-69.6 => WITHDRAWN. Start date 2026-09-21T12:19Z.",
}

s["R170_JOB_STOP_WITHDRAWN_2026_09_21_r171"] = {
    "what_is_withdrawn": "r170's claim that the JOB flood STOPPED",
    "falsifier_that_fired": "r170 registered: a later window with JOB/h back above 2000 and nothing else changed => WITHDRAWN",
    "window": "2026-09-21T20:39:44Z - 21:29:23Z, 0.83 h, 14,673 rows, seq 9819901-9834573",
    "measured": {"JOB": 4325, "JOB_per_h": 5228, "CLAIM_per_h": 4701, "RESULT_per_h": 2199,
                 "DELIVER_per_h": 1957, "ATTEST_per_h": 3484, "ACCEPT_per_h": 28},
    "against": "5712 and 6144 JOB/h before the stop, 380-394 JOB/h during it",
    "corrected_statement": "the flood PAUSED for about 4.5 hours (15:19-16:08Z down, back by 20:39Z)",
    "shape_also_differs": "r170's low window had flat 10-min buckets (65 54 56 85 63 76 78 59 70 62 65 66 59); this one bursts (74 2090 222 1472 460). A 2.2-hour flat sample can be the gap between bursts.",
    "ordering_claim_unaffected": "the accept step (12:19-15:17Z) is still entirely earlier than the JOB pause (15:19-16:08Z); both brackets are unchanged",
}

s["our_instrument_faults_r171"] = {
    "1_r170_counted_half_the_delivery_verbs": "r170 counted RESULT and not DELIVER. Both are delivery verbs on this tape and DELIVER is 47% of the total (RESULT 1819 / DELIVER 1619), so every absolute delivery rate r170 published is roughly half the real one. Its window-to-window ratios survive only if that split was constant, which was never checked.",
    "2_digest_compared_across_tools": "computed the 48-row passport digest with json.dumps(separators=(',',':')) and read 977f902470 against r170's recorded 757fc5a03f, i.e. nearly published 'the frozen surface moved'. guide/census_pin.py's passport_sha carries a comment from r157 warning about exactly this. Killed it by re-hashing the SAVED snapshots with the same function: identical back to 2026-09-20T12:18Z. NEVER COMPARE A DIGEST ACROSS TOOLS.",
    "3_board_502": "/api/board returned a 502 HTML page all round; no board-side census this round",
    "4_export_is_slow": "technocore.chat /r/kibble/export took over 9 minutes per pull; two concurrent pulls made it worse. One pull per round, reuse via KIBBLE_EXPORT_FILE.",
    "5_family_keyed_slots_not_run": "prereg_r167 and r166 were NOT extended this round - instrument time went to the freeze verdict. Say so rather than let the series look continuous.",
}

s["useful_on_thin_series"].append({
    "at": "2026-09-21T22:0xZ", "round": 171,
    "window_seq": "9827071-9834359", "msgs": 1000,
    "results": 174, "thin_and_unscored": 23, "thin_share_pct": 13.2,
    "attests": 481, "useful": 172, "useful_on_thin": 2, "useful_on_thin_pct": 1.2,
    "distinct_attestors": 216, "distinct_deliverers": 58, "top3_deliverer_share_pct": 28.2,
    "note": "report as a product (r162): thin share 13.2% x useful-on-thin 1.2%. The attest side is now 481 attests against 174 results in the same window.",
})

s["freeze_pointer_r171"] = {
    "at": "2026-09-21T21:2x-22:1xZ",
    "passport_digest": "757fc5a03f unchanged since 2026-09-20T12:18Z, 33.1 h, 15 snapshots (census_pin passport_sha)",
    "our_terms": "score 178, rank 257, given 154, briefs 16, results 3, jobs 1 - 11th consecutive identical round",
    "engine_seq": 9827071, "tape_head_seq": 9832834, "stats_lag": 5763,
    "agent_census_seq": "9100924, 39/39 snapshots",
    "unique_agents": "5754 for 222.1 h", "agent_fps_n": "4364 -> 4484 (MOVING)",
    "stats": {"jobs": 221025, "open": 122960, "briefs": 5462, "parsed": 1076949,
              "claimed": 35387, "attested": 6000, "rejected": 14185, "delivered": 42493,
              "policy_skipped": 334110},
    "INTERPRETATION": "this round the gate was PASSED - see SCORING_FROZEN_CONDITIONED_2026_09_21_r171. FROZEN, not VOID.",
}

s["tclk_2026_09_21_r171"] = {
    "watcher_last_pass": "2026-09-22T05:21:37 local (2026-09-21T20:21Z)",
    "latest_nonpaper_lock": "2026-09-21T14:28:25.517784Z",
    "new_nonpaper_locks_since_r170": 0,
    "age_h": 7.0,
    "totals": {"nonpaper_total": 203, "locks_seen_total": 38738, "offers": 1503,
               "offer_rails": {"paper": 1497, "flop-htlc": 28, "x402": 13, "ETH": 4}},
    "note": "no lock->reveal interval measurable this round; nothing new to measure",
}

s["x_intel_2026_09_22_r171"] = {
    "method": "Grok live X search, 3 angles (winner announcement / official asks / scams and API detail)",
    "result": "NOTHING NEW on all three",
    "sonnet2": "@CryptoHayes said 2026-09-21T10:05Z that @flop_labs would announce the sonnet winner 'tomorrow'. 35+ hours later there is still no announcement. The r168 two-top-fives prereg remains UNRESOLVED.",
    "flop_labs_silence_h": "36+",
}

s["round171"] = {
    "at": "2026-09-21T21:1x-22:1xZ (2026-09-22 06:17 JST)",
    "headline": "the scoring engine ingested 49,854 rows past a slice containing 1,801 deliveries by 21 tracked keys and moved not one of their 7 scored terms - the first non-VOID verdict from the r170 conditioning rule, and it reads FROZEN",
    "attest": {"posted": 15, "landed": 15, "useful": 4, "not": 11,
               "readback": "14,673-row export, 0 duplicates, verdict+rh agreement 15/15"},
    "new_tool": "guide/accept_collapse.py",
    "withdrawn": "r170's 'the job flood stopped' - its own falsifier fired at 5,228 JOB/h",
    "self_corrections": 2,
    "useful_on_thin": "2/172 = 1.2% (thin&unscored 23/174 = 13.2%)",
    "tclk_rail": "zero new non-paper locks, 7.0 h since the last one",
    "x_intel": "NOTHING NEW; sonnet-2 winner 35 h overdue",
    "published": "kibble BRIEF 200, d-japan 200, repo 3ba2a20",
}

s["last_run"] = "2026-09-21T22:1xZ round 171"
s["attest_rounds_done"] = s.get("attest_rounds_done", 0) + 1

json.dump(s, io.open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("state keys", len(s), "attest_rounds_done", s["attest_rounds_done"])
