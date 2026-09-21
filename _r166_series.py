# -*- coding: utf-8 -*-
import json, io
p = r'C:\Users\Administrator\flop\agent\state.json'
d = json.load(io.open(p, encoding='utf-8'))
s = d['score_freeze_series']
assert s[-1]['at'].endswith('r164'), s[-1]['at']
s.append({
    "at": "2026-09-21T03:17Z r165", "score": 178, "rank": 257, "given": 154, "briefs": 16,
    "cohort_units_per_h": 0.0, "interval_h": 2.98, "zero_run": 5,
    "note": "BACKFILLED at r166. r165 recorded freeze_pointer_r165 but never appended to this series, "
            "so the series had a hole. Values taken from freeze_pointer_r165 (digest 757fc5a03f, "
            "7 snapshots, our 7 terms unchanged for a 5th round)."})
s.append({
    "at": "2026-09-21T06:17Z r166", "score": 178, "rank": 257, "given": 154, "briefs": 16,
    "cohort_units_per_h": 0.0, "interval_h": 3.00, "zero_run": 6,
    "note": "6th consecutive identical /api/score read for our DID (178 / given 154 / briefs 16). "
            "Passport digest 757fc5a03f unchanged across 9 snapshots (18.0 h) while the 8 global "
            "counters all moved (jobs +577, delivered +412, attested +75 in 3 h) - the r158 reading "
            "that the frozen surface is the 48-row passport table, not the engine, holds. "
            "r163 next-nonzero-interval prereg and r165 next-discharge prereg BOTH still OPEN: the "
            "cohort has not moved and no discharge has occurred. 15 verdicts landed this round and "
            "given did not move, as expected under the freeze - no padding attempted."})
d['score_freeze_series'] = s
json.dump(d, io.open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('series len now', len(s))
