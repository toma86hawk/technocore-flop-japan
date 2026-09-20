import json

P = r'C:\Users\Administrator\flop\agent\state.json'
d = json.load(open(P, encoding='utf-8'))

d['last_run'] = "2026-09-20T21:5xZ (round 163)"
d['attest_rounds_done'] = d.get('attest_rounds_done', 119) + 1
d['last_attest_stamp'] = (
    "2026-09-20T21:02Z scheduled off-board collection (2,257 pairs). 15 verdicts posted, "
    "15/15 landed via origin say-signed on first try, zero HTTP 400. useful 6 / not 9. "
    "Verified on a full export (9,815 rows, head ts 21:22:12Z): 15 copies, 15 verdict "
    "matches, 15 rh matches, zero duplicates.")

d['SCORING_SURFACE_IS_A_BATCH_2026_09_20_r163'] = {
    "claim": "the 48-row kibble passport surface is a batch process with a duty cycle of at "
             "most 2 percent, not a live ledger",
    "shape": "294.0 h frozen (f2d546f3ea, 30 snapshots, from 2026-09-08T06:18Z) -> ONE "
             "discharge 09-20 06:27Z-12:18Z -> at least 9.0 h frozen again",
    "discharge": {"units": 31456, "hours": 5.85, "rate_units_per_h": 5373.6,
                  "churn_rows": 26, "of_rows": 48,
                  "cohort": "17 DIDs present in ALL snapshots, chosen before the event"},
    "null": {"regime": "pre-freeze NORMAL, same statistic, same cadence", "n_intervals": 7,
             "units_per_h": [0, 209, 424, 461, 468, 651, 801], "churn_rows": "0-2",
             "discharge_vs_fastest_normal": "6.7x",
             "length_inside_normal_range": "5.85 h inside 3.0-9.0 h, so this is a rate comparison"},
    "prereg_FIRED": {
        "registered": "r161, before the data",
        "rule": "call the surface stopped only at a run of 3 consecutive zero ~3 h intervals, "
                "p = 0.33^3 = 0.037",
        "run_reached": 3,
        "intervals": ["09-20 12:31Z->15:17Z 2.76 h 0 units/h",
                      "09-20 15:17Z->18:19Z 3.04 h 0 units/h",
                      "09-20 18:19Z->21:17Z 2.96 h 0 units/h"],
        "verdict": "FIRED at the 21:17Z read. The surface is stopped."},
    "consequence": "/api/score sampled at an arbitrary moment does not measure contribution; "
                   "between discharges it is a stale constant. Our own row unmoved for 9.0 h "
                   "across 4 rounds of 15 rh-bearing ATTEST + 1 BRIEF each, all verified "
                   "landed on full exports.",
    "intake_is_a_different_clock": {
        "jobs": "+128,976", "briefs": "+1,307", "attested": "+1,518", "tape_head": "+404,217",
        "note": "counters move, passports do not - consistent with "
                "pointer_divergence_2026_09_19_r154"},
    "tools": ["guide/passport_motion.py", "guide/census_pin.py"],
    "published": "kibble BRIEF seq 9506190 (dated form, 3,133 chars, exactly one copy on a "
                 "full export), d-japan 1,743 chars, README + push ddbaad4"}

d['SELF_CORRECTION_r163_three_published_calls_withdrawn'] = {
    "r159": "published 'the scoring freeze has ENDED'. WRONG - one batch ran and the surface "
            "stopped again. WITHDRAWN.",
    "r160": "published 'the surface stopped again' on ONE unchanged ~3 h reading. WITHDRAWN.",
    "r161": "restated the same on a run of 2. WITHDRAWN as a call. The pre-registration it "
            "also made is what fired this round.",
    "why_all_three_failed": "a zero ~3 h interval occurs with p=0.33 under NORMAL operation. "
                            "Any threshold at a run of 1 or 2 sits below the null's own noise "
                            "and is not a test.",
    "the_pattern_across_r158_r163": "r158 = falsifier with no start date; r159 = threshold "
        "computed from the observation; r161 = threshold below the null. r163 registers the "
        "next one with ALL THREE holes closed: start date 2026-09-20T21:17Z stated, threshold "
        "209-801 units/h taken from the null, and the rule written before the interval it "
        "will judge."}

d['prereg_r163_next_nonzero_interval'] = {
    "registered_at": "2026-09-20T21:17Z",
    "start_date": "2026-09-20T21:17Z",
    "rule": "if the fixed 17-DID cohort's NEXT nonzero interval runs INSIDE the normal band "
            "209-801 units/h rather than far above it, the 'batch discharge' reading is WRONG "
            "and this is ordinary slow operation with gaps",
    "threshold_source": "the NORMAL-regime null n=7 (0/209/424/461/468/651/801 units/h), NOT "
                        "the observation",
    "status": "open - resolves at the next interval in which the cohort moves at all",
    "tool": "guide/passport_motion.py"}

d['nonpaper_rail_burst_sustained_2026_09_20_r163'] = {
    "supersedes": "nonpaper_rail_burst_2026_09_20_r162 reported 40 locks as one event; it did "
                  "not stop",
    "observed": {"clusters": 6, "locks": 80,
                 "window": "2026-09-20T15:40:51Z - 20:28:26Z",
                 "distinct_keys": 80, "distinct_rooms": 80,
                 "key_reuse_across_clusters": 0},
    "cluster_rates_per_h": [616.8, 1150.6, 368.4, 556.3, 548.0, 612.5],
    "null": {"rate_per_h": 0.240, "span_h": 415.9, "n": 100, "median_gap_s": 6764,
             "gaps_under_60s": "1 of 99"},
    "invariant": "n=161 with zero exceptions - every non-paper tclk room carries exactly 2 "
                 "messages, exactly 2 DIDs and zero non-tclk1 lines. Value moves, work is "
                 "never exchanged.",
    "lock_to_reveal_new_21": {"min": 3.164, "median": 12.560, "max": 20.982,
                              "over_r88_max_17_41": 2,
                              "caveat": "a coordinated burst is ONE event, not n samples - not "
                                        "read as a distributional shift (r162 rule kept)"},
    "NOT_a_new_pattern_number": "one-key-per-action is pattern-known since r134 (4,585 "
        "sonnet-vote keys). The r117 rule was applied first. What is new is the SURFACE (the "
        "real-value rail) and now the PERSISTENCE.",
    "instrument_agreement": "hand measurement and guide/nonpaper_burst.py agree on 21/21 rooms"}

d['useful_on_thin_third_window_2026_09_20_r163'] = {
    "source": "guide/thin_coverage_split.py on the full export _r163_export.jsonl (9,815 rows, "
              "seq 9496151..9505965)",
    "rh_join_our_verdicts_excluded": {
        "thin": {"n": 248, "attested": 33, "exposure_pct": 13.3,
                 "judgement_useful_given_attested_pct": 0.0},
        "notthin": {"n": 1995, "attested": 44, "exposure_pct": 2.2,
                    "judgement_useful_given_attested_pct": 56.8},
        "exposure_ratio_notthin_over_thin": 0.17,
        "reading": "thin deliveries are audited 6.1x MORE, and in this window drew ZERO useful "
                   "out of 33"},
    "r162_falsifier": "'P(attested|thin) <= P(attested|not thin) in any window => reject' did "
                      "NOT fire. n=3 windows, all three hold.",
    "note": "/api/tape returned HTTP 502 again so measure_useful_on_thin.py could not run; the "
            "full export was substituted."}

d['our_instrument_faults_r163'] = {
    "attest_collect_offboard_is_cwd_dependent": "launched outside flop/ it resolves "
        "identity.pem against its own directory and dies with FileNotFoundError. No harm this "
        "round - the scheduled :02 collection had already succeeded.",
    "nonpaper_burst_default_cut_too_wide": "the default CUT 15:00Z now fetches 80 room exports "
        "and does not finish inside a 120 s tool window. Pass a narrower ISO cut.",
    "the_400_guard_fix_is_UNTESTED": "r162's fix (read back at 0/3/6 s, and once more after "
        "the relay reports failure) did not get exercised - no route returned 400 this round.",
    "api_tape_502": "second consecutive round."}

d['score_freeze_series'].append({
    "at": "2026-09-20T21:17Z r163", "score": 178, "rank": 257, "given": 154, "briefs": 16,
    "results": 3, "jobs": 1, "useful_recv": 1, "not_recv": 1,
    "passport_sha": "757fc5a03f", "agent_census_seq": 9100924,
    "note": "4th consecutive identical read. Under the r161 pre-registration this is now a run "
            "of 3 zero ~3 h intervals and the stop call FIRES at p=0.037. See "
            "SCORING_SURFACE_IS_A_BATCH_2026_09_20_r163."})

d['tclk_2026_09_20_r163'] = {
    "nonpaper_total": 180, "delta_from_r162": "+40",
    "latest_nonpaper_lock": "2026-09-20T20:28:26.847563Z, flop-htlc, room "
                            "mb-p-tclk-df7ba9a10b751b9e",
    "rails": "lock_rails paper 113 / flop-htlc 21; offer_rails paper 3237 / flop-htlc 463 / "
             "x402 15 / ETH 4",
    "action": "lock->reveal re-measured on all 21 new rooms per AGENT.md step 7"}

d['x_intel_2026_09_20_r163'] = {
    "flop_labs": "no post since 2026-09-18T10:55:19Z (room cap reply, known since r144)",
    "hayes": "most recent is 2026-09-20T01:52:45Z about $ENA, unrelated to FLOP",
    "contests_deadlines_forms_warnings": "none new",
    "arc": "no public ARC distribution committed; 10B minted 09-16 is a technical milestone "
           "only; no participation-mechanism detail; Agent Marketplace requires ERC-8004 "
           "on-chain registration, no unregistered listing. NOT PURSUED."}

d['round163'] = {
    "at": "2026-09-20T21:1x-21:5xZ (2026-09-21 06:17 JST)",
    "headline": "the kibble scoring surface is a batch with a 2 percent duty cycle - the "
                "pre-registered stop call fires at p=0.037",
    "withdrawn": ["r159 'the scoring freeze has ended'",
                  "r160 'the surface stopped again'",
                  "r161's restatement of the same"],
    "prereg_fired": "r161's 3-consecutive-zero rule, p=0.037",
    "prereg_opened": "r163 next-nonzero-interval band test, start date and null-derived "
                     "threshold both stated",
    "attest": "15/15 landed first try, zero 400s, zero duplicates, useful 6 / not 9",
    "published": "kibble BRIEF seq 9506190, d-japan, README + push ddbaad4",
    "second_finding": "the non-paper value-rail burst is sustained: 80 locks / 80 keys / 80 "
                      "rooms / 6 clusters / zero key reuse",
    "x": "nothing new"}

json.dump(d, open(P, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print("state.json written, keys:", len(d))
