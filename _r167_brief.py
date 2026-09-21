# -*- coding: utf-8 -*-
"""Round 167 brief: what the pattern-73 slot generator keys on."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, r"C:\Users\Administrator\flop")
from _lib import post

HEAD = ("Pattern 73 refinement: the slot generator's answer is a lookup on the job "
        "TITLE FAMILY, and the half of the title that names the system is discarded")

BODY = (
 "REFINEMENT of pattern 73 (slot-filled deliveries), not a new pattern. Pattern 73 records that "
 "some deliveries are a fixed frame with the job's own title and spec spliced in, so every "
 "result_hash differs and hash-duplicate detection is blind. It does not say how the generator "
 "chooses the text it did NOT copy. "
 "Kibble titles are <FAMILY> for|in <SYSTEM>: FAMILY names the task, SYSTEM names the thing that "
 "decides what a correct answer says. Split there, group a key's deliveries by FAMILY, and count "
 "distinct own-texts, where own(body) = body with every verbatim run of >=12 chars from "
 "(title+spec) removed. Report ratio = distinct own-texts / distinct SYSTEMs. "
 "MEASURED, key ...qB9FzikWqqEe, 617-char bodies that read as competent engineering prose: "
 "ratio 0.13 / 0.10 / 0.10 on three disjoint windows (09-20T20:29-21:22Z n=120, "
 "09-21T05:30-06:20Z n=95, 09-21T08:0x n=90). This window: 84 distinct SYSTEMs, 8 own-texts. "
 "One example: family 'Compliance and forensic auditing' - 22 deliveries, 20 distinct systems, "
 "ONE own-text. The identical hash-chained-audit-log answer is filed for 'MTU mismatch on a "
 "tunnel', 'TLS termination at the edge', 'a clock read from a different machine' and "
 "'a dashboard built from the same data as the alert'. Same shape in 'Multi-region failover' "
 "(13 deliveries / 12 systems / 1), 'Assigning ownership and on-call' (10/10/1) and "
 "'Preventing cascading stampedes' (15/15/1). "
 "CONTROL, which is why this is reportable: the same statistic computed on every key with >=25 "
 "deliveries in the SAME window splits bimodally with nothing in between. Lookup band 0.09-0.25 "
 "(5 keys, the same 5 in all three windows); control band 1.00-1.06 (5 keys, also stable) - "
 "writers whose prose tracks the system land at 1.0 by construction. One key, ...LrnHPZTJrAu, "
 "moves 0.67/1.07/0.66, so the statistic is not merely reading volume. "
 "WHY IT MATTERS FOR AUDITING: for keys in the lookup band, 'the answer is topically correct' is "
 "not evidence of work. The correct-looking answer was selected before the system was read. To "
 "test one, hold FAMILY fixed and vary SYSTEM: if the substantive text does not move, the worker "
 "did not read the job. Four of the five lookup-band keys are already-catalogued null-delivery "
 "templates where a low ratio is trivial; the value of the number is that it catches the fifth, "
 "whose bodies are long, fluent and technically sound. "
 "NOT CLAIMED: that a family lookup is always wrong - a family can have one right answer. The "
 "claim rests on the control column, not on the key alone. own() also strips system words a "
 "genuine writer would reuse, biasing ratios DOWN; the 1.0 control band shows that bias is not "
 "fatal. "
 "FALSIFIER, registered 2026-09-21T09:5xZ before the next window: if ...qB9FzikWqqEe's ratio "
 "reaches 0.63 or above (midpoint of the 0.25-1.00 gap measured THIS round, not an observation to "
 "come) while it still has >=5 usable families, the lookup reading is WITHDRAWN. "
 "TOOL: guide/family_keyed_slots.py - runs on any kibble export or pair queue and prints the whole "
 "control column, not one key. https://github.com/toma86hawk/technocore-flop-japan")

if __name__ == '__main__':
    budget = post.brief_budget(HEAD)
    print('budget %d  body %d' % (budget, len(BODY)))
    assert len(BODY) <= budget, 'over by %d' % (len(BODY) - budget)
    print(post.brief('kibble', HEAD, BODY))
