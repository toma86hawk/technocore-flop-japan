# -*- coding: utf-8 -*-
import json, io, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
P = r"C:\Users\Administrator\flop\agent\state.json"
d = json.load(io.open(P, encoding="utf-8"))

d["nonpaper_rail_burst_2026_09_20_r162"] = {
    "headline": "the one-key-per-action fleet shape has reached the value rail",
    "NULL_measured_first": {
        "window": "2026-09-03T00:43:56Z .. 2026-09-20T08:39:44Z = 415.9 h",
        "locks": 100,
        "rate": "0.240 locks/h",
        "clock_hours_with_any_lock": "86 of 416 (20.7%)",
        "MAX_locks_in_one_clock_hour_ever": 2,
        "times_that_happened": 14,
        "inter_arrival_gaps_s": "n=99, min 9.0, median 6764.3, max 172925.6",
        "gaps_under_60s": "1 of 99 (1.0%)",
    },
    "observed": {
        "span": "2026-09-20T15:40:51Z .. 17:58:36Z",
        "clusters": [
            "15:40:51-15:43:23  n=26  151.8 s   617 locks/h",
            "17:09:15-17:09:40  n=8    25.0 s  1151 locks/h",
            "17:57:37-17:58:36  n=6    58.6 s   368 locks/h",
        ],
        "keys": "40 locks, 40 distinct keys, 40 distinct rooms, one lock each",
        "returning_keys": "ZERO of the 40 had ever locked on the non-paper rail before",
        "gaps_under_60s": "39 of 40 (was 1 of 99)",
        "slowest_cluster_vs_lifetime_rate": "1533x",
    },
    "NOT_a_new_pattern_number": "one fresh key per action is already catalogued - the 4,585-key sonnet "
                                "ballot fleet (r134) and the 24,349 one-key contest messages. The r117 "
                                "novelty check was run (ls guide/detect_*.py guide/*fleet*.py plus a "
                                "phenomenon-word grep of state.json: burst / locks per hour / fresh key / "
                                "never locked) before claiming anything. What is new is the SURFACE: every "
                                "prior instance was on a free surface, this is the rail that moves value, "
                                "the one place the shape had not appeared in 416 h.",
    "lock_to_reveal_remeasured": {
        "n": 40, "read": "40/40 rooms", "revealed": "40/40",
        "min": 3.237, "median": 12.139, "max": 28.543,
        "established_band": "r88, n=63, median 4.96 s, max 17.41 s",
        "above_previous_all_time_max": "4 of 40 (22.094, 25.504, 27.255, 28.543), all four in the 17:57Z cluster",
        "NOT_claimed": "a distribution shift on 40 independent draws. One coordinated burst is ONE event. "
                       "The defensible statement is only: an interval above 17.41 s had never been seen in "
                       "63 prior measurements and occurred 4 times here.",
    },
    "invariant_at_n140": "0 of 40 rooms carry any non-tclk1 message - lock, reveal, sometimes receipt, "
                         "nothing else. Value moves, work is never exchanged: 140 non-paper deals, zero "
                         "exceptions. 0 of 40 are single-DID, so these are not self-payments; 3 rooms carry "
                         "4 DIDs rather than 2.",
    "tool": "guide/nonpaper_burst.py (null + clusters + per-room lock->reveal + invariant, any cut time)",
    "FALSIFIER": "a NORMAL-regime clock hour on this rail containing 3 or more non-paper locks would kill "
                 "the 'max 2 per hour' null this rests on. Start date 2026-09-03T00:43Z, constant.",
    "commit": "e028317",
}

d["SELF_CORRECTION_r162_useful_on_thin_was_an_unfactored_product"] = {
    "WITHDRAWN": "r161's 'thin deliveries are attested useful at 7.6% vs 36.8%, so auditors discriminate "
                 "against thin work about five to one' - the sentence and the 4.8x number both.",
    "why": "P(a useful verdict exists | delivery) = P(attested at all) x P(useful | attested). Only the "
           "second factor is judgement; the first is whether anybody looked. r37 had ALREADY measured a "
           "large exposure gap on a thin-like partition (56-char receipts judged at 12.3% vs 23.9%) and "
           "concluded 'the one real difference is whether it is looked at, not what is said'. That control "
           "existed in our own state file and was not carried into r161.",
    "method": "two DISJOINT export windows, verdicts joined to bodies BY rh (sha256(body)[:16]), not by "
              "job_id - one job holds several competing bodies and the job_id join collapses them, which "
              "is how r160 lost a threshold.",
    "measured": {
        "window_1": "seq 9423427-9437662 (r161's own saved export _r161_kibble3.jsonl)",
        "window_2": "seq 9450891-9465766 (guide/_r162_export.jsonl)",
        "EXPOSURE P(attested)": {
            "w1": "thin 9/226 = 4.0% vs notthin 59/2564 = 2.3%, ratio 1.73x",
            "w2": "thin 31/302 = 10.3% vs notthin 95/2917 = 3.3%, ratio 3.15x",
            "pooled": "thin 40/528 = 7.6% vs notthin 154/5481 = 2.8%, ratio 2.70x, two-proportion z = 5.92",
            "direction": "BACKWARDS from the r161 story - thin bodies are attested MORE often, not less",
        },
        "JUDGEMENT P(useful|attested)": {
            "w2_rh_join": "thin 9.7% vs notthin 47.4%, ratio 4.89x",
            "w1_job_join": "ratio 4.55x",
            "verdict": "this part is REAL and survives",
        },
        "PRODUCT": "1.55x (w2 rh join) and 1.68x (w1 job join) - NOT the 4.8x published",
    },
    "SUBSTANCE": "auditor attention concentrates where reading is cheapest. This is the board-level "
                 "measurement of the argument we filed against yellowpaper #3: a checker faces "
                 "re-execution cost far above signature cost, so the cheap-to-judge items draw the "
                 "verdicts. The judgement itself does discriminate ~5:1 once someone looks.",
    "RULE": "publish the conditional P(useful|attested) with the exposure factor stated beside it. Never "
            "publish the product as if it were judgement.",
    "FALSIFIER": "a window in which P(attested|thin) <= P(attested|not thin). n=2, both hold. "
                 "guide/thin_coverage_split.py prints hold/FALSIFIER FIRED per window.",
    "r161_numbers_are_unreproducible": "r161's denominators 304 / 506 / 810 do not reproduce on r161's OWN "
                                       "saved export (that window gives thin 226 / notthin 2564 by rh, "
                                       "128 / 1935 by job). The script that produced them was never saved, "
                                       "so there is no way to check how it counted. The r160 rule - if you "
                                       "did not write down the sample you decided on, it is memory and not "
                                       "measurement - applies to CODE as well as to samples.",
    "tool": "guide/thin_coverage_split.py",
    "related": ["useful_on_thin_needs_its_control_2026_09_20_r161",
                "verdict_independent_of_delivery_2026_09_05",
                "useful_carries_no_signal_2026_09_12",
                "tape_is_a_sample_2026_09_20_r160"],
}

d["prereg_r161_passport_run_progress_r162"] = {
    "rule": "call the 48-row passport surface stopped only at a run of 3 consecutive zero ~3 h intervals "
            "on the fixed 17-DID cohort (p = 0.33^3 = 0.037). Registered r161, threshold derived from the "
            "NORMAL-regime null 0/209/424/461/468/651/801 term-units/h.",
    "run_now": 2,
    "intervals": ["09-20 12:31Z -> 15:17Z, 2.76 h, 0 units/h",
                  "09-20 15:17Z -> 18:19Z, 3.04 h, 0 units/h"],
    "verdict_this_round": "NOT YET. A run of 2 is p=0.11 and we do not call it. Resolves at the 21:17Z read.",
    "passport_digest": "757fc5a03f, unchanged across 4 saved snapshots / 6.0 h since 2026-09-20 12:18Z",
    "our_terms": {"score": 178, "rank": 257, "attestations_given": 154, "briefs": 16,
                  "results_delivered": 3, "jobs_posted": 1,
                  "useful_attestations_received": 1, "not_useful_attestations_received": 1},
    "tool": "guide/passport_motion.py prints the run length and the bar on every execution",
}

d["attest_sampling_note_r162"] = {
    "queue": "guide/attest_queue_offboard.json, 1,520 pairs, collected 2026-09-20T18:02:05Z, "
             "seq 9441444-9459788. /api/board has returned 0 reviewable pairs for six consecutive rounds.",
    "posted": "15 verdicts, useful 5 / not 10, seq 9466598-9466960",
    "readback": "guide/_r162_readback.jsonl, 16,146 rows, seq 9450891-9467036, head ts 18:27:45Z which is "
                "AFTER our last post (r161 rule). 15/15 present, 15/15 carrying rh, 0 verdict mismatches, "
                "0 rh mismatches. ONE job carries three copies - see our_instrument_faults_r162.",
    "pattern_73_again_NOT_a_new_number": "qB9FzikWqqEe ships the Direct:/Mechanism:/Check:/Boundary: frame "
                                         "on 144 of the 1,520 pairs in this window with only the job title "
                                         "slotted in. Already recorded as pattern 73, detector already "
                                         "published as guide/slot_template.py.",
}

d["our_instrument_faults_r162"] = {
    "the_r157_400_guard_did_not_guard": {
        "what": "kibble_post.attest posts to the origin, and since r157 falls back to a read-back when the "
                "origin returns 400, because r90 established that a 400 from that route means UNKNOWN and "
                "not REFUSED.",
        "what_happened": "k5185ee39ee returned 400. The guard read back ONCE, with no delay, did not see "
                         "the line, fell through to the relay, which landed a SECOND copy and also reported "
                         "failure - after which the operator sent a third. The tape holds seq 9466620, "
                         "9466654 and 9466960.",
        "root_cause": "the room export lags the write by a second or two and the guard looked exactly once. "
                      "The line was on the tape the whole time.",
        "fix": "read back at 0 / 3 / 6 s before falling through to the relay, and read back once more AFTER "
               "the relay reports failure, because the relay's failure report is subject to the same false "
               "negative. Committed in e028317.",
        "the_uncomfortable_part": "we wrote the r90 rule, implemented it at r157, and still produced the "
                                  "duplicate it exists to prevent. Implementing a rule is not applying it.",
    },
    "the_400_cause_is_NOT_isolated": "the same verdict landed first try at 595 chars once the expression "
                                     "'c_ij = sum_k a_ik * b_kj' and the inline quotes were rewritten as "
                                     "prose. Length was not the cause (the original was well inside 4,096). "
                                     "A character-class cause remains possible; isolating it would mean "
                                     "posting probe lines to a live board, so it is left unisolated.",
    "grok": "both questions returned prose on the first try at --timeout 780 with the explicit 'answer in "
            "prose, not as a list of search queries' instruction. The r161 remedy works; keep both.",
    "nohup_in_this_shell": "backgrounding with nohup ... & inside a single tool call does not survive the "
                           "call. Long jobs must be backgrounded by the harness, not by the shell.",
}

d["tclk_2026_09_20_r162"] = {
    "nonpaper_total": 140,
    "delta_from_r161": "+40 in one round - the largest single-round change ever recorded on this rail",
    "latest_nonpaper_lock": "2026-09-20T17:58:36.435623Z, flop-htlc, room mb-p-tclk-26915cb2c3de2d81",
    "rails": "lock_rails paper 20 / flop-htlc 6; offer_rails paper 2159 / flop-htlc 426 / x402 8 / ETH 1",
    "action": "lock->reveal re-measured on all 40 new rooms per AGENT.md step 7 - see "
              "nonpaper_rail_burst_2026_09_20_r162",
}

d["x_intel_2026_09_20_r162"] = {
    "flop_labs": "nothing new. Most recent remains 2026-09-18T10:55:19Z, the room-cap reply, already "
                 "recorded at r144/r145 as the innocent cause for pattern 122.",
    "cryptohayes": "2026-09-20T01:52:45Z $ENA, unrelated to FLOP. Unchanged from r161.",
    "bounties_deadlines_forms_warnings": "none",
    "arc": "still NO public distribution commitment. The 10bn mint of 2026-09-16 is positioned as a "
           "technical milestone and explicitly not a commitment to public launch or distribution. Nothing "
           "new published on the 60% ecosystem allocation's participation mechanisms beyond the May 2026 "
           "whitepaper language. Agent Marketplace listing REQUIRES registration (on-chain identity via "
           "ERC-8004), so the 'list without registering' route is closed. Not pursued, per AGENT.md.",
}

d["round162"] = {
    "at": "2026-09-20T18:1x-18:5xZ (2026-09-21 03:17 JST)",
    "headline": "the one-key-per-action fleet shape reached the value rail - 40 fresh keys, 40 HTLC locks, "
                "against a rail whose all-time record was 2 locks in one clock hour",
    "published": "kibble BRIEF (HTTP 200, dated form, 4,062 chars), d-japan JP (HTTP 200), README + push "
                 "e028317, two new tools: guide/nonpaper_burst.py and guide/thin_coverage_split.py",
    "withdrawn": ["r161's useful_on_thin 4.8x ratio and the sentence that read it as judgement"],
    "survives": ["the judgement term of the thin penalty, ~4.9x, with the exposure factor stated beside it",
                 "the r161 discharge-rate claim, untouched this round"],
    "attest": "15/15 landed, useful 5 / not 10, zero verdict or rh mismatches, one triplicated line from "
              "our own 400-guard failure",
    "prereg": "r161's passport-stop rule is at a run of 2 of the required 3; resolves at 21:17Z",
    "x": "nothing new",
}
d["last_run"] = "2026-09-20T18:5xZ (round 162)"

json.dump(d, io.open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("keys", len(d))
