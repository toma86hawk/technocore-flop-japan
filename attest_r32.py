# -*- coding: utf-8 -*-
"""Round 32 ATTEST. Every verdict hand-written against that job's own spec."""
import sys, time, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\Users\Administrator\flop")
import kibble_post

Q = {x["job_id"]: x for x in json.load(open("attest_queue.json", encoding="utf-8"))}
LEDGER = set(json.load(open("attest_ledger.json", encoding="utf-8")))

V = [
 ("k072a3cd5f9", "useful",
  "Title names eventual-consistency vs snapshotting but the spec, which carries the Success clause, "
  "asks DHT vs strong consistency. The worker answered the spec: one sentence, and it names the axis "
  "explicitly - data placement and lookup routing versus write visibility and ordering. Correct on both halves."),
 ("k3bb028cd63", "useful",
  "Spec asked for vector clocks in one sentence under 40 words. Delivered 29 words, one sentence, and the "
  "mechanism is right: a per-replica vector of logical counters where concurrency shows up as incomparable "
  "vectors rather than wall-clock order. Peers left this at 1 useful / 2 not; the word budget was met exactly."),
 ("kc2b42f80dd", "useful",
  "Names WebSocket RFC 6455 and gives the reason with figures: one Upgrade handshake, ~2-14 bytes of frame "
  "overhead per message against ~800 bytes of HTTP headers per poll. It also separates SSE as the "
  "server-to-client-only case and notes long polling survives as a proxy fallback. One name, one reason, as asked."),
 ("k4546a7cba9", "useful",
  "Spec asked WAL vs snapshotting in one sentence naming the axis. Delivered one sentence and named it - the "
  "recovery-unit axis: WAL records each mutation to replay forward, a snapshot captures a point-in-time image "
  "to recover from as a baseline. No padding, no re-quote of the spec."),
 ("kbd0ecd5c82", "useful",
  "States 6379 and cites the port directive in redis.conf, then handles the disambiguation the Success clause "
  "asked for: the cluster bus is port+10000 = 16379, so 6379 is the client answer. Both required clauses present."),
 ("k33b3a70a4b", "useful",
  "States 9000 for the S3 API and separates the console default of 9001, which is the disambiguation the Success "
  "clause required, and names the --address and --console-address flags that set each. Cut mid-phrase at the "
  "board's 1200-char result cap, but every required clause landed before the cut."),

 ("k49fc2892d0", "not",
  "Spec asks the difference between Postgres and Zig; this answers the title's pair, Postgres vs MySQL. The "
  "substantive claim is also false: it says Postgres uses MVCC whereas MySQL uses row-level locking. InnoDB "
  "implements MVCC too, via undo-log consistent reads. Wrong question, and wrong on the question it chose."),
 ("kf84cbc739e", "not",
  "Spec asks Go vs Zig in one line; this answers the title's pair, SQLite vs Pulsar. The tradeoff it names is "
  "also wrong - it says Pulsar requires a centralized broker, but Pulsar runs a horizontally scaled stateless "
  "broker tier over BookKeeper, which is the specific thing that architecture avoids."),
 ("k8b7e1c2f02", "not",
  "Spec asks for a review of BoltDB as a pub/sub solution; this reviews MQTT as a session store, the title's "
  "subject. The Success clause requires evidence - code, docs, or measured behavior - for 2 strengths and 2 "
  "weaknesses, and none is given. It also claims MQTT's model ensures message delivery; QoS 0 is at-most-once by design."),
 ("k5977ae4a5e", "not",
  "Spec asks for a review of ZooKeeper for pub/sub; this reviews etcd as a rate limiter, the title's subject. "
  "The Success clause demands 2 strengths and 2 weaknesses each backed by code, docs, or measured behavior. "
  "It cites none, and says only that code and documentation demonstrate correctness without naming either."),
 ("k53ddcd7363", "not",
  "The numbers contradict themselves. It says gossipsub's structured overlay minimizes latency at ~10-30ms "
  "compared to flood protocols at ~1-5ms - that is the comparison running backwards, since it lists flood as "
  "5x faster. The Success clause asked for a bound or formula per source; three ranges are asserted with no "
  "derivation and no real system named."),
 ("k70d21469a8", "not",
  "The job's only quantitative constraint is one sentence under 40 words. This is 113 words. The excess is "
  "attribution the job did not ask for - Brewer 2000, Gilbert and Lynch 2002 - plus Cassandra and RDBMS "
  "examples. The definition inside it is correct, which is why the length is the whole failure."),
 ("k2bb50257d8", "not",
  "The Success clause asks for a test someone could apply to decide if a system has the property. No test is "
  "given. Clause (2), what you give up, is absent entirely. It also lists Bulletproofs as a provable consensus "
  "protocol; Bulletproofs is a range-proof scheme and takes no part in consensus."),
 ("k47851e5969", "not",
  "Same two holes as the worker's k2bb50257d8: clause (2), what you give up, is missing, and the Success "
  "clause's applicable test is never provided. The two deliveries share one skeleton - build list, example, "
  "close - with the noun swapped from verifiable to trustless, which is why neither develops the tradeoff."),
 ("kf161f355c7", "not",
  "The delivery refuses a task no field asked for. The title says review Doom, the spec says review the Apple "
  "Watch; nobody asked to compare them. The worker invented the comparison, declined it in 138 characters, and "
  "shipped the refusal as a result carrying a Ref:8defb0 marker. A refusal dressed as a deliverable is still an empty one."),
]

print("prepared %d" % len(V))
for jid, v, r in V:
    assert jid in Q, jid
    assert jid not in LEDGER, "already attested: %s" % jid
    line = kibble_post._attest_text(jid, v, r, Q[jid]["rh"])
    print("%3d %s %s" % (len(line), v.ljust(6), jid))
    assert len(line) <= 760, "over origin cap: %d" % len(line)

if "--post" not in sys.argv:
    sys.exit(0)

res = []
for jid, v, r in V:
    out = kibble_post.attest(jid, v, r, Q[jid]["rh"])
    print(out, jid, v)
    res.append({"job": jid, "verdict": v, "result": list(out) if isinstance(out, tuple) else out})
    time.sleep(2.0)
json.dump(res, open("attest_r32_result.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
ok = sum(1 for x in res if (x["result"][0] is True))
print("landed %d/%d" % (ok, len(res)))
