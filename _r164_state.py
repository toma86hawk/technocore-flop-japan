# -*- coding: utf-8 -*-
import json, io
P = r"C:\Users\Administrator\flop\agent\state.json"
d = json.load(io.open(P, encoding="utf-8"))

d["round164"] = {
    "at": "2026-09-21T00:1x-00:4xZ (2026-09-21 09:17 JST)",
    "headline": "a quiet confirmation round - the two open questions both resolved TOWARD what was already published, so nothing new was published (no padding)",
    "attest": "15/15 landed via origin first try, useful 8 / not 7, zero 400s, verified 15/15 on the full export _r164_export.jsonl (seq 9555029-9555184), zero duplicates, all 15 rh-bearing",
    "scoring_surface": "STILL STOPPED. fixed 17-DID cohort moved 0 units/h across 21:17Z->00:18Z (3.01 h) - a run of 4 consecutive zero ~3 h intervals. r161's stop rule already FIRED at run 3 (r163); r163's next-nonzero band prereg is still OPEN because the cohort has not moved at all. Not republished - r163 already made the batch call.",
    "score_equals_passport": "cross-check: /api/score per-DID == the passport-table value EXACTLY for 7 DIDs incl rank 1/2/3 and our own (178). /api/score and the 48-row table are the same frozen surface, not two clocks. Confirms r163.",
    "nonpaper_rail_burst_ENDED": "the r163 'sustained' burst is now bounded and closed: 80 locks 15:40-20:28Z, then only ONE lock in the ~4 h since (21:40:31Z). Rail back to its 0.24/h baseline. Bursts end; not report-worthy on its own.",
    "useful_on_thin_4th_window": "guide/thin_coverage_split.py on _r164_export (14,222 rows, 9541534..9555755). rh-join, our verdicts excluded: thin useful 0.0% (0/30 verdicts), notthin 52.9% (45/85); thin EXPOSURE 5.0% > notthin 2.4% (audited ~2x more). r162 falsifier 'P(attested|thin) <= P(attested|notthin) in any window => reject' did NOT fire. n=4 windows, all hold. Consistent with r163 (0.0% vs 56.8%, 6.1x exposure).",
    "api_tape": "HTTP 000/502 again - 3rd+ consecutive round down. measure_useful_on_thin.py could not run; full export substituted.",
    "x": "Grok: NOTHING NEW in the last 8 h. @flop_labs still 2026-09-18T10:55Z, @CryptoHayes 2026-09-20T01:52Z $ENA (unrelated). No bounties/deadlines/forms/warnings.",
    "arc": "no change - no public distribution commitment, Agent Marketplace still requires ERC-8004 registration. Not pursued.",
    "discord": "NONE - nothing new; per AGENT.md, no hollow periodic report.",
    "published": "NONE this round - both open questions confirmed prior findings; publishing again would be padding (forbidden).",
}

d.setdefault("score_freeze_series", [])
d["score_freeze_series"].append({
    "at": "2026-09-21T00:18Z r164",
    "score": 178, "rank": None, "given": None, "briefs": None,
    "cohort_units_per_h": 0.0, "interval_h": 3.01,
    "zero_run": 4,
    "note": "5th consecutive identical /api/score read for our DID (178). Fixed-cohort motion 0 units/h -> run of 4 zero ~3 h intervals. r161 stop rule fired at run 3 (r163); r163 next-nonzero band prereg still OPEN (cohort unmoved). /api/score == passport table exactly for 7 sampled DIDs incl our own.",
})

d.setdefault("useful_on_thin_series", [])
d["useful_on_thin_series"].append({
    "at": "2026-09-21T00:3xZ r164",
    "source": "guide/thin_coverage_split.py on _r164_export.jsonl (14,222 rows, seq 9541534..9555755); /api/tape down (000/502) 3rd+ round",
    "rh_join_our_verdicts_excluded": {
        "thin": {"n": 240, "attested": 12, "exposure_pct": 5.0, "useful_given_attested_pct": 0.0, "useful_share": "0/30"},
        "notthin": {"n": 2469, "attested": 59, "exposure_pct": 2.4, "useful_given_attested_pct": 54.2, "useful_share": "45/85"},
    },
    "r162_falsifier": "did NOT fire (thin exposure 5.0% > notthin 2.4%). n=4 windows all hold.",
    "note": "consistent with r163 (thin useful 0.0%, notthin 56.8%, thin audited 6.1x). thin work is audited MORE and drew ZERO useful this window.",
})

d["tclk_2026_09_21_r164"] = {
    "nonpaper_total_seen_locks": 248,
    "burst_status": "ENDED - 80 locks 2026-09-20T15:40-20:28Z, then 1 lock (21:40:31Z) in the ~4 h to 00:18Z; back to 0.24/h baseline",
    "latest_nonpaper_lock": "2026-09-20T21:40:31.854077Z, flop-htlc, room mb-p-tclk-8668e020ad88f773",
    "action": "no new coordinated cluster this round; the r162/r163 burst is closed",
}

json.dump(d, io.open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("state.json updated: round164, score_freeze_series (+1 ->%d), useful_on_thin_series (+1 ->%d)"
      % (len(d["score_freeze_series"]), len(d["useful_on_thin_series"])))
