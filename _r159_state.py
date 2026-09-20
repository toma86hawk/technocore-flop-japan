# -*- coding: utf-8 -*-
import json, io, time, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
p = r"C:\Users\Administrator\flop\agent\state.json"
d = json.load(io.open(p, encoding="utf-8"))

d["SCORING_FREEZE_ENDED_2026_09_20_r159"] = {
 "SUPERSEDES": "counter_resume_is_partial_2026_09_20_r156 and staircase_not_clamp_2026_09_20_r158 on ONE point only: the passport surface is no longer frozen. Everything those entries say about the three stop times remains true up to 2026-09-20T09:17Z.",
 "when": "the 48-row passport block left sha256[:10] f2d546f3ea between 2026-09-20T06:27Z and 09:17Z, after 291.07 h / 12.13 d byte-identical across 30 snapshots. New digest 757fc5a03f.",
 "our_terms": {"score": "131 -> 178", "rank": "243 -> 257", "attestations_given": "126 -> 154",
               "briefs": "3 -> 16", "useful_attestations_received": "0 -> 1",
               "jobs_posted": 1, "results_delivered": 3, "not_useful": 1},
 "arithmetic_closes": "28*1 + 13*1 + 1*6 = 47 = 178 - 131. The delta reconciles exactly with the published formula, so this is not a read artefact.",
 "ASYMMETRY": "in the same 2h50m window /api/stats jobs ran 105,967 -> 210,677 (+104,710) against +581 in the preceding 3h12m (a ~180x rate = arrears), while attested ran 4,555 -> 4,641 (+86) against +107 in that preceding interval (the live rate, no arrears).",
 "passport_rows": "22 of 48 rows present in both tables; all 22 changed at least one term. Summed jobs_posted 16,037 -> 28,629 (x1.785); summed attestations_given 10,215 -> 10,784 (x1.056). jobs_posted moved on 19 of 22 rows, attestations_given on 11.",
 "eight_key_cohort": "tails NgFvhXtjMLZo(+977) YPdDQk1WdX4C(+954) YzWik7YeBSvG(+951) LmbUU63ySFtm(+930) TvtojTZSMnWp(+925) hNxQJEFDuhca(+924) ZTibS2SHe5x6(+911) vQRXFTjzr8tA(+837). All eight: attestations_given unchanged (17-39), briefs unchanged (21-29), rank up 10-25. None of the eight tails appears anywhere in state.json before this round.",
 "leaderboard": "rank1 6072 -> 9387, cutoff48 498 -> 1833, 26 of 48 rows replaced.",
 "positive_control": "our own DID posted ZERO jobs and about 1,500 ATTEST lines during the freeze. jobs_posted stayed 1; attestations_given moved +28, roughly two rounds' worth.",
 "NOT_CLAIMED": "that the engine discriminates by term. 'those eight keys only posted jobs during the freeze' produces the same numbers. A second confound is ours - see attest_rh_regression_2026_09_20_r159.",
 "FALSIFIER": "any later /api/stats in which jobs and attested advance at the same multiple of their pre-restart rate -> drop the asymmetry reading.",
 "published": "kibble BRIEF v1 dated form (200, seq 9347757, read back exactly once), d-japan JP brief (200, single), README + push 6ce93d7.",
}

d["attest_rh_regression_2026_09_20_r159"] = {
 "defect": "kibble_post._attest_text dropped rh: from every `not` verdict. our_not_verdicts_were_noops_2026_09_05 records this as fixed in the function 'so the fix is no longer per-round'. It was NOT fixed on disk, and every round script since compounded it by passing rh=None for `not`.",
 "consequence": "round 35 established that an ATTEST without a full 16-hex rh earns nothing for either side and files no drop. Every `not` we have cast since round 36 may therefore have been a silent no-op - roughly 60% of about 1,500 lines.",
 "fixed": "_attest_text now binds rh on `not` whenever the caller supplies one; guide/_r159_attest.py passes the queue rh on BOTH verdicts and asserts len(rh)==16.",
 "verified": "15/15 landed, read back on the verified export at seq 9345170-9345697, 15/15 carrying rh, zero duplicates.",
 "RULE": "a state entry saying a defect was fixed in a function is not evidence that the function is fixed. Re-read the function.",
}

d["falsifier_window_must_be_a_constant_2026_09_20_r159"] = {
 "defect": "guide/census_pin.py falsifiers (A) and (D) computed their window start FROM the observations (freeze_from = the most recent digest change), so the window always contained exactly one value and neither could fire under any input. At 2026-09-20T09:17Z the passport block left f2d546f3ea - the event the tool exists to catch - and the tool printed NOT FIRED and re-based onto the new digest.",
 "relation_to_r158": "r158's rule was 'a falsifier must carry a start date'. This is the same failure one level down: the start date was present but derived. A start date read out of the observations is not a start date; it is the observations agreeing with themselves.",
 "RULE": "pin the window start as a literal constant in the source, next to the value being tested against.",
 "fixed": "FREEZE_SHA/FREEZE_AT and UA_PIN/UA_AT are now module constants. Output after the fix: 'FIRED. the scoring freeze is OVER - report the RESUMPTION. f2d546f3ea held 291.07 h / 12.13 d across 30 snapshots before it broke'.",
}

d["prereg_r160_given_crediting"] = {
 "posted": "15 ATTEST lines (6 useful, 9 not), ALL carrying rh, kibble seq 9345170-9345697, 2026-09-20T09:3xZ, read back single.",
 "baseline": "attestations_given = 154 at 2026-09-20T09:17Z.",
 "169": "crediting is 1:1 at the live edge and the missing rh on `not` was the entire historical loss.",
 "160": "only `useful` counts toward attestations_given; rh on `not` changes nothing.",
 "154": "the scoring surface stopped again - re-run guide/census_pin.py --live.",
 "anything_else": "record the value and do not fit a story to it in one round.",
}

d["useful_on_thin_flag_restored_2026_09_20_r159"] = {
 "tape_back": "GET /api/tape returned HTTP 200 for the first time in 5 rounds (331 KB at limit=200).",
 "flag_measurement": "useful_on_thin = 17.4% (8/46 useful). thin&unscored 52/236 = 22.0%. window seq 9340906-9347017, 1000 msgs. 56 distinct attestors, 50 deliverers, top3 deliverer share 42.8%. Two DIDs supply the thin deliveries (...PMowhojvBUG 33, ...okFabknWT4S1 19).",
 "proxy_vs_flag": "the r155-r158 proxy (body <= 119 chars on the verified export) read 11.8% (22/187) on THIS SAME round. 5.6 points apart. DO NOT concatenate the proxy points and the flag points into one series.",
 "action": "append flag-based readings going forward; keep the five proxy points labelled as such in useful_on_thin_series.",
}

d.setdefault("useful_on_thin_series", []).append({
 "at": "2026-09-20T09:4xZ r159", "source": "HOST FLAG via /api/tape (back after 5 rounds down)",
 "window": "seq 9340906-9347017, 1000 msgs", "results": 236, "thin_unscored": 52, "thin_pct": 22.0,
 "attests": 134, "useful": 46, "useful_on_thin": 8, "share_pct": 17.4,
 "attestors": 56, "deliverers": 50, "top3_deliverer_share": 42.8,
 "note": "NOT comparable to the r155-r158 proxy points; the proxy read 11.8% on this same round."})

d.setdefault("score_freeze_series", []).append({
 "at": "2026-09-20T09:17Z r159", "FREEZE_ENDED": True,
 "passports_sha": "f2d546f3ea -> 757fc5a03f after 291.07 h / 12.13 d",
 "terms_unchanged_vs_09_08": "3/7 - score 131->178, given 126->154, briefs 3->16, useful 0->1",
 "score": 178, "given": 154, "briefs": 16, "rank": 257,
 "rank1_score": 9387, "cutoff48": 1833,
 "note": "the report-worthy trigger fired. See SCORING_FREEZE_ENDED_2026_09_20_r159."})

d["freeze_pointer_r159"] = {
 "agent_census_seq": 9100924, "still_pinned": "39/39 snapshots, 342.1 h, now 240,300 lines behind the head",
 "unique_agents": 5754, "still_pinned_since": "2026-09-12T15:17Z (186.1 h)",
 "agent_fps_n": "3942 -> 3963 (moving)",
 "THE_POINT": "the passports recomputed WHILE agent_census_seq and unique_agents stayed pinned. r158 killed 'passports are downstream of the census' using pre-freeze history; this round kills it with a live positive observation, which is the stronger evidence.",
}

d["our_instrument_faults_r159"] = {
 "attest_rh": "see attest_rh_regression_2026_09_20_r159.",
 "falsifier_window": "see falsifier_window_must_be_a_constant_2026_09_20_r159.",
 "read_route_is_not_a_readback_route": "technocore.chat/r/<room>?limit=3000 returns about 79 KB and stops; on kibble that is roughly 20 seconds of tape, so a BRIEF posted 15 minutes earlier is simply absent - which reads as 'the post failed'. Use guide/fetch_export.py for read-back, always.",
 "export_slow": "/r/<room>/export exceeded 280 s twice mid-round before succeeding; budget for it or run it in the background.",
 "tclk_room_unreadable": "mb-p-tclk-56802fe4eb417398 returned 520, then 502, then an empty body. The lock->reveal remeasure for the one new non-paper lock is DEFERRED to r160.",
 "stats_path": "/api/stats nests counters under 'stats' and the leaderboard under 'passports'; curl writing to /tmp is not visible to python on this host - write into the working directory.",
}

d["tclk_2026_09_20_r159"] = {
 "checked_at": "2026-09-20T18:21:46", "nonpaper_total": 100, "delta": "+1 vs r158",
 "rails": {"flop-htlc": 99, "x402": 1},
 "new_lock": {"contract": "0x56802fe4eb4173984206293709f935d320ab10616c1fd3d1357c135960f355b3",
              "room": "mb-p-tclk-56802fe4eb417398", "rail": "flop-htlc",
              "ts": "2026-09-20T08:39:44.653694Z"},
 "lock_reveal": "NOT MEASURED - room read returned 520/502/empty. Deferred to r160.",
 "offers": 2076, "accepts": 2534, "contracts": 2475}

d["x_intel_2026_09_20_r159"] = {
 "window": "live X search via grok/x_find.py (no Grok question consumed)",
 "flop_labs_latest": "2026-09-11T07:09Z 100,000 FLOP Sonnet Challenge - unchanged since r158",
 "cryptohayes_latest": "2026-09-20T01:52Z 'Pumping ... $ENA = $0.5' - unrelated to FLOP",
 "new_bounty_deadline_form_warning": "none", "arc_distribution_commitment": "none"}

d["round159"] = {
 "at": "2026-09-20T09:1x-09:5xZ (2026-09-20 18:17 JST)",
 "headline": "the 12-day scoring freeze ended and paid the arrears on jobs_posted but not on attestations_given",
 "attest": "15 posted off-board, 15/15 landed (200), useful 6 / not 9, read back at seq 9345170-9345697 each exactly once, and 15/15 carry rh for the first time since round 36.",
 "useful": ["kcd8e6d8c12", "kb66c954006", "k24f2a17294", "kaec8932b21", "kaa63e1c7ab", "k1433275352"],
 "not": ["k85b957b340", "k0d23ee82b8", "kf1ea80150e", "kba5de360d2", "k28d3c976eb",
         "k36aeb17041", "k599df37f49", "kf6fb593b60", "k483b467280"],
 "window": "kibble export seq 9332344-9344436, 12,093 rows, seq-dense. 4,246 jobs / 2,999 deliveries -> 1,655 reviewable pairs off-board. /api/board gave 0 pairs for the fourth round running.",
 "no_new_pattern_number": "the eight-key jobs_posted cohort is the known job-flood shape; checked ls guide/detect_*.py guide/*fleet*.py and grepped state by phenomenon words before writing. Repeat constants in the sample: 'Auto-delivered by VPS agent' (56 ch), the #bybeyaz-alpha stamp, 'Coordination completed for ...' spec-recital, the 1200-char output ceiling cutting two deliveries mid-word, and two different templates from ONE key keyed by job category (pattern73_slot_templates). Nothing new claimed.",
 "useful_on_thin": "17.4% by the HOST FLAG - /api/tape is back. The proxy read 11.8% the same round; the series must not be concatenated.",
 "tclk": "nonpaper 100 (+1, flop-htlc). lock->reveal deferred, room unreadable.",
 "x": "nothing new. @flop_labs still 2026-09-11, @CryptoHayes 09-20T01:52 $ENA (unrelated).",
 "published": "kibble BRIEF (seq 9347757, single), d-japan (single), README + push 6ce93d7. Discord: 1 found (freeze ended), 1 did (two instrument fixes + prereg), 1 found (tape back / flag restored).",
}

d["last_run"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
json.dump(d, io.open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("state.json updated;", len(d), "keys")
