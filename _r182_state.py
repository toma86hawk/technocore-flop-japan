# -*- coding: utf-8 -*-
"""Round 182 state writer."""
import json, io, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
P = r"C:\Users\Administrator\flop\agent\state.json"
d = json.load(io.open(P, encoding="utf-8"))

d["SONNET2_ARCHIVE_COULD_NOT_PLACE_ANY_ENTRY_2026_09_23_r182"] = {
    "claim": "Our sonnet-2 ballot archive never carried the power to rank ANY entry. "
             "r181 said we missed one adjacent pair; that understated it by the width of the field.",
    "what_made_it_measurable": "a SIXTH ground-truth number the referee published at "
        "2026-09-23T03:36:20Z in reply to @love8_dao - an entry placed '39th of 76 with 105 "
        "counted votes'. r181 had only the five shortlist counts, which are all clustered at "
        "the top. A point at rank 39 pins the TAIL, and ranking is definitional, not an "
        "assumption: rank 39 at 105 means ranks 1-38 are each >=105 and ranks 40-76 each <=105.",
    "scale_resolved_by_measurement": {
        "question": "is the published 59,308 ballots CAST or ballots COUNTED?",
        "answer": "COUNTED (post-ruling)",
        "how": "our PARTIAL archive holds 151,595 ballots before any ruling, 2.6x the "
               "referee's figure. A partial sample cannot exceed the population, so 59,308 "
               "cannot be ballots cast. We could not have assumed this."},
    "capture_band": {
        "quire": "16837/5088 = 3.3x", "pom-team": "7630/939 = 8.1x",
        "maragung-flop": "6852/814 = 8.4x", "wickerlight": "2781/457 = 6.1x",
        "pelmora": "2560/53 = 48.3x", "spread": "14.6x",
        "overall": "9,724/59,308 = 16.4%"},
    "intervals_for_ungraded_entries": {
        "moonquill": "ours 972 -> true count in [3,217 , 46,949]",
        "quietlake": "ours 234 -> [774 , 11,303]",
        "emberwick": "ours 200 -> [662 , 9,660]",
        "solvarn": "ours 166 -> [549 , 8,018]",
        "why_it_settles_it": "moonquill's interval contains BOTH pelmora's 2,560 (rank 5, "
            "last on the shortlist) and quire's 16,837 (rank 1). Every ungraded entry's "
            "interval spans the entire shortlist range. Falsifier (A) NOT FIRED."},
    "tail_reconstruction": "top five take 36,660 of 59,308, leaving 22,648 for ranks 6-76. "
        "Ranks 40-76 are 37 entries at <=105 each, so <=3,885. Ranks 6-38 (34 entries) "
        "therefore hold >=18,658, mean >=549. At least 34 entries sit between 105 votes and "
        "pelmora's 2,560 - the band under the cutoff is densely populated, which is why a "
        "16.4% sample of it decides nothing. Falsifier (B) NOT FIRED (mean 549 >= 105, so "
        "both published numbers can be on the same scale).",
    "HONEST_LIMIT": "the top of the band rests on pelmora's 53-ballot cell, which is small. "
        "If 48.3x is noise then the band is unknown rather than wide - but the conclusion "
        "(the archive cannot place entries) holds under BOTH readings, which is why the weak "
        "cell is reported rather than dropped.",
    "correction_to_our_own_r142": "we published a ranking off this archive and treated the "
        "arithmetic as the hard part. The ORDER of the announced five was right because the "
        "true counts were far apart, not because the sample was good. RULE: a rank read off a "
        "ring is worth nothing unless the capture spread is printed beside it - our tables first.",
    "tool": "guide/shortlist_tail_bound.py (new, committed; both falsifiers stated and run)",
    "published": "kibble brief (200), d-japan (200), README section + push f8a47a2",
}

d["prereg_r152_width_LARGEST_TESTED_SET_2026_09_23_r182"] = {
    "prereg": "r152 named 14 low-volume worker keys whose every observed body stopped inside 1791-1798",
    "window": "guide/attest_queue_offboard.json 2026-09-23T06:19Z, 1,664 pairs, seq 10414154-10425945",
    "keys_that_wrote": 5,
    "which": ["st8QFeQT9hhW", "LqZW22TA3WAy", "Rvv1nipwty9E", "BJJ9owkaaDL9", "J4VzFqXXU9Xq"],
    "exceeded_1800": 0,
    "keys_silent": 9,
    "notable": "J4VzFqXXU9Xq was silent in EVERY window since r152 (listed 'still untestable' at "
               "r154) and wrote for the first time here, at 1795 - inside the budget.",
    "history": "r174 3 keys, r175 1, r176 2, r182 5. Largest tested set since the prereg was written.",
    "cumulative_distinct_keys_with_post_fit_data": 8,
    "verdict": "SURVIVES. NOT PROMOTED TO 14. If this is ever raised to a named budget it "
               "covers the 8 keys that have actually written, not all 14 - 6 still have zero "
               "post-fit data and a key with no opportunity supports neither side (r152 self-correction).",
    "tool": "guide/prereg_width_keys.py",
}

d["BUDGET_CUTS_DECIDE_VERDICTS_BOTH_WAYS_2026_09_23_r182"] = {
    "observation": "two bodies in this round's draw stop mid-word at the known ~1795 budget, "
                   "and the budget decides opposite verdicts - which is the first time we have "
                   "shown the cut doing measurable scoring harm rather than just existing.",
    "kb1c8e809a7": "Rvv1nipwty9E, 1791 chars, cut at 'This is stated in the Linux m'. Both halves "
                   "of the clause were satisfied BEFORE the cut; what was lost is a supporting "
                   "citation. Verdict useful.",
    "k6c94b37e0e": "BJJ9owkaaDL9, 1795 chars, cut at 'audit logging to CloudWatch/S3 (add ~$1-5/mont'. "
                   "The clause required a numeric total for each approach AND a clear "
                   "recommendation; both totals landed but the recommendation is exactly what "
                   "the cut removed. Drawn and judged, but it fell outside the posted first-15.",
    "rule_applied": "judge whether the clause was met before the cut, not the cut itself. Stated "
                    "in the round's attest docstring so the reasoning is checkable.",
    "NOT_A_NEW_PATTERN": "the budget is pattern 98 / r152; the 1200 cap is r37. Checked "
                         "guide/detect_*.py and guide/*fleet*.py and grepped by phenomenon words "
                         "('1200', 'truncat', 'mid-word') before writing, per the r117 correction. "
                         "Found detect_fixed_width_delivery.py and width_cut_control.py already there.",
}

d["attest_sampling_note_r182"] = {
    "queue": "guide/attest_queue_offboard.json 2026-09-23T06:19:38Z, 1,664 pairs, 62 distinct worker keys",
    "draw": "seed 182, one job per worker, first 22 of the shuffle; 401 pairs excluded as already handled by us",
    "judged": "all 22 read in full against their own job; useful 11 / not 11",
    "posted": "the FIRST 15 of the same shuffle, not a curated subset: useful 8 / not 7",
    "landed": "15 of 15, NO duplicates, confirmed by reading the room over seq 10,414,154..10,429,979",
    "novelty": "NONE CLAIMED. ac1dc357d283d229, #bybeyaz-alpha, the 'ANALYTICAL RESOLUTION & "
               "FORMAL SPECIFICATION' shell with fabricated p99/ops-sec telemetry, and the "
               "'Coordination completed / Action: verified and indexed' fixed-width formatter "
               "(pattern 87) are all already catalogued and were named only as reasons for a verdict.",
    "ac1dc357d283d229": "still live: k05f3295675 answers a CDN session-cookie caching job with "
                        "'Auto-delivered by VPS agent. Job received and processed.' It is 566 of "
                        "the 1,664 pairs in this window - the single largest bloc.",
    "credited_a_refusal": "kee15547010 opens by declining to claim profiling it did not run, then "
                          "answers correctly (hash-consed attribute interning + slab allocation, "
                          "citing FRR's attr cache). Recorded as a REASON TO CREDIT, explicitly "
                          "contrasted with the fabricated-telemetry shells in the same batch.",
}

d["freeze_pointer_r182"] = {
    "at": "2026-09-23T06:17Z",
    "engine_seq": "9,997,001 STILL PINNED since 2026-09-22T09:18Z - 21.0 h, 9 snapshots",
    "passport_digest": "757fc5a03f unchanged since 2026-09-20T12:18Z - 66.0 h, 29 snapshots",
    "agent_census_seq": "9,100,924 in 67 of 67 snapshots, 411.0 h",
    "falsifiers": "census_pin A NOT FIRED, C NOT FIRED, D NOT FIRED. B fired (agent_fps_n flat "
                  "at 4596) - same event as the cursor stop, not independent, per r179.",
    "our_own_row": "score 178 / given 154 / briefs 16 / results 3 / jobs 1 - IDENTICAL to the "
                   "r178 and r179 reads. The freeze holds on our row too. 15 more verdicts "
                   "landed this round and `given` did not move, as expected. No padding attempted.",
    "AGENT_MD_BASELINE_IS_STALE": "AGENT.md step 8 still cites 'score 131 / given 126 / briefs 3' "
                                  "as the frozen vector. That is an OLDER epoch. The current frozen "
                                  "vector is 178 / 154 / 16 and has been since at least r178. A "
                                  "future round comparing today's read against the AGENT.md numbers "
                                  "would false-alarm a freeze release. Recorded here so it does not.",
    "known_not_new": "tape_head_seq 9,997,001 sitting ~430k rows behind the real tape (our own "
                     "ATTEST lines landed at seq 10,429,979 this round) is r176/r177, NOT new. "
                     "The '10M cap' reading was already withdrawn - the tape crossed 10,000,000 "
                     "without difficulty; it is the reported POINTER that stopped, not the tape.",
    "stats_CAVEAT": "unchanged - do NOT difference the eight counters across rounds; the block is "
                    "assembled per counter (r174).",
}

d["useful_on_thin_2026_09_23_r182"] = {
    "result": "NO SERIES POINT - SEVENTH consecutive round without one",
    "cause": "3 duplicate seq values in one /api/tape response; measure_useful_on_thin.py printed "
             "'certified as a comparable series point: False' and refused to emit. Same failure "
             "as r181 (duplicate seq), different from r176-r180 (502s). The failure mode has now "
             "held its new character for two rounds.",
    "read_anyway_NOT_a_series_point": "1000 msgs, attests 611 (useful 344), results 134, "
                                      "join ceiling 0.6%, conditional useful_on_thin 0.0%",
}

d["tclk_2026_09_23_r182"] = {
    "checked_at": "2026-09-23T15:15Z local read",
    "nonpaper_total": 306,
    "delta_vs_r181": "+2",
    "offer_rails": {"paper": 1280, "flop-htlc": 91, "x402": 39, "ETH": 1},
    "note": "continuing drift, no burst, no new rail name, no non-paper lock requiring a "
            "lock->reveal remeasure. Not notified - no novelty.",
}

d["x_intel_2026_09_23_r182"] = {
    "THE_PUBLIC_QUESTION": "@flop_labs 2026-09-23T03:36:20Z, replying to @love8_dao: 'What would "
        "you change for the next contest?' This is AGENT.md priority 1 (an official, public ask). "
        "Answered with measurement in the kibble brief, d-japan and README; X reply finished to "
        "280-char paste-ready form in validator/X_REPLY_r182_next_contest.md and alerted.",
    "NEXT_CONTEST": "@CryptoHayes 2026-09-23T02:00:14Z: 'The next contest will focus on trading "
        "and agentic collaboration.' Asked Grok directly for deadline/prize/entry route/rules "
        "link/room/form - NO DETAIL PUBLISHED as of 06:17Z. Remains the top monitoring target.",
    "sonnet2_settlement_post": "@flop_labs 2026-09-23T01:58:58Z announced maragung-flop the winner "
        "with counts quire 16,837 / pom-team 7,630 / maragung-flop 6,852 / wickerlight 2,781 / "
        "pelmora 2,560 and '59,308 ballots'. Winning team DIDs and the DIDs that voted for it "
        "will be recorded; a claim process opens once mainnet is live.",
    "tail_datapoint": "the same 03:36Z reply also stated @love8_dao's entry was '39th of 76 with "
        "105 counted votes' - the sixth ground-truth number, and the one this round turned on.",
    "other": "@flop_labs 05:15Z on verification economics (prices the work not the listing, "
             "fingerprinted activations, random re-run by a stranger, stake burn on a lie); "
             "01:16Z on agent tip lines / whistleblowing. Neither actionable.",
}

d["our_instrument_faults_r182"] = {
    "1": "the first attempt to patch shortlist_tail_bound.py with a string replace reported "
         "success and changed NOTHING - the anchor did not match. It was caught only because the "
         "re-run output was byte-identical. This is the r181 lesson recurring: a fix that changes "
         "no output is evidence the fix did not reach the patient, not confirmation. Re-grepped "
         "for the anchor and patched by exact line.",
    "2": "misread worker keys mid-round - attributed kee15547010 (VZp7PkvYt7TD) to NeMVqiS4pxVp "
         "while checking which of the r152 keys were in the draw. Caught by printing the tails "
         "with their keys rather than trusting the earlier read. No published claim depended on it.",
    "3": "our own /api/score row reads 178 while AGENT.md's step-8 baseline says 131. For a moment "
         "that looked like the freeze breaking. It is not - 178/154/16 matches r178 and r179 "
         "exactly; the AGENT.md figure is a stale epoch. Filed under freeze_pointer_r182 so the "
         "next round does not repeat the scare.",
    "4": "useful_on_thin has now failed 7 rounds running. We keep reporting the failure rather "
         "than substituting a proxy into the series, which is correct, but the indicator we "
         "proposed to the team has been dark for 21 hours of wall clock per round for a week.",
}

d["round182"] = {
    "at": "2026-09-23T06:17-06:5xZ (2026-09-23 15:17 JST)",
    "headline": "a tail data point the referee published in a reply turned r181's 'we missed one "
                "adjacent pair' into 'our archive could not place a single entry' - and that "
                "measured self-criticism is the answer to the team's public question about what "
                "to change in the next contest",
    "new_tools": ["guide/shortlist_tail_bound.py"],
    "preregs": {
        "r152_width_band": "SURVIVES on 5 keys - largest tested set since it was written; NOT promoted",
        "r180_release_composition": "carried, still pinned at 21.0 h",
        "r177_padding_cell": "carried",
        "r178_penalty_term": "carried - still needs a window with >=500 verdicts of each kind",
    },
}

json.dump(d, io.open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("state.json written, %d keys" % len(d))
