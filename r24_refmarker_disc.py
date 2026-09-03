#!/usr/bin/env python3
"""Does the `[Ref:<6hex>]` marker predict anything, without using my own verdicts?

The marker itself is only a label. The question that matters is whether marked
deliveries behave differently. This uses one mechanical discriminator that needs
no human judgement:

  TITLE-FOLLOWING. A large share of kibble jobs have a title naming one system
  and a Success clause naming a different one (we catalogued this as title/spec
  decoupling). On those jobs there is an objectively right target: the Success
  clause. So for every pair where title and spec name different subjects, check
  which subject the delivery actually discusses. Answering the title is a
  mechanical failure, not an opinion.

Subject extraction is deliberately dumb: a fixed vocabulary of system names, so
there is no room to tune it per case. Jobs where the vocabulary finds no clean
title-vs-spec split are dropped, and the drop count is reported.
"""
import json, re, sys, glob, collections

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MARK = re.compile(r"\[Ref:([0-9a-f]{6})\]\s*$")

VOCAB = [
    "Kafka", "Redis", "SQLite", "Postgres", "MySQL", "NATS", "Consul", "Vault",
    "ZooKeeper", "BoltDB", "etcd", "MQTT", "Cassandra", "RabbitMQ", "MinIO",
    "Prometheus", "Pulsar", "CockroachDB", "CouchDB", "DynamoDB", "memcache",
    "Kademlia", "Chord", "HyParView", "gossipsub", "libp2p", "Scuttlebutt",
    "Matrix", "IPFS", "iroh", "go-ethereum", "geth", "hashicorp/raft", "slog",
    "kubo", "Raft", "Paxos", "PBFT", "WebRTC", "GraphQL", "Bluetooth", "5G",
    "blockchain", "XML-RPC", "WebSocket", "gRPC", "Rust", "Kotlin", "Zig",
    "Go", "Java", "CRDTs", "CQRS", "WAL", "DHT", "vector clocks", "quorum",
    "Merkle", "proof-of-stake", "CAP theorem", "pub/sub", "x402", "Flop",
]


def subjects(text):
    t = text.lower()
    return {v for v in VOCAB if re.search(r"(?<![a-z0-9])" + re.escape(v.lower()) + r"(?![a-z0-9])", t)}


def field(p, *names):
    for n in names:
        v = p.get(n)
        if isinstance(v, str) and v:
            return v
    return ""


seen = {}
for f in sorted(glob.glob("attest_runs/*.json")):
    try:
        snap = json.load(open(f, encoding="utf-8"))
    except Exception:                                          # noqa: BLE001
        continue
    ps = snap if isinstance(snap, list) else next((snap[k] for k in ("queue","pairs","items","jobs") if isinstance(snap.get(k), list)), [])
    for p in ps:
        if not isinstance(p, dict):
            continue
        jid, res = field(p, "job_id", "id"), field(p, "result", "body", "text")
        if jid and res:
            seen[jid] = p

tally = {True: collections.Counter(), False: collections.Counter()}
dropped = 0
examples = {True: [], False: []}

for jid, p in seen.items():
    title, spec = field(p, "title"), field(p, "spec", "body_spec", "success")
    res = field(p, "result", "body", "text")
    if not title or not spec:
        dropped += 1
        continue
    st, ss = subjects(title), subjects(spec)
    only_title, only_spec = st - ss, ss - st
    if not only_title or not only_spec:
        dropped += 1                 # no clean decoupled pair to test on
        continue
    sr = subjects(res)
    hit_spec = bool(sr & only_spec)
    hit_title = bool(sr & only_title)
    if hit_spec == hit_title:
        dropped += 1                 # answered both or neither - not decisive
        continue
    m = bool(MARK.search(res.rstrip()))
    tally[m]["followed_title" if hit_title else "followed_spec"] += 1
    if len(examples[m]) < 4 and hit_title:
        examples[m].append((jid, sorted(only_title), sorted(only_spec)))

print("Mechanical test: on jobs whose title and Success clause name different")
print("systems, did the delivery answer the Success clause or the title?")
print("(no human judgement involved; %d of %d pairs dropped as not decisive)\n"
      % (dropped, len(seen)))
for m in (True, False):
    c = tally[m]
    n = sum(c.values())
    lbl = "carries [Ref:] marker" if m else "no marker            "
    if n:
        print("  %s  n=%3d   followed spec %3d (%.1f%%)   followed TITLE %3d (%.1f%%)"
              % (lbl, n, c["followed_spec"], 100.0 * c["followed_spec"] / n,
                 c["followed_title"], 100.0 * c["followed_title"] / n))
    else:
        print("  %s  n=0" % lbl)

print("\ntitle-following examples among marked deliveries:")
for jid, ot, os_ in examples[True]:
    print("   %s  answered %s, spec asked %s" % (jid, ot, os_))
print("title-following examples among unmarked deliveries:")
for jid, ot, os_ in examples[False]:
    print("   %s  answered %s, spec asked %s" % (jid, ot, os_))

json.dump({"marked": dict(tally[True]), "unmarked": dict(tally[False]),
           "dropped": dropped, "pairs": len(seen)},
          open("r24_refmarker_disc.json", "w"), indent=1)
print("\nwrote r24_refmarker_disc.json")
