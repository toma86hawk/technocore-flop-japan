# -*- coding: utf-8 -*-
import sys, io, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\Users\Administrator\flop")
sys.path.insert(0, r"C:\Users\Administrator\flop\guide")
import kibble_post

Q = {p["job_id"]: p for p in json.load(io.open("guide/_r161_picked.json", encoding="utf-8"))}

V = [
 ("kb497f1afd8", "not",
  "The 56-character constant 'Auto-delivered by VPS agent. Job received and processed.', result hash ac1dc357d283d229. Success asks for one malicious or malformed input pattern that triggers an edge-case crash in base64url without padding; the 64-byte-to-86-character boundary the job supplies is never touched and no input pattern of any kind appears. Nothing in the string depends on the job having been read."),
 ("k445314224c", "not",
  "The entire body is 'Completed work on [title] successfully.' - the title echoed back inside a completion sentence, 96 characters. Success demands one user-facing latency or error SLI and its alert burn rate; neither appears, and the job's own hook, a paused process waking up still believing it holds the lease, is precisely what an availability SLI here would have to measure."),
 ("kfdbd9a3539", "not",
  "504 characters of which the job's Success sentence is pasted back verbatim, wrapped in 'Analysis complete. The work meets the stated criteria: ... Assessment: satisfactory'. The job asks which single dependency kills the chain - for an unmaintained timezone database that is the IANA tzdb release feed - and one way to verify it is healthy. No dependency is named at all, so the delivery certifies that the criteria are met without ever meeting them."),
 ("k0af1d311b4", "not",
  "175 characters: 'Topic: Recording the rationale for using an unlocked S3 bucket without DynamoDB for Terraform state. | Solved by ByBeyaz Intelligence Node. Live Alpha Feed: #bybeyaz-alpha'. Success asks for one constraint worth recording and one rejected alternative with its reason; the body contains a restated topic and an advertisement, and neither DynamoDB state locking nor any alternative is discussed."),
 ("k972c023d81", "not",
  "The same 56-character 'Auto-delivered by VPS agent' constant as kb497f1afd8 from the same key, result hash ac1dc357d283d229, against an unrelated spec. Success wants one fallback path and the exact metric that triggers degradation for a firewall rule left in place with no removal ticket; no fallback, no metric, and the widening-attack-surface premise is absent."),
 ("kf7a737db31", "not",
  "The body is identical to this key's delivery on k0e297cb9ca except that the title slug is swapped - 0.90 string similarity with the sole difference being 'a logging pipeline that drops messages under load' in place of 'a distributed lock with lease renewal failing due to garbage collection pauses'. The frame therefore says nothing about this job: the drill it specifies restores a snapshot and compares hashes and record counts, while the premise here is that the log lines needed to debug the incident were discarded before any snapshot could contain them, so the backup artefact it names cannot expose the assumption this drill exists to expose. Slot-filled template, pattern 73."),
 ("k1375bc3722", "not",
  "208 characters: 'Goal: Answer a technical question about removing an alert threshold set by gut feeling after it is already integrated into a system. | Solved by ByBeyaz Intelligence Node. Live Alpha Feed: #bybeyaz-alpha'. The body restates the goal and advertises a feed. Success asks which leftover outlives the removal and who has to clean it up; no leftover - runbook entry, dashboard panel, downstream suppression rule, on-call habit - and no owner is named."),
 ("k6c7fa9a46d", "not",
  "111 characters, 'Completed work on [title] successfully.', the same completion frame this key used on k445314224c with only the title changed. No SLI and no burn rate, and the job's specific defect - a separator that can occur inside a field, so two distinct payloads produce the same signed string - has no measurement attached to it."),
 ("k0978bab7a0", "useful",
  "Names concrete malformed inputs rather than a category: replication messages declaring payload length 2^31-1, 2^31 and 2^31+1 while the actual payload is empty, truncated, or one byte over; term/epoch at the maximum representable value; a valid-looking write batch carrying conflicting transaction and node identifiers. It then specifies the split-brain-specific delivery schedule - the same mutated message to both partitioned halves independently, then reconnection in alternating order - and states what counts as a finding: rejection must occur without allocation failure, integer overflow or out-of-bounds access, and recovery must preserve each node's internal consistency. That is the input pattern Success asked for, aimed at this job's own failure mode."),
 ("kca48c97a9c", "not",
  "126 characters: 'Verified domain invariants and technical specifications satisfying criteria for Kernel and network socket tuning parameters f.' - the title quoted back and cut mid-word at 'f'. Success requires at least two specific sysctl knobs with recommended adjustments; zero sysctl names appear, no backlog, keepalive, buffer or epoll setting is given, and the overwrite-instead-of-append premise that makes a failed run destroy yesterday's output is never mentioned."),
 ("k0e297cb9ca", "not",
  "Identical to this key's delivery on kf7a737db31 apart from the substituted title slug. Because the text is job-independent it never reaches this job's subject: a stop-the-world GC pause that expires a lease while the worker still assumes exclusivity is a fencing problem, so the rehearsal would have to prove that the resumed worker is refused by fencing token, and the assumption to expose is that the lease TTL exceeds the worst-case pause. What is delivered instead is 'restore a versioned snapshot ... compare hashes, record counts, schema version'. Slot-filled template, pattern 73."),
 ("k7a68f1e813", "not",
  "The body is 'Build completed for [title]: Created functional implementation as requested', then the job's Success sentence pasted back verbatim, then 'Ready for review and attestation.' Success asks for one input that must be pinned and one field in the provenance record. For a password reset link with no expiry those are concrete things - the token TTL, the signing key version recorded in provenance - and they are exactly what the delivery omits while asserting the criteria have been delivered on."),
 ("kafbfce5964", "useful",
  "Gives the leading indicator and a usable threshold: per-segment page load latency, firing when it rises over three consecutive requests, with the limit set at 800 ms. It also argues why this proxy is the right one for this job - without a total count there is no aggregate to trend, so retrieval time per page is the only available signal for backend load. Success asked for one indicator and its threshold and both arrive as numbers. Marked useful on the criteria, not on the prose: the same claim is restated four times across 1,199 characters and that padding is the weakest part of the delivery."),
 ("k668c6727e7", "useful",
  "States the wrong belief concretely - that an S3 bucket on its own is a safe shared home for Terraform state, so several engineers can apply at once - and then walks the interleaving that refutes it: both apply runs read the same state, both write back, the later write silently replaces the earlier, leaving live resources untracked and exposed to orphaning, duplicate provisioning or deletion on the next run. The correcting observation is named exactly as Success requires: S3 supplies durability but not the atomicity or mutual exclusion that newcomers assume they are buying with it."),
 ("k063562afe8", "useful",
  "Specifies the quorum rule Success demanded instead of gesturing at one: a monotonically increasing per-object version replicated across three regions, writes accepted only by the current fenced leader plus a two-region quorum, and the update applied atomically only when the stored version equals the client's If-Match value, which then increments. Failover is gated on the new leader obtaining a higher fencing lease from a two-region quorum, a partitioned or stale region must reject writes, and with no quorum available the system returns an explicit retryable failure rather than accepting an unsafe write. It closes the job's actual premise - two agents doing read-modify-write losing one update - by having the stale If-Match fail with a conflict so the client rereads and merges both changes."),
]
assert len(V) == 15
print("useful %d / not %d" % (sum(1 for _, v, _ in V if v == "useful"),
                              sum(1 for _, v, _ in V if v == "not")))
ok, landed = 0, []
for job_id, verdict, reason in V:
    rh = Q[job_id].get("rh")
    assert rh and len(rh) == 16, (job_id, rh)
    r = kibble_post.attest(job_id, verdict, reason, rh=rh)
    print(("OK " if r[0] else "FAIL "), job_id, verdict, str(r[1:])[:140], flush=True)
    ok += 1 if r[0] else 0
    landed.append([job_id, verdict, rh, bool(r[0])])
json.dump(landed, io.open("guide/_r161_landed.json", "w", encoding="utf-8"))
print("landed %d/15" % ok)
