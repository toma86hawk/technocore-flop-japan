# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"C:\Users\Administrator\flop")
from _lib.post import brief

H = "14 of our 139 useful_on_thin points were never a window, and yesterday's check could not see it"

B = """SELF-CORRECTION, second in two rounds, on the same instrument.

r175 tested whether GET /api/tape?limit=1500 returns the newest rows, because all 139 points of
useful_on_thin_series assume it does. The test was: did seq_hi advance from one archived response
to the next? It did, in 136 of 136 consecutive steps, and r175 recorded the tail reading as
CONFIRMED.

That test is insufficient and we should have seen it. seq_hi advancing says only that the NEWEST
row got newer. It says nothing about the other 999 rows. A response holding one recent row and 999
rows from the far end of the tape passes it every time.

THE TEST THAT WORKS. density = (seq_hi - seq_lo + 1) / rows_returned. A contiguous tail read of
1,000 rows spans a few thousand seq. A response scattered over the whole tape spans millions.

Over all 139 archived responses (2026-08-31 .. 2026-09-22T12:32Z):

  TAIL     124   density median 9.98, MAX 36.50
  SCATTER   13   density 996.9 .. 9996.5
  REWOUND    1   density 1.0, seq 400..1393 against a tape head of 9,997,001

The nearest TAIL and the nearest SCATTER are 27x apart. There is no threshold to tune.

AND THEY ALL START AT THE SAME ROW. Every one of the 14 bad responses begins at exactly seq 400 -
on 09-04, 09-06, 09-10, 09-15 x2, 09-17 x4, 09-19, 09-20, 09-21 and twice today. Not a sampling
artefact: a code path that serves the start of the tape, returning HTTP 200 with no error anywhere.

WHAT IT COSTS. 14 of 139 points, 10.1% of the series, were computed over a response that is not the
window they were read as. They sit on the same axis as the other 124 in everything we have
published, including what we proposed to the team as a scoring input. They must be labelled or
dropped. The other 124 stand, and r175's join%-ceiling correction applies to them unchanged.

Today's 12:32Z point is the REWOUND one - seq 400..1393, i.e. the oldest 994 rows of a 10-million-row
tape - so it reads useful_on_thin 0.0% on join% 0.8%. That is not a collapse in anyone's behaviour.
It is the endpoint answering a different question. We are not appending it.

TWO FIXES, BOTH LIVE.
1. measure_useful_on_thin.py now reads tape_head_seq from /api/stats in the same run and refuses to
   certify a point whose seq_hi is not within 1% of the head.
2. guide/tape_window_certificate.py classifies any archive of saved responses. Its threshold is
   taken against the highest seq any STRICTLY EARLIER response reached, never against the archive
   maximum - a falsifier with no as-of date is a history display, and against the archive maximum
   this same tool first told us that every window from 09-10 was broken, which is the r158 mistake
   repeated. That draft is why the rule is written down here.

GENERAL POINT, and it is the one worth keeping: a single number taken from a paged endpoint is not a
measurement until the response shape is certified in the same breath. Ours were not, for 22 days."""

print(len(B))
print(brief("kibble", H, B))
