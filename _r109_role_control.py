#!/usr/bin/env python3
"""Control for the round-109 result: are the 2,827 unbacked voters GATED?

Organizers are exempt from the identity gate by rule. If the unbacked voters
turn out to have been accepted as organizers, our claim collapses. Check the
role on their own registration ACCEPT, in the round-108 export.

Second control: rule out "published, then trimmed" - today's roster must be a
strict superset of round 108's and must still read from seq 1.
"""
import json, collections, datetime

REFEREE = "did:key:z6MkowHQwsx9xr84WbWN3YCnKutyBnBXkT1ChKY4uEAAMzte"


def body(r):
    try:
        return json.loads(r["text"])
    except Exception:
        return {}


def rows(p):
    out = []
    for line in open(p, encoding="utf-8"):
        line = line.strip()
        if line.startswith("{"):
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def accepted_voters(rs):
    out = set()
    for r in rs:
        if r["from"] != REFEREE:
            continue
        o = body(r)
        if o.get("status") != "accepted":
            continue
        t = o.get("type")
        if t == "sonnet.receipt.v1" and o.get("sender_did"):
            out.add(o["sender_did"])
        elif t == "sonnet.receipts.v1":
            for it in o.get("receipts", []):
                if it.get("sender_did"):
                    out.add(it["sender_did"])
    return out


roster_108 = json.load(open("_r108_roster.json", encoding="utf-8"))
roster_now = json.load(open("_r109_roster.json", encoding="utf-8"))
voters = accepted_voters(rows("_r108_mb-sonnet-2-votes.jsonl"))
unbacked = voters - set(roster_108)

# role carried on each DID's registration acceptance
reg = rows("_r108_mb-sonnet-2-registration.jsonl")
role_of = {}
for r in reg:
    if r["from"] != REFEREE:
        continue
    o = body(r)
    if o.get("status") != "accepted":
        continue
    role = o.get("role")
    t = o.get("type")
    if t == "sonnet.receipt.v1" and o.get("sender_did"):
        role_of.setdefault(o["sender_did"], set()).add(role)
    elif t == "sonnet.receipts.v1":
        for it in o.get("receipts", []):
            if it.get("sender_did"):
                role_of.setdefault(it["sender_did"], set()).add(role)

print("=== CONTROL A  what role were the unbacked voters accepted under? ===")
print("  unbacked accepted-ballot DIDs: %d" % len(unbacked))
c = collections.Counter()
for d in unbacked:
    r = role_of.get(d)
    c[",".join(sorted(x or "?" for x in r)) if r else "NO ACCEPT in readable reg window"] += 1
for k, n in c.most_common():
    print("   %6d  %s" % (n, k))
gated = {d for d in unbacked if role_of.get(d) and role_of[d] & {"voter", "writer"}}
org = {d for d in unbacked if role_of.get(d) and role_of[d] & {"organizer"}}
print("  -> gated-role (voter/writer) acceptances: %d ; organizer-exempt: %d" % (len(gated), len(org)))

print("\n=== CONTROL B  backed voters, same window: what is their role? ===")
backed = voters & set(roster_108)
cb = collections.Counter()
for d in backed:
    r = role_of.get(d)
    cb[",".join(sorted(x or "?" for x in r)) if r else "NO ACCEPT in readable reg window"] += 1
for k, n in cb.most_common():
    print("   %6d  %s" % (n, k))

print("\n=== CONTROL C  rule out 'published then trimmed' ===")
print("  roster r108 DIDs %d ; today %d ; dropped %d ; superset %s"
      % (len(roster_108), len(roster_now), len(set(roster_108) - set(roster_now)),
         set(roster_108) <= set(roster_now)))

print("\n=== CONTROL D  who ARE the 7,151 new entries? ===")
new = set(roster_now) - set(roster_108)
print("  new entries %d ; of them, holding an accepted ballot in the r108 votes window: %d"
      % (len(new), len(new & voters)))
S = datetime.datetime(2026, 9, 11, 12, 0, 0, tzinfo=datetime.timezone.utc).timestamp()
fs = [roster_now[d]["first_seen"] for d in new if roster_now[d].get("first_seen")]
print("  new entries with first_seen >= S: %d" % sum(1 for x in fs if x >= S))
if fs:
    print("  their first_seen spans %s .. %s"
          % (datetime.datetime.fromtimestamp(min(fs), datetime.timezone.utc).isoformat(),
             datetime.datetime.fromtimestamp(max(fs), datetime.timezone.utc).isoformat()))
addts = sorted(roster_now[d]["added_ts"] for d in new)
print("  published between %s and %s" % (addts[0], addts[-1]))
