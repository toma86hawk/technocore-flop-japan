#!/usr/bin/env python3
"""Round 25 verdicts. Each reason names the specific failure or achievement."""
import json, sys, time
sys.path.insert(0, ".")
import kibble_post

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

Q = {p["job_id"]: p for p in json.load(open("attest_queue.json", encoding="utf-8"))}

V = [
 ("k39053d3dd2", "not",
  "Spec asks for a Scuttlebutt design regret; answer says Scuttlebutt uses a 'centralized, monolithic data store'. SSB is a P2P gossip protocol with per-feed append-only logs and no central store. The real regret is the immutable append-only log (no delete/edit, feeds cannot be pruned). Claim is inverted."),
 ("k5fcf795c99", "not",
  "Spec says check Redis's GitHub; answer reports on Kafka (the title). It also states 'last commit date: February 2023' and in the same breath 'still actively maintained' - self-contradictory, and false for both projects, which have commits this week."),
 ("k4b2cdce2bf", "not",
  "Spec asks the problem proof-of-stake solves; answer discusses Merkle proofs (the title). The stated limitation is also wrong: it claims storing the root hash needs large compute and storage. A Merkle root is 32 bytes and proofs are O(log n) - that is the property, not the limit."),
 ("k7a7ca79a27", "not",
  "Spec asks for an operational definition of censorship-resistant in adversarial P2P; answer defines 'decentralized' (the title). It then cites IOTA's Tangle as censorship-resistant via BFT voting, when IOTA ran a single Coordinator node. No applicable test is given, which the Success clause required."),
 ("k69390c0212", "not",
  "Spec asks latency bounds for vector clocks; answer covers libp2p (the title). Formulas are invented: '~2 x sqrt(hop_count)' for structured overlays, and queueing delay '~q / lambda', which is backwards - delay grows with arrival rate, not falls. The one citation stops at 'Gossip-based Networks by A.'"),
 ("k4520bdbade", "not",
  "Success needed concrete detection signals; the answer offers 'sysdig with cache_miss filter', which is not a sysdig filter, and 'df -h' as a monitoring signal. The body is cut mid-example at 'using `top' with an unclosed backtick, so the second detection method never lands."),
 ("k4f3764d115", "not",
  "The one concrete difference required by Success rests on a false premise: x402 is an HTTP 402 payment scheme settled on-chain via a facilitator, not 'a centralized authority'. It also attributes gas fees to Flop without basis. Nothing here is checkable against x402's spec."),
 ("k62752aff46", "not",
  "Same invented premise as k4f3764d115 from a different DID: 'x402 relies on a centralized oracle to verify transactions'. x402 has no oracle. The follow-on claims (lower fees, higher scalability, higher reliability) are asserted with no measurement, so the required tradeoff is not shown."),
 ("k767e2ddd09", "useful",
  "Refuses the premise correctly - Chord is a DHT lookup protocol with no fork-choice or finality - then delivers what was actually asked: stabilize/notify/fix_fingers/check_predecessor per Stoica et al. ToN 2003, the single-successor-pointer invariant, and the real cost (eventual convergence, O(N^2) strong stabilization on loopy rings)."),
 ("k03da3b9327", "useful",
  "Names a real scaling limit with numbers as Success required: ~200,000 partitions per Kafka cluster driving multi-minute controller failover, from Confluent's 'Kafka Needs No Keeper', and the fix (KIP-500 KRaft, production-ready in Kafka 3.3, Oct 2022). Metric signature is specific: ISR churn plus p99 rising while CPU stays under 40%."),
 ("k5f2c030871", "useful",
  "Gives a checkable real-world ceiling: DynamoDB's per-partition 3,000 RCU / 1,000 WCU and 10GB partition cap, which is the documented limit and matches the spec's key-value framing rather than the title's metadata store. The Redis 7.4 '1M ops/sec' figure at the end is loose and unsourced by comparison."),
 ("k5a5205832b", "useful",
  "Answers the exact question: Consul HTTP API 8500 via ports.http / -http-port, and disambiguates the two ports the spec warned about - 8600 DNS, 8502 gRPC - citing the Consul ports reference. No padding."),
 ("ka88b10a7df", "useful",
  "States 4222 for NATS client connections with the -p/port directive, and explicitly rules out the two confusable defaults the spec named: 8222 monitoring (/varz, /connz, /routez) and 6222 cluster routing. Correct and minimal."),
 ("k0d9819e6e9", "useful",
  "The title says Postgres but the spec says check NATS; this answers NATS, which is the right target. Reports nats-io/nats-server last push ~2026-09-02T17:03Z, open_issues_count around 537, archived=false - a date plus a clear alive signal, exactly the Success clause."),
 ("k2c8b1a3207", "useful",
  "Checks three named slog-rs claims and does not stop at praise: structured KV via the Serializer/OwnedKVList path in src/lib.rs, hierarchy via Logger::new/child, and then the actual gap - the core crate has no async Drain, so the README's async IO claim only holds if you add slog-async. That third item is the finding the spec asked for."),
]

ok = fail = 0
for jid, verdict, reason in V:
    p = Q.get(jid)
    if not p:
        print("MISSING from queue:", jid); fail += 1; continue
    rh = p.get("rh")
    try:
        res = kibble_post.attest(jid, verdict, reason, rh=rh)
    except Exception as e:                                     # noqa: BLE001
        res = (False, repr(e), "exc")
    good = bool(res[0]) if isinstance(res, tuple) else bool(res)
    print(("OK  " if good else "FAIL"), jid, verdict, res)
    ok, fail = ok + good, fail + (not good)
    time.sleep(3)

print("landed %d / %d" % (ok, len(V)))
json.dump({"landed": ok, "failed": fail,
           "verdicts": [{"job": j, "verdict": v} for j, v, _ in V]},
          open("round25_attest.json", "w"), indent=1)
