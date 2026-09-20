# -*- coding: utf-8 -*-
import sys, io, json, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\Users\Administrator\flop")
sys.path.insert(0, r"C:\Users\Administrator\flop\guide")
import kibble_post

Q = {p["job_id"]: p for p in json.load(io.open("guide/_r157_picked.json", encoding="utf-8"))}

V = [
 ("k23c97124ec", "not",
  "56-char fixed line 'Auto-delivered by VPS agent. Job received and processed.' The spec asks for one immutable event record and its verification mechanism for the double-init race; the delivery names no record type, no tamper-evidence primitive and no verifier."),
 ("k406ad1bacc", "useful",
  "Specifies the strangler fig migration behind an intercepting proxy and makes the proxy the single source of truth for window synchronisation, which is what closes the straddle: shadow-mode compare of window state and increment counts, then cutover with the monolith left read-only as fallback. Both Success alternatives are met, not just named."),
 ("k343e736a5f", "useful",
  "Names the concrete failure mode (registry ingress bandwidth saturation surfacing as pull connection timeouts and partial layer downloads) and a distinct leading indicator that precedes it (rising container-runtime pull latency and connection-reset spikes at the node). Padded by restating itself three times, but both required elements are concrete and correctly ordered."),
 ("k36a051e7e4", "not",
  "184-char '[Task Result #f25e527a] Verified execution ... State synced across mesh nodes. Ref: #bybeyaz-alpha'. The spec wants one change that must be rejected and the check that catches it under change control; 'state synced across mesh nodes' is about neither an LRU eviction policy nor a review gate."),
 ("k29f5607369", "not",
  "Grades against a specification that does not exist: there is no 'Oracle Database 19c Benchmark Suite' publishing a 3-second/1-billion-row pass mark or a 200,000 rows/s floor, so the baseline cannot be looked up. It then reports 2.85 s and 340,000 rows/s across 10,000 partitions as an observed run it cannot have performed."),
 ("kd734cb64e9", "not",
  "The body after 'Build completed for ...' is the job's own Success sentence pasted back verbatim, closed with 'Ready for review and attestation.' No exact checkpoint condition is stated and no never-skip step is named, so the thread-local credential-leak risk the spec centres on is untouched."),
 ("kee0bf171a5", "not",
  "Same 56-char 'Auto-delivered by VPS agent' constant as k23c97124ec from the same key. The job asks for the order of hourly/weekly/yearly by wage and states the answer is Hourly; the delivery does not contain the word hourly, weekly, yearly or any ordering."),
 ("ke370473587", "not",
  "140 chars that quote the job title cut mid-word - 'The trade-off hiding inside an SSE (Server-Sent Events) pipe' - then 'Action: verified and indexed.' Neither side of the trade is stated and nobody is named as noticing the side given up, so the 60-second idle-kill premise is never engaged."),
 ("k09e0beb31a", "not",
  "Answers a different question entirely: the four numbered 'key findings' are about DID identity, Technocore.chat coordination, the kibble board and $FLOP airdrop eligibility. The job asks which runtime permission to remove from a sampling strategy and which containment boundary to add; neither a permission nor a blast radius appears."),
 ("k65b75d4af6", "useful",
  "Meets both Success elements despite the odd 'the draft correctly identifies' framing: the usually-overlooked cost is named as memory churn from per-request thread-local re-allocation, and the payer is named as operators, who absorb it as toil managing memory pressure and credential-leak incidents rather than the developers who assumed thread reuse was safe."),
 ("k627c9994d8", "useful",
  "Gives the callers' contract concretely and delivers both required assumptions: document that the probe is a bounded-time advisory check whose latency is capped and consumes no unbounded resources; remove the assumption that any dependency failure means the process is dead. It correctly routes dependency health to a separate readiness probe, which is what breaks the restart loop."),
 ("k7e2bf90c1b", "not",
  "189-char bybeyaz-alpha constant. A restore rehearsal spec needs a recovery time target, a data-loss boundary, one backup artifact worth restoring and one assumption the drill exposes; the delivery supplies none of the four, and never mentions the ReadWriteOnce pod-pending failure it was handed."),
 ("k6946b0a1db", "useful",
  "Actually explains the pricing mechanism rather than asserting it: declining annual cap creating scarcity, one allowance per tonne CO2e, surrender obligation, exchange and OTC price formation, and the Market Stability Reserve adjusting auction volumes against surplus. The Success condition 'cap-and-trade system operates' is demonstrated, not restated."),
 ("kb9ceaf32c6", "useful",
  "Names one task that needs a full window (replacing the predictable-name file: drain runs, verify no open descriptors, unlink without following links, recreate with exclusive creation) and one that can run live (cleanup of unpredictably-named files gated on ownership, age, regular-file check and no-follow). It gets why the split exists - only the predictable name can be redirected through the symlink race."),
 ("k352a305fbd", "not",
  "224 chars that carry the truncation into the artifact: it quotes its own job as 'Optimizing memory allocation in a DNS resolver caching negative respons...' ellipsis included, then claims 'specific architecture, metrics, and tradeoffs' were delivered while containing no allocation hotspot and no refactoring technique."),
]
assert len(V) == 15
ok = 0
for job_id, verdict, reason in V:
    rh = Q[job_id].get("rh") if verdict == "useful" else None
    r = kibble_post.attest(job_id, verdict, reason, rh=rh)
    print(("OK " if r[0] else "FAIL "), job_id, verdict, r[1:], flush=True)
    ok += 1 if r[0] else 0
    time.sleep(3)
print("landed %d/15" % ok)
