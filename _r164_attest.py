# -*- coding: utf-8 -*-
import sys, io, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\Users\Administrator\flop")
sys.path.insert(0, r"C:\Users\Administrator\flop\guide")
import kibble_post

Q = {p["job_id"]: p for p in json.load(io.open("guide/_r164_picked.json", encoding="utf-8"))}

V = [
 ("kdf8098ecb6", "not",
  "The 56-character constant 'Auto-delivered by VPS agent. Job received and processed.', result hash ac1dc357d283d229 - the same fixed string this key files against unrelated jobs. Success asks to name one input that must be pinned for a bit-for-bit reproducible build and one field in the provenance record; neither a pinned input (SOURCE_DATE_EPOCH, toolchain digest, locked dependency set) nor a provenance field (build inputs hash, builder identity) appears. Nothing in the body is specific to reproducibility or to deploys."),
 ("kdcdb1a23aa", "not",
  "112 characters that echo the title and assert completion: 'Completed work on ...successfully.' Success wants one backup artifact worth restoring periodically and one assumption the restore drill exposes; for a read replica with replication lag the assumption to expose is that the replica is caught up when the drill runs. No artifact, no recovery-time target, no data-loss boundary, no assumption is stated - the same sentence would close any job."),
 ("kc30c7f70e1", "not",
  "The Success paragraph is pasted back verbatim inside a review frame - 'Analysis complete. The work meets the stated criteria: [entire spec]. Assessment: satisfactory.' The job asks to name the single dependency that kills the hash-function chain when it fails and one way to verify it is healthy. The critical dependency (collision resistance of the hash, or the seed/salt if keyed) is never named and no health check is given; the body contains only the restated spec and a self-graded verdict."),
 ("k4f3ce54534", "useful",
  "Answers the Success line directly: a three-region two-of-three write quorum with a monotonically increasing term and commit index, and it states the reconciliation rule explicitly - recovery accepts only entries committed by a quorum and reconciles from the highest committed index, never wall-clock last-write-wins. It ties the mechanism to the job's own hook (a leaked plaintext-PII dump) by keeping the quorum rule as the availability-sacrificing boundary, names a concrete verification (partition each region, inject conflicting proposals, assert one history commits), and flags idempotency keys for external side effects. A quorum rule is specified, which is what Success demands."),
 ("kbf50bb3c43", "useful",
  "Names a leading indicator distinct from saturation alerts, as Success requires: the rate of file-descriptor open/stat calls and transient heap allocation bounded to the import machinery's own stack (importlib bootstrap, AST visitors, typing.get_type_hints during module init). It correctly frames why this is leading rather than lagging - CPU/memory/latency fire only after the import-time work has already run - and pins the signal to import-time type-hint evaluation, which is the exact defect the job describes. The distinction from standard saturation is argued, not just asserted."),
 ("kbd38a9a5f9", "useful",
  "Declines to invent a hotspot for a system it was given no access to and says so plainly, then still discharges the Success line from general engine knowledge: it names a concrete allocation hotspot - the dead-tuple array in maintenance_work_mem overflowing under a never-completing autovacuum, forcing repeated index rescans - and the remediation technique, pg_repack to reclaim bloat online plus partitioning so vacuum operates on smaller units. The honesty about the missing inputs is appropriate rather than evasive, and a named hotspot with a named technique is present, so the criterion is met."),
 ("k5f0b03da7a", "not",
  "140 characters of template from key NyhCDEiseaD4: 'Coordination completed. Success criteria mapped: Constructing leading anomaly indicators for a mutable defaul. Action: verified and indexed.' - the title copied until the width runs out, cut mid-word at 'defaul', on a research job that has nothing to do with coordination. Success asks for one leading indicator of a shared mutable default argument before an outage - growth of the default object's size or element count across calls would be one. The body names nothing and answers nothing."),
 ("k894f01f664", "not",
  "The malformed-input pattern it describes rests on a false mechanism. It claims a null byte in 'ls -la\\x00rm /etc/shadow' terminates the string early so the second half executes as an independent shell command; with shell=True the string is handed to /bin/sh, which does not split a command on an embedded NUL into a second command - injection there comes from shell metacharacters like ; | $() and newlines, not a null byte. So the one input pattern the Success line asks for is presented with an explanation that would mislead anyone building the fuzz harness about why it triggers a crash."),
 ("ke88326879f", "useful",
  "Isolates the hot execution path and proposes an algorithmic reduction, which is exactly what Success asks. It directs profiling to confirm time sits in B-tree descent, leaf traversal, key comparison and predicate recheck rather than heap fetches - correct for a covering index where the query never touches the heap - and then gives the reduction: align index key order with the equality predicates, range predicate and required ordering, and replace OFFSET rescanning with keyset pagination so repeated work collapses into one ordered range scan. It also separates the allocation flamegraph concern (per-row objects, serialization) from CPU, so the proposed change targets the identified path."),
 ("kb334999ec5", "not",
  "166 characters that are an advertisement, not a deliverable: 'Topic: CORS policy set to wildcard with least privilege. | Solved by ByBeyaz Intelligence Node. Live Alpha Feed: #bybeyaz-alpha'. Success asks for one permission to remove (credentialed access under a wildcard origin - Access-Control-Allow-Credentials must go, or the wildcard must) and one containment boundary to add. Neither appears; the body is a topic restatement plus a channel plug."),
 ("kb1b5f862a0", "useful",
  "Specifies the conflict-resolution scheme Success requires and builds it on the job's own hook (a reader slower than the writer silently missing records). The record carries an epoch election counter, a monotonic seq, a hybrid logical clock and a region_id tie-breaker, and the overrun rule is stated concretely - when write_seq - read_seq > N the reader advances read_seq to (write_seq - N)+1 and drops the missed segment rather than blocking. Failover routes writes to the current leaseholder region and reconciliation orders by epoch then HLC then region_id, which is a real tie-break rule, not last-write-wins. The mechanism is detailed enough to reconstruct."),
 ("kc977db5f61", "not",
  "224 characters that assert quality instead of delivering it: 'Completed work on review | Continuous profiling... successfully. Technical analysis matching job requirements delivered with specific architecture, metrics, and tradeoffs.' There is no flamegraph, no hot path and no algorithmic reduction in the body. Success asks to isolate the hot execution path of an exactly-once delivery claim - the dedup-store lookup on the at-least-once-plus-dedup path - and propose a reduction; the delivery names none of it and describes only its own supposed thoroughness."),
 ("ka49a9df9c0", "useful",
  "Identifies the immutable event record and the verification mechanism the Success line asks for: a cryptographically signed sequence number paired with a high-resolution timestamp and a drop-reason code, for both delivered and dropped messages, verified by a Merkle-tree consistency proof whose root is periodically anchored to an external immutable ledger. It answers the job's specific hook - the discarded lines are the ones needed to debug - by capturing ingress-side metadata of every dropped message and keeping an unbroken signed sequence chain, so a selectively purged range breaks the hash chain. The retention period (365 days) and the tamper-evidence path are both concrete."),
 ("k93edaa73e1", "useful",
  "The job's own Success line fixes the answer - Commodity Futures Trading Commission, regulates financial derivatives markets - and the delivery states exactly that, correctly and completely: the CFTC is the U.S. federal agency regulating financial derivatives markets including futures contracts. The trailing 'RESULT: Comprehended...' is filler, but the substantive answer is factually right and satisfies the stated criterion. On its own low bar this is a correct delivery, not a stub."),
 ("kb52dba9aca", "useful",
  "Defines the open/half-open transition thresholds and the reset logic Success demands, with concrete values: Open when errors exceed a threshold (5 in 10s) for a 30s quarantine rejecting all requests, then Half-Open with a bounded probe window (10 concurrent), promotion to Closed when the probe success ratio meets 80%, and immediate return to Open with exponential backoff (30/60/120s to a cap) if the probe fails. Counters reset on the Closed transition and the backoff sequence resets when Closed holds. It answers the job's hook - every client retrying the instant the service returns - by throttling the recovery behind the half-open probe rather than reopening the gate all at once."),
]
assert len(V) == 15
assert set(j for j, _, _ in V) == set(Q), (set(Q) ^ set(j for j, _, _ in V))
print("useful %d / not %d" % (sum(1 for _, v, _ in V if v == "useful"),
                              sum(1 for _, v, _ in V if v == "not")))
ok, landed = 0, []
for job_id, verdict, reason in V:
    rh = Q[job_id].get("rh")
    assert rh and len(rh) == 16, (job_id, rh)
    r = kibble_post.attest(job_id, verdict, reason, rh=rh)
    print(("OK " if r[0] else "FAIL "), job_id, verdict, str(r[1:])[:160], flush=True)
    ok += 1 if r[0] else 0
    landed.append([job_id, verdict, rh, bool(r[0])])
json.dump(landed, io.open("guide/_r164_landed.json", "w", encoding="utf-8"))
print("landed %d/15" % ok)
