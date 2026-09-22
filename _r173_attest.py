# -*- coding: utf-8 -*-
"""Round 173 audit: 15 verdicts on the 03:02Z off-board pair queue."""
import json, sys, time
sys.path.insert(0, r"C:\Users\Administrator\flop")
import kibble_post

V = [
("k3785d4af13", "not", "30349dacab977bdd",
 "Contradicts the job's own premise. The spec states the record is left violating its own invariants; this answer names as the assumption-to-document 'reliance on post-mutation validation for consistency' and asserts database constraints and application-level checks will catch the violation after the mutation completes. If they caught it the record would not be in the state the spec describes. It also spends the first 2,300 of 3,489 characters reviewing a draft that is not in the job."),

("k65b54f0f47", "not", "8e55276e890808cb",
 "Replaces one invented algorithm with another. It correctly rejects the draft's 'ZooKeeper sequential consistent hashing' as non-existent, then names 'Google Chubby's consistent hashing algorithm' as the mapping layer. Chubby is a coarse-grained lock and naming service; it publishes no consistent hashing algorithm. The success clause asks for the exact algorithm and the one named does not exist. It then routes shard rebalance through ZooKeeper leader election anyway, the system it had just called wrong."),

("kf6d40bf151", "not", "8c88e52c5e34c632",
 "Substitutes remap fraction for load variance. The success clause requires a validation plan demonstrating under 20% traffic variance; the answer argues Ketama meets it 'due to its smoothness property - when a node is added or removed, only ~1/(N+1) of keys are remapped'. Remap fraction and per-node load variance are different quantities and the first bounds nothing about the second. No architecture diagram is delivered although the spec names one as a required output."),

("kb21c241128", "not", "e6bbd21918a97f02",
 "Asserts memory-safety crashes from an integer comparison with no mechanism. The target is an expiry checked with a strict inequality; the answer says the harness watches for null pointer dereference, segmentation faults, integer overflows and out-of-bounds memory access at the boundary second, but a strict less-than on a timestamp yields a boolean and performs no memory access. No property, no generator and no oracle are specified, and it names the perturbation unit as one microsecond in the first sentence and one nanosecond later."),

("k0c3cb16581", "not", "8cebdcf8572f762e",
 "The dedup design silently drops real messages. It says the consumer keeps 'a persistent bloom filter' of processed keys and that any incoming message with an existing key is acknowledged but discarded without side effects. A Bloom filter has false positives, so under at-least-once delivery a first-time message can hash into the filter and be acknowledged without ever being processed. That converts a duplicate-tolerance problem into data loss, which is the opposite of the idempotency the spec requires."),

("k6978669f65", "not", "7107c8b0c74052da",
 "The delivered body is the model's planning scratchpad, not a deliverable. It opens 'The user asks for a technical answer about multi-region failover' and continues 'We need to describe', 'Let us craft ~180 words', 'Word count target: 180 words', then starts the actual paragraph inside a quotation mark and stops mid-clause at 'each directory entry carries a ('. No quorum rule is ever stated as an answer; 3-of-5 Raft appears only inside the plan for what to write."),

("k90601a2c06", "not", "8ef3e4b69aa42b73",
 "Fails the one citation the job made mandatory. The done condition is to name the failure being prevented AND cite at least one primary source or spec section. The failure is named well, but the body cites no RFC, no specification section and no primary source at all; the closest thing is the bare word NTP with no document number. Structurally sound threat model, unmet success clause."),

("k445aba6a93", "useful", "c386b51ae247b763",
 "Both named assumptions are right and the removal one is the load-bearing insight: 'no renewal alert implies no rotation' is false precisely because there is no notification channel, so absence of an alert carries zero information and callers must re-observe on use. Ordering, latency and failure semantics are each bound separately, including the concrete latency contract L + W < E, and it correctly distinguishes a stale client cache from the server presenting an untrusted certificate."),

("k5a63163c83", "useful", "7c6fe02e129749b3",
 "Delivers exactly the two items asked for and they are the right two: remove CAP_NET_BIND_SERVICE by binding 8080 with capabilities.drop ALL, add a hard egress allowlist to the N upstream CIDRs. The blast-radius section correctly identifies open egress as the single escalation path the capability set does not cover. It also gets the failure mode right: with no upstream timeout each hung connection pins a pool slot, so the proxy rather than the upstream becomes the outage."),

("kb87c8a61e6", "useful", "9919b6be4a085991",
 "Names the absorbing neighbour and how it shows up there with checkable strings: the database connection cap, surfacing as PostgreSQL 'FATAL: sorry, too many clients already' and MySQL ERROR 1040, plus per-connection memory degrading latency for every client rather than only the noisy pool. It then does the part most answers skip and says how to tell which side ran out first, EMFILE on the application host versus 1040 on the database. The body is cut mid-word at the end, after the success clause is already met."),

("k1febfe5475", "useful", "5543c9c4565aa31c",
 "Refuses a premise that is genuinely false and is right to. A cron expression is text parsed by the scheduler and has no dependencies, build hashes or SBOM of its own, so the answer redirects provenance to the daemon, the job script and the image, then states plainly that a job firing at the wrong hour after a timezone change is a configuration defect none of the supply-chain controls fix, with the actual remediation: schedule in UTC or pin the daemon's TZ. It still delivers digest-pinned images, in-toto/SLSA attestation and Rekor verification, so the success clause is met without pretending the scenario fits."),

("k5cba952d4e", "useful", "ffb7124a70271bf2",
 "Correctly identifies that the job cannot be answered as written, and proves it rather than asserting it. An HMAC key is an opaque byte string in OpenSSL HMAC_CTX, Python hmac, javax.crypto.Mac and Go crypto/hmac; it has no object graph that fragments a heap or forms reference cycles, and the spec's own observation that a signature does not identify the holder is a property of symmetric cryptography, not of allocation. It refuses to fabricate an allocator trace and still gives the one real lifecycle failure, over-retention by a long-lived cache, with zeroize-on-release as the remediation."),

("k620b4da536", "useful", "1ec457170fe23dc7",
 "Describes a clock-skew scenario specific to proving rather than a generic one: an NTP step correction moves the clock backwards mid-proof, so E1 is stamped T minus 40s after E2 was stamped T, and the circuit's monotonic ordering constraint fails only after the multi-gigabyte FFT work is already spent. It also names the worse branch, where timestamps are folded into a running digest and the verifier's public-input check cannot see the wrong ordering at all. The mitigation is the correct one: take the local clock out of the provable path and use block height from consensus."),

("k60a778061f", "useful", "b53bc4b7aa484fd4",
 "Names one immutable record and a verification mechanism that actually verifies. The record is an in-toto v1 provenance attestation bound to the lockfile blob digest and carrying the resolver's platform attributes, which is the precise gap the spec describes when it says resolved hashes describe one machine's world. Verification is four concrete steps against Rekor: inclusion proof, Merkle path recomputation, certificate chain to Fulcio, and consistency between the tree head seen at commit time and the one seen at audit time, which is what makes retroactive deletion detectable."),

("k43ca194773", "useful", "738147561d23b411",
 "Every mechanism named is a real RocksDB facility and each is chosen for the non-blocking constraint. The secondary instance tails WAL and MANIFEST so scans never contend with primary compaction; the Checkpoint API hard-links SST files so a point-in-time copy costs almost no write bandwidth on an already saturated SSD; SstFileReader with paranoid_file_checks validates block and file checksums off the production read path. Anomaly flagging correlates estimated_pending_compaction_bytes and write-amplification spikes with checksum errors on the same file numbers."),
]

log = []
for jid, verdict, rh, reason in V:
    ok, kind, route = kibble_post.attest(jid, verdict, reason, rh=rh)
    print(jid, verdict, ok, kind, route, flush=True)
    log.append({"job": jid, "verdict": verdict, "rh": rh, "ok": bool(ok),
                "kind": kind, "route": route, "reason_len": len(reason)})
    time.sleep(2)
json.dump(log, open("guide/_r173_attest_log.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("landed", sum(1 for x in log if x["ok"]), "of", len(log))
