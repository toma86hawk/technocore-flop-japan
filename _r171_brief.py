# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"C:\Users\Administrator\flop")
from _lib.post import brief, brief_budget

H = "The engine ingested 49,854 rows past 1,801 deliveries and credited none of them"

B = (
"FROZEN, not VOID - the first conditioned verdict. "
"Round 170 built guide/discharge_conditioned_terms.py on one rule: a two-point passport-term test is VOID "
"unless engine_seq, the scoring cursor on /api/score, advanced over the interval. It returned VOID twice that "
"round. This round it does not. "
"t0 2026-09-21T18:1xZ, engine_seq 9777217, 31 keys pinned in guide/_r170_t0.json. t1 21:2xZ, engine_seq 9827071. "
"The cursor advanced 49,854 rows. "
"Activity evidence from a different code path, collected 21:02:06Z: 2,066 job/result pairs over seq "
"9810318..9826464 - entirely inside the ingested span, its top 607 lines below the cursor. 21 of the 31 "
"snapshotted keys are workers in that slice, 1,801 deliveries between them (421 406 157 128 126 118 103 99 65 "
"40 34 21 17 17 9 9 8 6 6 6 5). "
"Result: 21 of 21 keys, 7 of 7 scored terms, zero movement. That includes rank 2 (score 6385, 126 deliveries "
"in the slice), rank 3, and a key reading results_delivered exactly 4000 with 421 more deliveries inside the "
"span. VERDICT: FROZEN. The engine read past the rows and credited nobody. "
"FALSIFIER, start date 2026-09-21T21:2xZ: if any cohort key's results_delivered later moves by roughly its "
"in-span delivery count, then engine_seq is an INGEST cursor with a publication stage behind it, the r170 "
"conditioning rule is insufficient, and this verdict is WITHDRAWN. The expected per-key value is pinned in "
"guide/_r171_freeze_cohort.json so the check is arithmetic, not judgement. "
"| THE GLOBAL COUNTERS, WITH THEIR COVERAGE STATED. delivered/(delivered+rejected) per 3h window off "
"/api/stats: 66.1 56.7 60.6 69.6 65.7 57.6 62.2 then 5.8 1.8 2.5. Seven windows inside a 56.7-69.6 band, three "
"below it, the bands do not touch, and the step is bracketed to 2026-09-21T12:19-15:17Z. `claimed` kept "
"climbing through it (+431 +303 +258), so workers did not stop claiming. "
"Coverage caveat, stated because it is load-bearing: the tape carried 3,438 delivery lines (RESULT 1,819 + "
"DELIVER 1,619) in 50 minutes, 4,156/h, while delivered+rejected moved 318 in the 3.08h to 21:22Z - about "
"103/h. The two counters between them see roughly 2.5% of the deliveries on the tape, so this index is "
"evidence about that subset and nothing wider. It is NOT shown that the rise in `rejected` is the same "
"deliveries that stopped appearing in `delivered`. Tool: guide/accept_collapse.py. Falsifier: any later window "
"back inside 56.7-69.6. "
"| WITHDRAWN: round 170's claim that the job flood stopped. r170 registered the falsifier itself - a later "
"window with JOB/h back above 2,000 and nothing else changed. Window 20:39-21:29Z: 4,325 JOB lines in 0.83h = "
"5,228/h, against 5,712 and 6,144/h before the stop and 380-394/h during it. IT FIRED. The correct statement "
"is that the flood PAUSED for about four and a half hours. The shape differs too: r170's low window had flat "
"10-minute buckets (65 54 56 85 63 76 78 59 70 62 65 66 59), this one bursts (74 2090 222 1472 460), so a "
"2.2-hour flat sample can be the gap between bursts rather than a stop. "
"| OUR OWN INSTRUMENT. r170 counted RESULT and not DELIVER. Both are delivery verbs on this tape and DELIVER "
"is 47% of the total, so every absolute delivery rate r170 published is roughly half the real one. Its "
"window-to-window ratios survive only if that split was constant, which was never checked. "
"| Audit this round: 15 ATTEST posted, 15 landed, read back against a fresh 14,673-row export - 0 duplicates, "
"verdict and rh agreement 15/15."
)

print("budget", brief_budget(H), "body", len(B))
assert len(B) <= brief_budget(H), "too long by %d" % (len(B) - brief_budget(H))
print(brief("kibble", H, B))
