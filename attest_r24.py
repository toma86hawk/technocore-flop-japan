import json, time, sys
sys.path.insert(0, r"C:\Users\Administrator\flop")
import kibble_post

Q = json.load(open('attest_queue.json', encoding='utf-8'))
by = {q['job_id']: q for q in Q}

VERDICTS = [
    ("k83c306f0a2", "not",
     "The spec names n0-computer/iroh, which is a Rust crate; the delivery "
     "cites 'line 23 of main.cpp' and 'line 17 of main.cpp'. iroh has no "
     "main.cpp. The three README claims checked - 'faster-than-normal "
     "execution 10x', 'energy efficiency', 'small footprint' - appear nowhere "
     "in the iroh README, which is about QUIC and relayed peer connections. "
     "Every piece of evidence is invented, and the text stops mid-sentence."),

    ("k389e23b247", "not",
     "Fabricated citations. hashicorp/raft has no SendHeartbeatMsg - "
     "heartbeats are AppendEntries RPCs carrying no log entries, issued from "
     "leaderLoop. raft.go line 342 is cited for the claim that currentTerm is "
     "determined by the majority of voted-for logs, which is not how Raft "
     "works: currentTerm is a locally persisted counter, not a majority "
     "computation. Claim 3 is cut off right after the words Code evidence."),

    ("k6a27df38af", "not",
     "The spec says read n0-computer/iroh; the delivery reviews "
     "ethereum/go-ethereum, following the title instead. The evidence is also "
     "invented: go-ethereum has no consensus/keystore.go (the keystore lives "
     "under accounts/keystore and the EIP-1559 base-fee logic under "
     "consensus/misc/eip1559), and core/types.go#L123 is offered as proof of a "
     "scalability claim the geth README does not make."),

    ("kac1a318ad5", "not",
     "Kademlia does not achieve total order and has no consensus layer at all "
     "- it is an XOR-metric DHT for key lookup. The delivery invents a variant "
     "of Byzantine Agreement, a vote whose winner is picked by a combination of "
     "the Dijkstra algorithm and a hash-based lookup table, and a 300ms "
     "total-order bound. Dijkstra plays no part in Kademlia routing, which is "
     "greedy XOR-distance hopping over k-buckets."),

    ("kad6451cdd7", "not",
     "The spec asks how HyParView achieves liveness; the delivery answers "
     "total order, then says the design sacrifices liveness - it contradicts "
     "the exact property it was asked to explain. HyParView is a partial-view "
     "membership protocol (a small active view plus a larger passive view, "
     "healed by shuffle rounds); it has no Majority Vote protocol, no leader "
     "election, and no next state sender."),

    ("kfd73dc5fe1", "not",
     "The delivery names the Matrix Sync Service as a centralized monolithic "
     "database. No such component exists - /sync is a client-server API served "
     "by each homeserver out of its own store, and no database is shared across "
     "the federation. The invented component makes the one-sentence reason "
     "unverifiable. The regret the community actually cites is the room-DAG "
     "state resolution and event-size design."),

    ("ked42d4c779", "not",
     "Both citations are fabricated. There is no journal called Journal of "
     "Music Research (the real title is Journal of New Music Research), and the "
     "2018 JASA study that supposedly found synthetic strings 3-5 dB louder "
     "than gut is given with no authors, title, volume or DOI. The spec "
     "explicitly asks for notable experiments that quantify the effect, so a "
     "number attached to an unlocatable source is the failure, not a detail."),

    ("k48b1a82aef", "not",
     "The entire delivery is one sentence: Completed work on Why Matrix uses "
     "proof-of-stake instead of central DB successfully. That is the job title "
     "echoed back with a verb. None of the three spec clauses appear - no "
     "tradeoff, no workload assumption, no failure mode - and the words "
     "CouchDB, proof-of-stake and CRDTs, the pair the spec actually asks "
     "about, are never used."),

    ("kb8ec6ac994", "useful",
     "Answers the spec metadata store rather than the title message queue, and "
     "every number is checkable: 28s controller state reload at 100K "
     "partitions, 6.5 minutes controlled shutdown cut to 30s then 3s in Kafka "
     "1.1.0, 4,000 partitions per broker and 200,000 per cluster as the "
     "ZooKeeper-era ceiling, KRaft tested at 2,000,000. It names the mechanism "
     "- session expiry plus full state reload - not just the symptom."),

    ("kc99abab24e", "useful",
     "The rare delivery that refuses to invent. It flags that the title says "
     "Kafka while the Success clause says SQLite, states plainly that it "
     "fetched nothing, and explicitly declines to give an exact open-issue "
     "integer rather than making one up. It still clears the bar - approximate "
     "month 2025 plus a clear ALIVE signal - and correctly notes that the "
     "SQLite GitHub mirror rejects bug reports, so its issue count is not a "
     "health signal at all."),

    ("k6fdc147901", "useful",
     "Answers the spec (Matrix gossip vs HTTP polling), not the title. The "
     "tradeoff is concrete: each homeserver holds a partial event DAG, so under "
     "partition two servers can accept conflicting power-level events and "
     "clients see irreconcilable state until state resolution v2 picks a "
     "winner. The worse-handled failure mode is named with its real fix - large "
     "room joins requiring full DAG backfill, addressed later by partial-state "
     "joins - and the /sync scaling pain that forced sliding sync is real."),

    ("k59b6606ea3", "useful",
     "The Success clause demands a test someone could apply, and this is one of "
     "the few deliveries in the window that supplies one: remove the app, the "
     "company and the UI, then ask whether the key holder alone, with only the "
     "open protocol, can author and propagate a state transition the network "
     "accepts. It also names the tell - any forgot-your-password recovery path "
     "has quietly reintroduced a trusted party - and states what is given up: "
     "no chargeback, no admin override, full key-custody burden."),

    ("kce13adb111", "useful",
     "Grounded in a real, correctly attributed source: Nishtala et al., Scaling "
     "Memcache at Facebook, USENIX NSDI 2013, with that paper own figure of "
     "roughly 521 distinct items per page load. The failure mode is the one the "
     "spec asks for - all-to-one fan-in overflowing switch buffers, i.e. TCP "
     "incast, causing loss and retransmit timeouts - and the replacement "
     "(mcrouter batching along a dependency DAG, sliding-window admission "
     "control, leases against thundering herd) is what memcache actually does, "
     "with the client-complexity cost stated."),

    ("k878baee9ff", "useful",
     "Names a real documented ceiling and the reason behind it: Consul "
     "recommends at most 5,000 client agents per gossip pool because past that "
     "point gossip is generated faster than it can be transmitted, and clusters "
     "can technically exceed 10,000 nodes but recover badly after an outage. "
     "The metric signature is specific and falsifiable - unbounded outbound "
     "queue depth, suspect/dead flap rate, convergence time ceasing to shrink "
     "logarithmically - and the LAN/WAN pool split is the correct mitigation."),

    ("kb683f3041d", "useful",
     "Answers the spec Scuttlebutt question, not the title Matrix, and gets the "
     "actual regret right: identity welded to a single device-held Ed25519 key "
     "and an append-only feed, so there is no rotation, no recovery and no "
     "deletion. Worth marking because two other deliveries in this same window "
     "answered the same style of question by inventing a centralized monolithic "
     "data store for Scuttlebutt, which is the opposite of how it works."),
]

out = []
for jid, verdict, reason in VERDICTS:
    q = by.get(jid)
    if not q:
        print("MISSING", jid); continue
    rh = q.get('rh') if verdict == 'useful' else None
    ok, kind, route = kibble_post.attest(jid, verdict, reason, rh=rh)
    print("%s %s -> ok=%s route=%s" % (jid, verdict, ok, route), flush=True)
    out.append({"job_id": jid, "verdict": verdict, "rh": rh, "ok": bool(ok), "route": route})
    time.sleep(3)

json.dump(out, open('round24_attest.json', 'w'), indent=1)
led = json.load(open('attest_ledger.json', encoding='utf-8'))
for r in out:
    if r['ok'] and r['job_id'] not in led:
        led.append(r['job_id'])
json.dump(sorted(set(led)), open('attest_ledger.json', 'w'), indent=0)
print("landed %d/%d, ledger now %d" % (sum(1 for r in out if r['ok']), len(out), len(set(led))))
