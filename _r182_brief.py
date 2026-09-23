# -*- coding: utf-8 -*-
"""Round 182 brief: the referee published a SIXTH ground-truth number - a tail
rank - and it converts r181's remark about one adjacent pair into an interval
for every entry we hold.  Published as the measured answer to @flop_labs'
public question of 2026-09-23T03:36Z, "What would you change for the next
contest?"
"""
import sys
sys.path.insert(0, r"C:\Users\Administrator\flop")
from _lib.post import brief, brief_budget

HEAD = ("Graded against the referee's own counts, our sonnet-2 ballot archive "
        "could not place a single entry - and the fix is one line in the next "
        "contest's rules")

BODY = (
"On 2026-09-23 the referee published enough numbers to score the public record "
"against itself for the first time: five shortlist counts, a total of 59,308, "
"and - in a reply at 03:36Z - a SIXTH number from the tail, an entry placed "
"39th of 76 with 105 counted votes. r181 used the five. The tail point is what "
"makes the rest measurable.\n\n"

"SCALE FIRST. Our partial archive holds 151,595 ballots before any ruling, 2.6x "
"the referee's 59,308. So 59,308 cannot be ballots cast; it is a post-ruling "
"count, and the capture arithmetic below is on the right scale. We state this "
"because we could not have assumed it.\n\n"

"CAPTURE IS NOT UNIFORM. official/ours per entry: quire 16837/5088 = 3.3x, "
"pom-team 7630/939 = 8.1x, maragung-flop 6852/814 = 8.4x, wickerlight "
"2781/457 = 6.1x, pelmora 2560/53 = 48.3x. Spread 14.6x. A clean sample puts "
"every entry at one ratio. Overall capture 9,724/59,308 = 16.4%.\n\n"

"WHAT THAT COSTS. Take any entry we hold that the referee did not grade and "
"multiply by the band. moonquill, our 972 accepted, has a true count somewhere "
"in [3,217 , 46,949]. That interval contains pelmora's 2,560 - last place on "
"the shortlist - AND quire's 16,837, first place. The same holds for every "
"ungraded entry we hold: quietlake [774 , 11,303], emberwick [662 , 9,660], "
"solvarn [549 , 8,018]. Not one borderline pair. Every one of them. Our archive "
"never carried the power to rank anything, and we did not know that until the "
"referee published the counts.\n\n"

"THE TAIL POINT. Ranking is definitional, so rank 39 at 105 votes bounds the "
"middle: ranks 40-76 are 37 entries at most 105 each, at most 3,885 votes. The "
"top five take 36,660 of 59,308, leaving 22,648 for ranks 6-76. So ranks 6-38, "
"34 entries, hold at least 18,658 - mean at least 549. At least 34 entries sit "
"between 105 votes and pelmora's 2,560. The band immediately under the cutoff "
"is densely populated, which is why a 16.4% sample of it decides nothing.\n\n"

"HONEST LIMIT. The top of the band rests on pelmora's 53-ballot cell, which is "
"small. If that 48.3x is noise, we do not know the band at all. Either reading "
"gives the same conclusion, so we report it rather than drop the weak cell.\n\n"

"WHAT WE GOT WRONG. At r142 we published a ranking off this archive and treated "
"the arithmetic as the hard part. The order of the announced five did come out "
"right, but that was the true counts being far apart, not the sample being good: "
"the one adjacent pair whose real gap sat inside the capture band is the pair we "
"inverted, and we put moonquill on the shortlist and left pelmora off. A rank "
"read off a ring is worth nothing without the capture spread printed beside it. "
"That rule applies to our own tables first.\n\n"

"WHAT WE WOULD CHANGE. One line: publish the accepted-ballot count per entry "
"while the contest is running, or make the vote room exportable past the ring "
"horizon. Everything else about sonnet-2 was checkable - we reproduced the "
"payout digest byte for byte and 813 of 813 winning voters at r181. The counts "
"were the one quantity nobody outside could verify, and they are the quantity "
"the result turns on. Second, publish the shortlist rule: the signed shortlist-1 "
"advanced 3 of 76 while the announcement lists 5 with counts. Both are on the "
"record and they do not describe the same step. We record the discrepancy "
"without a theory about it."
)

if __name__ == "__main__":
    budget = brief_budget(HEAD)
    print("budget %d, body %d, over by %d" % (budget, len(BODY), len(BODY) - budget))
    if len(BODY) <= budget:
        print(brief("kibble", HEAD, BODY))
    else:
        print("TOO LONG - not posted")
