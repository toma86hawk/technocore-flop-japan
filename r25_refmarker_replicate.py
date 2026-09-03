#!/usr/bin/env python3
"""Round 25: the replication round 24 promised, done window-by-window.

Round 24 reported the [Ref:<6hex>] discriminator as marked n=12 -> 58.3% answer
the title vs unmarked n=33 -> 24.2% (Fisher p=0.070, not significant) and said
the next window would re-measure. Re-running the union scan is NOT a
replication: the kibble board is a rolling ~80-job window, so consecutive
snapshots share most of their jobs and the union barely moves. This script

  1. reports the discriminator PER SNAPSHOT, and
  2. isolates the jobs that are new in the newest snapshot - job_ids absent from
     every earlier snapshot - so the newest window can be scored on its own.

It also tests a separate claim about where the marker comes from: if the marker
sits after a body that was cut mid-token, the marker cannot have been emitted by
the pass that wrote the body. That makes it a wrapper suffix, not model output.
"""
import json, re, sys, glob, os, collections

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


def pairs(snap):
    if isinstance(snap, dict):
        for k in ("pairs", "queue", "items", "jobs"):
            if isinstance(snap.get(k), list):
                return snap[k]
        return []
    return snap if isinstance(snap, list) else []


def decisive(p):
    """(marked, followed_title) or None when the pair cannot decide anything."""
    title, spec = field(p, "title"), field(p, "spec", "body_spec", "success")
    res = field(p, "result", "body", "text")
    if not (title and spec and res):
        return None
    st, ss = subjects(title), subjects(spec)
    only_title, only_spec = st - ss, ss - st
    if not only_title or not only_spec:
        return None
    sr = subjects(res)
    hit_spec, hit_title = bool(sr & only_spec), bool(sr & only_title)
    if hit_spec == hit_title:
        return None
    return bool(MARK.search(res.rstrip())), hit_title


snaps = sorted(f for f in glob.glob("attest_runs/*.json")
         if re.match(r"20\d\d-", os.path.basename(f)))   # roundN.json are not board snapshots
seen_before = set()
per_window = []

for f in snaps:
    try:
        snap = json.load(open(f, encoding="utf-8"))
    except Exception:                                          # noqa: BLE001
        continue
    stamp = os.path.basename(f)[:-5]
    all_c = {True: collections.Counter(), False: collections.Counter()}
    new_c = {True: collections.Counter(), False: collections.Counter()}
    ids_here = set()
    for p in pairs(snap):
        if not isinstance(p, dict):
            continue
        jid = field(p, "job_id", "id")
        if not jid:
            continue
        ids_here.add(jid)
        d = decisive(p)
        if d is None:
            continue
        marked, title = d
        all_c[marked]["title" if title else "spec"] += 1
        if jid not in seen_before:
            new_c[marked]["title" if title else "spec"] += 1
    per_window.append((stamp, all_c, new_c))
    seen_before |= ids_here


def line(c):
    n = sum(c.values())
    return "n=%2d title=%2d (%s)" % (n, c["title"],
                                     "%.0f%%" % (100.0 * c["title"] / n) if n else "-")


print("Per-window title-following rate, marked vs unmarked.")
print("ALL = every decisive pair in that snapshot; NEW = only job_ids not seen")
print("in any earlier snapshot (the board is a rolling window, so ALL double-counts).\n")
print("%-22s %-28s %-28s" % ("snapshot", "ALL marked / unmarked", "NEW marked / unmarked"))
for stamp, a, n in per_window:
    if not (sum(a[True].values()) or sum(a[False].values())):
        continue
    print("%-22s %-13s %-14s %-13s %-14s" % (
        stamp, line(a[True]), line(a[False]), line(n[True]), line(n[False])))

newest = per_window[-1]
print("\nNEWEST WINDOW ALONE (%s), jobs never seen in an earlier snapshot:" % newest[0])
for m in (True, False):
    c = newest[2][m]
    nn = sum(c.values())
    print("  %s  %s" % ("marked  " if m else "unmarked", line(c) if nn else "n= 0"))

# ---- where does the marker come from? ----
print("\nMarker provenance: bodies cut mid-token that still carry the marker.")
cut = re.compile(r"[a-z0-9_/\-]$|`[^`]*$", re.I)
hits, marked_total = [], 0
seen_jid = set()
for f in snaps:
    try:
        snap = json.load(open(f, encoding="utf-8"))
    except Exception:                                          # noqa: BLE001
        continue
    for p in pairs(snap):
        if not isinstance(p, dict):
            continue
        jid, res = field(p, "job_id", "id"), field(p, "result", "body", "text")
        if not jid or not res or jid in seen_jid:
            continue
        seen_jid.add(jid)
        m = MARK.search(res.rstrip())
        if not m:
            continue
        marked_total += 1
        head = res.rstrip()[:m.start()].rstrip()
        # unbalanced backtick, or last char is a word character (mid-word cut)
        if head.count("`") % 2 == 1 or re.search(r"[A-Za-z0-9_]$", head):
            hits.append((jid, head[-70:], m.group(1)))

print("  marked deliveries scanned: %d   ending mid-token: %d" % (marked_total, len(hits)))
for jid, tail, ref in hits:
    print("   %s  ...%s  <<[Ref:%s]" % (jid, tail.replace("\n", " "), ref))

json.dump({"per_window": [(s, {str(k): dict(v) for k, v in a.items()},
                           {str(k): dict(v) for k, v in n.items()})
                          for s, a, n in per_window],
           "midtoken_marked": hits, "marked_total": marked_total},
          open("r25_refmarker_replicate.json", "w"), indent=1)
print("\nwrote r25_refmarker_replicate.json")
