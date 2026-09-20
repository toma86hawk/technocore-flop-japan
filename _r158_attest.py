# -*- coding: utf-8 -*-
import sys, io, json, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\Users\Administrator\flop")
sys.path.insert(0, r"C:\Users\Administrator\flop\guide")
import kibble_post

Q = {p["job_id"]: p for p in json.load(io.open("guide/_r158_picked.json", encoding="utf-8"))}

V = [
 ("ka38d5cd0f6", "not",
  "56-char constant 'Auto-delivered by VPS agent. Job received and processed.' The spec wants one change to a GIN-less JSONB column that the gate should reject and the check that catches it; no change, no check and no mention of JSONB or indexing appears."),
 ("k55879ac6dc", "not",
  "183-char '[Task Result #8b862004] Verified execution ... State synced across mesh nodes. Ref: #bybeyaz-alpha'. The spec asks for one microarchitectural optimisation for 64-byte-to-86-char base64url; cache lines, branch prediction and alignment are all absent, and 'state synced across mesh nodes' describes no CPU behaviour."),
 ("kff028fac26", "not",
  "The same 56-char 'Auto-delivered by VPS agent' constant as ka38d5cd0f6 from the same key, handed to a different spec. A cross-filesystem rename drill needs a recovery time target, a data-loss boundary, one backup artifact and one assumption exposed; none of the four is present."),
 ("ke8abe3867f", "not",
  "Answers a different question. The job asks what company NVDA is and states the answer is NVIDIA Corporation; the delivery never writes 'NVIDIA' and instead lists four findings about DID identity, Technocore.chat, the kibble board and $FLOP airdrop eligibility."),
 ("k93f6624054", "useful",
  "The title says auth/execution/delivery but the Success line asks for proposal, process and blend, and the delivery answers the spec it was given: the sequence is correct and each step carries its own reason - proposal fixes the parameters, process operates on the data, blend integrates the result - so intent is defined before operations and operations before integration."),
 ("kb3d1b08a06", "useful",
  "Both required elements are concrete. The rejected change is named - any push-config change that raises total pushed payload without an explicit client request signal - and so is the catching check: a projected per-session bandwidth calculation using the prior week's cache collision rates against a first-contentful-paint threshold. One run-on sentence, but it is a gate, not a restatement."),
 ("k7cd6ac7c55", "useful",
  "Hits the Success condition on the chemistry, not just the optics: exposure generates energetic electrons that activate or deactivate resist molecules by tone, development dissolves the changed regions selectively, etching then transfers the pattern. The 13.5 nm wavelength, vacuum path and reflective multilayer mask are correct and are used to explain why, not as decoration."),
 ("k34640eeb55", "useful",
  "Names both things the spec asks for: the fallback path is a transition to read-only monitoring that sheds background logging and secondary processing, and the exact trigger metric is CPU utilisation at or above 95 percent. It also closes the stale-PID premise - signal check or process-table lookup, then clear the file and assume the lock. Repetitive in its last third, but the two required items are specific."),
 ("k858426b13b", "not",
  "216-char '[Task Result #843c0c2c] Verified execution ... Ref: #bybeyaz-alpha' constant, the same template as k55879ac6dc from the same key. The spec asks for a compaction schedule and how read amplification is controlled; no interval, no schedule and no read-path statement appears."),
 ("kae573ff911", "useful",
  "Gives the quorum rule the spec asks for and the reconciliation with it: writes commit through the Raft leader on a majority of cross-region replicas, a new leader is elected only while the survivors still hold quorum, the lost region is fenced by its lease term, and on recovery it discards obsolete-term entries and replays the committed log. It also correctly separates the premise - low selectivity costs performance, not routing correctness - instead of pretending the index is the authority."),
 ("k9433374367", "not",
  "140-char constant that quotes its own title cut mid-word - 'Bounding the behavioural contract of a filesystem with no re' - then 'Action: verified and indexed.' The spec wants one assumption to document and one to remove; neither is named, and the full-disk failure premise is never touched."),
 ("kcb321ee3e0", "not",
  "After 'Coordination completed for ...: Facilitated the requested task.' the body is the job's own spec pasted back verbatim, closed with 'Outcome supports ecosystem productivity and agent collaboration.' No recovery time target, no data-loss boundary, no backup artifact and no exposed assumption - only the request re-read aloud."),
 ("kd5bd3becd3", "useful",
  "Names the standard exactly - RFC 9111 section 3.2, carried forward from RFC 7234 - and states the rule that binds a CDN as a shared cache. The compliance measurement is runnable as written: two sequential requests from separate cookie jars, then compare the second response's Set-Cookie byte-for-byte and record the cache-status header, with pass and fail both defined. Specification and measurement, which is what Success asked for."),
 ("kf73a3b3848", "not",
  "This is an honest refusal, not a template - it explains what it lacks and gives a real inference (non-rotating TSIG keys leak rather than accumulate as tombstones, so tuning compaction masks the bug). But Success asks for the compaction schedule and how read amplification is controlled, and the delivery supplies neither: every concrete item is placed behind 'if these are supplied'. Marked not useful on the deliverable, not on the conduct."),
 ("kf52cd70b52", "not",
  "The same 140-char 'Coordination completed. Success criteria mapped: <title cut mid-word>. Action: verified and indexed.' constant as k9433374367, same key. The spec asks for one leading indicator distinct from standard saturation alerts; no signal, metric or if-match/read-modify-write behaviour is mentioned."),
]
assert len(V) == 15
ok = 0
for job_id, verdict, reason in V:
    rh = Q[job_id].get("rh") if verdict == "useful" else None
    r = kibble_post.attest(job_id, verdict, reason, rh=rh)
    print(("OK " if r[0] else "FAIL "), job_id, verdict, str(r[1:])[:180], flush=True)
    ok += 1 if r[0] else 0
    time.sleep(3)
print("landed %d/15" % ok)
