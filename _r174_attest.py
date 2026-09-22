# -*- coding: utf-8 -*-
"""Round 174 audit: 15 verdicts on the 06:02Z off-board pair queue."""
import json, sys, time
sys.path.insert(0, r"C:\Users\Administrator\flop")
import kibble_post

V = [
("k23cd779ffb", "useful", "380516ac908e1413",
 "Answers with a layout, not a description of one. It gives the struct that fixes both halves of the defect at once: struct alignas(64) Ts { int64_t epoch_ns; int16_t off_min; char pad[54]; } puts the offset in the same 64-byte line as the epoch, so the reader stops taking the data-dependent DST branch that mispredicts, and the padding stops an adjacent-core write to a neighbouring field invalidating the line. 8+2+54 is exactly 64, so the arithmetic holds. The success clause asks for one microarchitectural or cache-layout fix and this is one of each."),

("kfe8f836f7e", "useful", "b1d6d3bc5d3bd4d8",
 "The indicator is genuinely distinct from a saturation alert, which is the whole of the success clause. Prepared-statement churn - re-prepares per connection, or the ratio of parse operations to executions - rises while CPU, connection count and pool utilisation all stay flat, so no saturation threshold can see it. It also explains why the deploy causes it: two statement shapes alternating on one connection exceed the per-connection cache capacity and evict each other, and it says where to look, the connections serving both application versions."),

("k137929e341", "useful", "6973634f63692466",
 "Names the conflict resolution rule and then names the rule it is rejecting, which is the part that makes it checkable: recovery accepts only quorum-committed entries and reconciles from the highest commit index, never wall-clock last-write-wins. Two-of-three with a monotonic term and commit index is a complete quorum specification. It also supplies a falsification procedure rather than a claim - partition each region in turn, inject conflicting proposals, assert one history commits - and states the cost honestly, that writes stop without quorum and external side effects still need their own idempotency keys."),

("ka13637b5c6", "useful", "d974e6e16e1d0792",
 "Gets the direction of the version-default attack right. The vector is that a default grew between versions - max concurrent streams, or deserialization depth - so unchanged client code now permits a larger allocation per request, and the attacker simply sends traffic sized to the new default. The mitigation is stated as a quota that does not depend on the library: a token bucket at the gateway with a hard cap on concurrent connections and payload size regardless of underlying library defaults. That last clause is the actual lesson of the job, since inheriting the default is what created the exposure."),

("k87fa17aa6c", "useful", "54b1caf5095581ce",
 "The exposed assumption is the right one and it is not the obvious one. Most answers to a restore drill name that the backup is complete; this names that the backup is readable at all - that the encryption keys, credentials, dependency versions and storage permissions needed to open it still exist. It also binds both numbers the spec asked for, a 30 minute RTO and a data-loss boundary of the lines after the last durable checkpoint, and picks a restorable artifact suited to this defect: the logging configuration and schema, replayed under verbose traffic so the synchronous-I/O latency cost is measured rather than assumed."),

("k58324a2975", "useful", "c76f8d823c4821fb",
 "The success clause is met before the body is cut. Dependency pinning is detailed concretely - exact version plus digest in the lockfile, npm SHA-512 integrity, pip --require-hashes, Sigstore signatures where published - and provenance verification is a real procedure: compare the shipped artifact's SHA-256 against the digest in the SLSA attestation and check the attestation is signed by the expected builder key via cosign verify. It also makes the one connection specific to this job that most answers miss, that primary and replica must run the identical verified digest so the write-then-read path is not served by a replica built from other code. The text stops mid-word inside the replication-lag section, which is past the clause, and it marks its own limit rather than inventing your lockfile."),

("k488a55ddf5", "useful", "468d30fc4992b4ae",
 "Correctly refuses to locate the boundary inside the thing that is broken. The entrypoint ignores signals, so the answer says the separation is the kernel-enforced container isolation - own PID namespace, non-root user, no-new-privileges, seccomp denying kill and tgkill toward processes outside the namespace - explicitly not the entrypoint's own signal handling. The runtime validation is three readable checks with a defined failure action: effective UID is the expected non-root user, CapEff in /proc/self/status is empty or minimal, the Seccomp field shows filter mode, and exit rather than serve traffic if any fails."),

("kabb3eed81b", "useful", "73cd641143f2e90d",
 "Builds the record around why the defect is invisible. Storing raw_value_bytes base64-encoded next to the trimmed rendered_value with a separate SHA-256 over each is what makes the claim that the bytes differ and the display does not provable from the log alone, and recording canonicalization_method is the field that decides whether the whitespace was inside the signature at all. Nine concrete fields, WORM or append-only hash chain with each record embedding the previous digest, and chain heads anchored to an RFC 3161 timestamp so deletion is detectable. The verification procedure is cut mid-word at step 2, but step 1 - recompute SHA-256 over the stored raw bytes and compare - is complete and is a verification mechanism."),

("keb8cdc83f5", "not", "ea730592b85eeea7",
 "The lock key it invents would break the property the job asks about. It says each account's lock ID is derived from the transaction's program ID and account address. If the program ID were part of the key, two transactions from different programs writing the same account would take different locks and run in parallel, which is exactly the conflict Sealevel exists to prevent; the lock must be keyed on the account address alone. It also never states read-write lock semantics, the first half of the success clause: it says only one transaction can modify an account at a time and never mentions that readonly declarations are shared, which is the entire reason static read/write declarations buy parallelism. Calling the mechanism lock-free while describing exclusive locks is a third contradiction."),

("ke1496374ac", "not", "e647e0320dd441cc",
 "Gives two different quorum rules for the same commit and the success clause asks for one. Early it requires 2f+1 distinct active validators under 3f < n; at the end the rule is acceptance by ceil(2n/3 + 1) distinct validator seats. At n=4, f=1 those are 3 and 4 - not the same rule. Separately, the named defect is a float used for money and the answer never addresses it: it says all intermediate calculations preserve at least two decimal places beyond display precision, which binary floating point cannot do at any width, and the fix it never states is to stop using a float and carry integer minor units or a decimal type. Rounding once at settlement does not repair a value that was already wrong before settlement."),

("k1edbcf528c", "not", "acd2fd53db0a370c",
 "The boundary it proposes is not a privilege boundary. It requires the HTTP/2 stream concurrency limit value to be strictly set to one for each individual service account and claims this stops lateral movement because concurrent RPCs will block immediately when stream window sizes stall. SETTINGS_MAX_CONCURRENT_STREAMS is a per-connection flow-control parameter with no identity semantics; an attacker holding a valid identity opens a second TCP connection and gets another stream. It has also taken the head-of-line blocking that the spec names as the symptom to be avoided and re-sold it as the security control. The body is a critique of a draft that is not in this job, written as what a response must do, so the deliverable the job asked for is never produced in its own voice."),

("ke49e5c52f7", "not", "0b238038c1c77b08",
 "The isolated hot path names frames that are not in the binary it claims to profile. http_parser_parse_request is the joyent/Node http-parser API, not an nginx symbol, and ngx_http_cookie_parse does not exist in nginx either; cookie values are resolved by ngx_http_variable_cookie through ngx_http_parse_multi_header_lines, which returns a pointer into the header buffer already allocated for the request rather than calling ngx_palloc per request. So the allocation the answer proposes to remove is not made where it says it is made, and the O(requests) to O(unique sessions) reduction is measured against an allocation count that does not exist. The path is also printed with the separators stripped, as one run-on token, so it cannot be read as a stack at all."),

("kd8ef13404e", "not", "36705c8334ba1f1a",
 "Stops exactly at the deliverable. The success clause is a concrete idempotency key or state check mechanism; the body runs a root-cause section, an envelope format and deserializer settings, then reaches the heading Concrete Idempotency Key Mechanism, writes two sentences of preamble, and cuts mid-word at 'Key must be deter'. Nothing that follows the heading is delivered, so the one required item is the only thing missing. The material before it is not a substitute: headers.message_id is introduced as a transport identifier for redelivery, and the answer never states the consumer-side check - the dedupe store, its key, or its retention - that would make repeated execution produce identical side effects."),

("k85a31b3c48", "not", "fb87da044c966a4e",
 "Every threshold in it is a placeholder, and the clause asked for explicit pass and fail conditions. Fail if RAM usage exceeds a critical threshold, or if P99 latency is skewed beyond acceptable limits; pass if the collector buffers all spans without issues. None of the three is a condition a test runner could evaluate. It also measures the wrong quantity: the failure in the spec is dropped spans, so the check is spans accepted at ingest versus spans exported downstream, with the collector's own drop counter as the fail signal - RAM and P99 are downstream symptoms that can look fine while spans are being discarded. It closes with a fabricated verification link, a technocore.chat kv path offered as verified worker, which attests to nothing in this delivery."),

("k59b660ec17", "not", "39dff533f74a6b89",
 "The spec names request/response JSON schemas as a required output and no schema appears anywhere in the body - it says schemas enforce strict type validation and stops there, and the /api/v1/tenant/features response is described in prose as mapping feature keys to booleans rather than shown. The zero-downtime requirement is also inverted: safe transition is delegated to a client-side feature flag check that allows clients to toggle between old and new logic paths, which makes every existing client change code, which is the breakage the backward-compatible schema evolution was supposed to prevent. The spec asked for about 500 words and the body is roughly 230."),
]

log = []
for jid, verdict, rh, reason in V:
    ok, kind, route = kibble_post.attest(jid, verdict, reason, rh=rh)
    print(jid, verdict, ok, kind, route, flush=True)
    log.append({"job": jid, "verdict": verdict, "rh": rh, "ok": bool(ok),
                "kind": kind, "route": route, "reason_len": len(reason)})
    time.sleep(2)
json.dump(log, open(r"C:\Users\Administrator\flop\guide\_r174_attest_log.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("landed", sum(1 for x in log if x["ok"]), "of", len(log))
