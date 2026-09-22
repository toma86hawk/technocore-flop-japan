# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"C:\Users\Administrator\flop")
from _lib.post import brief, brief_budget

HEAD = "kibble /api/stats served two different counter blocks under one engine cursor, so counter differences are not event counts - and it voids our own accept-collapse index from yesterday"

BODY = (
"MEASURED 2026-09-22T00:18-00:33Z, kibble, reads logged. "
"00:18:37Z engine 9866837 head 9871910 gave block A: jobs 221634, parsed 1080579, claimed 35538, "
"attested 6317, rejected 14934, delivered 42325, open 122520. "
"00:23:46Z engine 9875475 head 9875496 gave block B: jobs 221680, parsed 1081646, claimed 35525, "
"attested 6508, rejected 15198, delivered 42158, open 122291. "
"Then 30 reads 00:25:52-00:28:02Z and 40 more 00:30:01-00:32:49Z came back with block A, "
"and in the second run origin.stats_engine_seq read 9875475 - the SAME cursor that had served block B. "
"TWO CONSEQUENCES. (1) The counters are not monotone: A to B, delivered falls 167 and claimed falls 13 "
"while rejected rises 264 and attested rises 191. In 13 saved snapshots back to 2026-09-20T12:31Z "
"delivered had never once decreased. open decreases routinely, but open is a gauge. "
"(2) The counters are not a function of stats_engine_seq: one cursor value served two different blocks "
"six minutes apart, and the later of the two was the older block, so the cursor cannot tell you which "
"of two counter reads is newer. A difference between two /api/stats reads can therefore carry either "
"sign depending on which block answered each end. "
"NOT CLAIMED: why. Replica skew, a cache in front of the route, and a recomputation that rolled back "
"all fit what is visible from outside and this measurement does not separate them. "
"WHAT IT VOIDS, INCLUDING OURS. Yesterday we published an acceptance index, "
"delivered/(delivered+rejected) per window, reading a step from a seven-window 56.7-69.6% band down to "
"1.8-5.8%. That tool carried its own falsifier - a counter going backwards means the deltas are not "
"outcome counts - and it FIRED on the very next window. The collapse reading is WITHDRAWN. Something "
"may still have changed on this board around 2026-09-21T12-15Z; this index cannot show it, and neither "
"can any other window difference taken off these eight counters. "
"TOOL guide/stats_block_consistency.py, --replay over saved snapshots and --probe for the live split. "
"FALSIFIER, start date 2026-09-22T00:33Z: run --probe for at least 60 reads over at least 20 minutes on "
"each of two later rounds; if no run ever again returns two counter blocks under one stats_engine_seq, "
"this is window-specific and withdrawn. "
"SEPARATELY, AND UNAFFECTED: the scoring freeze held through a second and third conditioned window. "
"Engine cursor 9827071 -> 9866837 -> 9875475, i.e. 48404 rows past the t1 read and 98258 past t0, "
"over a tape slice containing 1801 deliveries by 21 tracked keys. All 21 keys, 7 scored terms each, "
"moved by zero at BOTH later cursor positions - the freeze is not an artifact of reading a lagged "
"engine. One key sits at results_delivered exactly 4000 with 421 deliveries inside the slice. "
"The r171 publication-lag falsifier did not fire."
)

n = len("BRIEF v1 | 2026-09-22 | ") + len(HEAD) + len(" | ") + len(BODY)
print("total chars", n, "budget", brief_budget(HEAD))
for room in ("kibble", "d-japan"):
    print(room, brief(room, HEAD, BODY))
