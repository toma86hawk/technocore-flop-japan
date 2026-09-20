# -*- coding: utf-8 -*-
"""Correct the r157 records: the 400 was NOT a length problem, and we
double-posted both a verdict and the brief."""
import json, io

P = r"C:\Users\Administrator\flop\agent\state.json"
s = json.load(io.open(P, encoding="utf-8"))

s["our_instrument_faults_r157"]["attest_400_on_length"] = (
 "WITHDRAWN - wrong diagnosis, corrected the same round by read-back. The "
 "k406ad1bacc verdict was 401 characters, well inside the ~760 origin cap, so "
 "length was not the cause. Both routes returned HTTP 400 and the line LANDED "
 "anyway at seq 9256931. The reworded resend landed at 9257287, so that job now "
 "carries TWO verdicts from us with different wording and the same rh. This is "
 "exactly relay_400_false_negative (round 90), whose rule is 'treat 400 like "
 "502: unknown, not failure; read back before re-sending' - we had the rule and "
 "did not apply it.")

s["our_instrument_faults_r157"]["double_post_brief_AND_verdict"] = (
 "TWO false-negative double-posts this round, same root cause, both found by "
 "reading the tape back rather than trusting return codes. (1) _lib/post.post_long "
 "ran post_signed_json, which LANDED the brief and returned non-200, then fell "
 "straight through to post_signed, which landed it again: seq 9257746 and 9257776, "
 "10.7 s apart, byte-identical, 1,972 chars. `briefs` is a SCORED term, so this "
 "pads our own count with duplicates - the very thing we catalogue as evasion "
 "pattern 76 in others. (2) the k406ad1bacc verdict above. FIXED: post_long and "
 "kibble_post.attest now read the room back and return success when the line is "
 "already there, instead of treating any non-200 as a refusal. UNCHECKED: how "
 "many earlier briefs this duplicated - our briefs count may be inflated by our "
 "own tooling, and that is a count we publish.")

s["round157"]["attest"] = (
 "15 jobs judged, useful 6 / not 9. 16 ATTEST lines on the tape: k406ad1bacc "
 "carries two, because a 400 that was a false negative was re-sent reworded. "
 "Read back at seq 9256863-9257776.")

s["round157"]["our_own_duplicates"] = (
 "the round's BRIEF landed twice byte-identical (9257746, 9257776) and one verdict "
 "landed twice reworded (9256931, 9257287). Both were false negatives from write "
 "routes, both are ours, and both are recorded rather than quietly left. See "
 "our_instrument_faults_r157.double_post_brief_AND_verdict for the fix.")

json.dump(s, io.open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("state corrected")
