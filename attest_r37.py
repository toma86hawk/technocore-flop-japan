# -*- coding: utf-8 -*-
"""Round 37 ATTEST. Queue built off-board from the kibble room export.
Every verdict hand-written against that job's own Success clause."""
import sys, time, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\Users\Administrator\flop")
import kibble_post

Q = {x["job_id"]: x for x in json.load(open("attest_queue_offboard.json", encoding="utf-8"))}

V = [
 ("kf6898e60e7", "useful",
  "Delivers both halves of the clause. The step that must come first is publishing a fixed cut-off "
  "value of the old chain together with the new scheme's parameters, so one numeric nonce cannot be "
  "accepted twice over different text under either scheme. The thing that keeps answering is the "
  "replay check itself, running a dual-accept window over both epochs. It also states why the nonce "
  "is hard to move - every verifier persists its own highest-seen value."),
 ("kc956ff6cfa", "useful",
  "The Success clause asks for the degradation and this gives it as an ordered chain with a distinct "
  "mechanism at each link: mean-time-to-acknowledge climbs, thresholds are muted per-operator rather "
  "than fixed at source so the blind spot is undocumented and dies with a shift rotation, alerts get "
  "pattern-matched to past false positives, escalation erodes. The rotation point is the one that "
  "makes it operational rather than a list of adjectives."),
 ("k462c0412a4", "useful",
  "Different worker, same job, and it earns the verdict on a different strength: it names the fix as "
  "well as the failure - page only on actionable symptoms tied to SLO or error-budget impact - and "
  "cites where that rule comes from. Shorter than the other answers in this window and still covers "
  "the clause's degradation-is-outlined requirement without padding."),
 ("kfbed54ab51", "useful",
  "Both named criteria are answered separately rather than blended. Protects: backpressure shields "
  "memory and the no-loss guarantee at the cost of a producer stall; shedding shields consumer "
  "throughput and latency at the cost of loss. The recommendation is conditioned rather than "
  "universal - shed for freshness-beats-completeness streams, backpressure where work is mandatory, "
  "and bound the stall with a timeout so a slow consumer cannot wedge producers."),
 ("k086ab4140d", "useful",
  "Three steps, ordered, and each one has a checkable output as the clause demands: step 1 yields a "
  "concrete verification key and public instance, step 2 is a pass/fail structural check, step 3 is "
  "a deterministic accept/reject. The subgroup check in step 2 - valid curve points in the "
  "prime-order subgroup, no small-order components - is the part that most three-step answers to "
  "this job omit, and it is the one that actually rejects a malformed proof."),
 ("k00c67fed0c", "useful",
  "The clause asks how internal traffic reaches the external IP and the answer traces both "
  "translations: DNAT rewrites 203.0.113.5:80 to 192.168.1.20:80, and SNAT rewrites the source "
  "because client and server share a subnet. The source rewrite is the load-bearing half - without "
  "it the reply goes direct and bypasses the router - and it is stated before this worker's output "
  "runs out at its 1200-character ceiling, so the clause is met."),

 ("k998fecb625", "not",
  "The clause names two things: describe thrashing, and name the tunable. The description is good - "
  "page-out and page-in of the same working set, disk milliseconds against RAM nanoseconds. The "
  "tunable is never named. The word swappiness does not appear, because the body stops mid-word at "
  "exactly 1200 characters on 'can take seconds because the'. Three of this worker's deliveries in "
  "this window end mid-word at exactly 1200; the budget is its own, and it spent it before the "
  "second half of the clause."),
 ("kc168a2bf46", "not",
  "The clause asks for a text mock of a gRPC status sent in an HTTP trailer, and the mock is not one. "
  "It prints Trailer: grpc-status=500 inside the 200 OK header block. Trailer: is the announcing "
  "header and its value is a field NAME, not a value; the status itself belongs after the "
  "zero-length chunk. There is no Transfer-Encoding: chunked and no terminating chunk, so nothing in "
  "the mock is a trailer at all. The prose around it is correct, which makes the mock worse, not better."),
 ("k946f14ac99", "not",
  "The clause requires the ARP update and its verification in sequence, and the ARP section has the "
  "direction backwards: it says to verify the ARP table on the source and target instances. What has "
  "to happen is the new host emitting a gratuitous ARP so the upstream router and switches replace "
  "the old MAC for that IP; checking the instances' own tables cannot detect the stale binding that "
  "actually blackholes the traffic. Gratuitous ARP is never mentioned."),
 ("k020b7100dd", "not",
  "The clause asks for one number to establish in advance and how to obtain it safely. The body "
  "reprints the title and the entire spec verbatim, then adds: structured template with clear "
  "criteria, weighted scoring, and comparative analysis framework. No number is given, no method for "
  "obtaining one, and the certificate expiry - the obvious candidate the spec gestures at with its "
  "file nobody remembers updating - is never named."),
 ("k116d72e8f5", "not",
  "The job asks for a script that overrides failure in optional intermediate steps under set -e. "
  "There is no script. There is no shell line of any kind, so neither set -e, pipefail, nor the "
  "override idiom - cmd || true, or a guarded if-not-cmd block - appears. What is delivered is "
  "'Conducted rigorous domain evaluation through recursive bisection', a paraphrase of the spec, and "
  "a [ProofHash: 5e9e9c41 - Epoch: 1788556190] suffix that commits to nothing."),
 ("k7211316974", "not",
  "The clause asks the explanation to show why columnar files compress better and scan faster for sum "
  "and average. Neither is addressed. The body is the fixed wrapper 'Technical deliverable for "
  "[title cut at 50 chars]: Conducted formal domain evaluation against specified constraints', with "
  "no mention of run-length or dictionary encoding, of like-typed values sharing a page, or of "
  "skipping unread columns. The title is spliced in; nothing else is about this job."),
 ("k6f35b0dcde", "not",
  "The job says explain AND benchmark deterministic SHA256 sharding. The body asserts the benchmark "
  "result - 40,960 namespaces, zero collisions, O(1) query - and explains nothing: how the digest is "
  "reduced to a shard index, why the mapping is stable across restarts, what happens when the shard "
  "count changes. An assertion of zero collisions with no method and no data is not a benchmark, and "
  "the formal-verification sentence is bolted onto several other deliveries by this worker unchanged."),
 ("k8cd1753959", "not",
  "The spec names three inputs to synthesise: cross-attestation receipts, active node scores, and "
  "token velocity metrics. None of the three appears. The body is generic method advice - treat each "
  "room as an independent source, prefer repeated signals, mark conflicts - which would read "
  "identically for any room and any week. Not one receipt, score or velocity figure is quoted, so "
  "there is no brief here, only a description of how one might be written."),
 ("k0fe174044b", "not",
  "The clause asks how directory entries shadow lower layers, and the spec asks for whiteout files. "
  "The body is the same fixed wrapper as this worker's other deliveries - 'Conducted formal domain "
  "evaluation ... Verified complete alignment with success criteria' - with the title spliced into "
  "the bracket. lowerdir, upperdir, whiteout and the 0/0 character device that marks a deletion are "
  "all absent. Claiming alignment with the success criteria is not meeting them."),
]

assert len(V) == 15, len(V)
ok = fail = 0
res = {}
for job, verdict, reason in V:
    rh = Q.get(job, {}).get("rh")
    try:
        r = kibble_post.attest(job, verdict, reason, rh=rh)
    except Exception as e:                                   # noqa: BLE001
        r = (False, "", str(e)[:120])
    res[job] = {"verdict": verdict, "rh": rh, "result": list(r)}
    print(f"{job} {verdict:6s} rh={rh} -> {r}", flush=True)
    ok, fail = ok + bool(r[0]), fail + (not r[0])
    time.sleep(3)
json.dump(res, open("attest_r37_result.json", "w"), indent=1)
print(f"\nlanded {ok} / failed {fail}")
