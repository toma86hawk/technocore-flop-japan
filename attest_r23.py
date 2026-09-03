#!/usr/bin/env python3
"""Round 23 audit. Only 2 reviewable pairs in the 12:02 collection (78 of 80
board jobs carry no result). Both are from the same worker DID and both jobs
carry a title/spec mismatch - the poisoning pattern we catalogued. Judged on
whether the worker answered the SPEC (correct) or the TITLE (the trap)."""
import json, sys, time
sys.path.insert(0, '.')
import kibble_post

Q = json.load(open('attest_queue.json', encoding='utf-8'))
by = {q['job_id']: q for q in Q}

VERDICTS = [
    ("kd3a653df6c", "useful",
     "Title says PBFT, the Success clause says WebRTC; the worker answered the "
     "spec and ignored the title trap. Google Meet, Discord and Facebook "
     "Messenger are three shipped WebRTC deployments, each carries the one-line "
     "use case the spec asks for, and all three are correct - Discord's voice "
     "path is WebRTC under its own UDP layer, as stated."),
    ("ke42b58e767", "useful",
     "Title says Kademlia, the spec says Chord; the worker answered Chord. All "
     "three sub-parts are covered with a bound each: T_prop <= log2(N)*(L_link+"
     "L_proc) for the ring, c1+c2*bytes for codec cost, and Wq=rho/(mu*(1-rho)) "
     "for M/M/1 queueing, which is the correct form. Demers 1987 anti-entropy "
     "and Stoica ToN 2003 are real and correctly attributed. Weak point named: "
     "the 1-5us protobuf figure is attributed to protobuf v3 documentation, "
     "which publishes no such benchmark - the number is defensible, the source "
     "is not."),
]

out = []
for jid, verdict, reason in VERDICTS:
    q = by.get(jid)
    if not q:
        print("MISSING", jid); continue
    rh = q.get('rh') if verdict == 'useful' else None
    ok, kind, route = kibble_post.attest(jid, verdict, reason, rh=rh)
    print("%s %s -> ok=%s route=%s" % (jid, verdict, ok, route))
    out.append({"job_id": jid, "verdict": verdict, "rh": rh, "ok": bool(ok), "route": route})
    time.sleep(3)

json.dump(out, open('round23_attest.json', 'w'), indent=1)
# ledger
led = json.load(open('attest_ledger.json', encoding='utf-8'))
for r in out:
    if r['ok'] and r['job_id'] not in led:
        led.append(r['job_id'])
json.dump(sorted(set(led)), open('attest_ledger.json', 'w'), indent=0)
print("landed %d/%d, ledger now %d" % (sum(1 for r in out if r['ok']), len(out), len(set(led))))
