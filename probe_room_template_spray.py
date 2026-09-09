#!/usr/bin/env python3
"""How much of technocore.chat's visible traffic is distinct work, and how much
is a small set of templates re-emitted across many rooms by many DIDs?

Context: @flop_labs 2026-09-09T04:09Z pointed at /humans -- "10k+ agents across
thousands of rooms. No central orchestrator. Growing fast."  Room count, message
count and agent count are three different claims.  This probe measures the third
against the first two: it collapses message bodies to templates and asks how many
DIDs and rooms each template spans.

Honest scoping, stated up front:
  * The room list is capped at the 200 most recently active rooms and does NOT
    paginate (offset is ignored -- verified).  So this samples the ACTIVE window,
    not the 51k-room namespace.  Conclusions are about visible live traffic.
  * Room and topic names are caller-chosen strings; the server says so.  They are
    used here only to bucket, never as a claim about who runs a room.

Falsification:
  F1 "the repeats are legitimate protocol frames"  -> tclk1/kibble protocol lines
     are classified separately and excluded from the template verdict.
  F2 "it is one spammer"                            -> a template only counts as
     spray if it spans MANY DIDs, not one.
  F3 "mailbox rooms are a special case"             -> named rooms are measured
     as an independent control group.
"""
import json, re, urllib.request, collections, sys, time

BASE = "https://technocore.chat"
PER_ROOM = 200


def get(url, timeout=25):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


LINE = re.compile(r"^\[(\d+)\]\s+(\S+)\s+<([^>]+)>\s+(.*)$")


def read_room(room):
    """Return (seq, nick, body) triples from a room's plain-text dump."""
    try:
        txt = get(f"{BASE}/r/{room}?limit={PER_ROOM}")
    except Exception:
        return []
    out = []
    for ln in txt.splitlines():
        m = LINE.match(ln)
        if m:
            out.append((int(m.group(1)), m.group(3), m.group(4)))
    return out


# ---- protocol frames we must NOT count as decorative repetition (F1) --------
PROTO = re.compile(r"^(tclk1\s|JOB v1|CLAIM v1|RESULT v1|DELIVER v1|ATTEST v1|"
                   r"BRIEF v1|HELLO v1|SUBMIT v1|WITNESS v1)")


def templatize(body):
    """Collapse a body to its shape: strip the values, keep the skeleton."""
    s = body
    s = re.sub(r"did:key:[A-Za-z0-9]+", "<did>", s)
    s = re.sub(r"\b0x[0-9a-fA-F]{6,}\b", "<hex>", s)
    s = re.sub(r"\b[0-9a-fA-F]{6,}\b", "<hex>", s)
    s = re.sub(r"\d+", "<n>", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def main():
    rooms_json = json.loads(get(f"{BASE}/rooms?format=json&limit=200"))
    rooms = rooms_json["rooms"]
    print(f"namespace total={rooms_json['total']} capacity={rooms_json['capacity']} "
          f"visible_window={len(rooms)}", flush=True)

    groups = {"mailbox": [r["room"] for r in rooms if r["room"].startswith("mb-")],
              "named":   [r["room"] for r in rooms if not r["room"].startswith("mb-")]}

    report = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "namespace_total": rooms_json["total"],
              "namespace_capacity": rooms_json["capacity"],
              "engagement": rooms_json.get("engagement"),
              "groups": {}}

    for gname, gl in groups.items():
        sample = gl[:60]
        msgs = []                       # (room, nick, body)
        for rm in sample:
            for _seq, nick, body in read_room(rm):
                msgs.append((rm, nick, body))
        if not msgs:
            continue

        proto = [m for m in msgs if PROTO.match(m[2])]
        chat = [m for m in msgs if not PROTO.match(m[2])]

        tpl_dids = collections.defaultdict(set)
        tpl_rooms = collections.defaultdict(set)
        tpl_count = collections.Counter()
        for rm, nick, body in chat:
            t = templatize(body)
            tpl_count[t] += 1
            tpl_dids[t].add(nick)
            tpl_rooms[t].add(rm)

        # F2: spray = a template used by >=10 distinct DIDs in >=5 distinct rooms
        spray = {t: c for t, c in tpl_count.items()
                 if len(tpl_dids[t]) >= 10 and len(tpl_rooms[t]) >= 5}
        spray_msgs = sum(spray.values())

        g = {
            "rooms_sampled": len(sample),
            "messages": len(msgs),
            "protocol_frames": len(proto),
            "non_protocol": len(chat),
            "distinct_dids": len({m[1] for m in msgs}),
            "distinct_templates_non_protocol": len(tpl_count),
            "spray_templates": len(spray),
            "spray_messages": spray_msgs,
            "spray_share_of_non_protocol": round(100.0 * spray_msgs / len(chat), 1) if chat else None,
            "top_templates": [
                {"template": t[:110], "messages": c,
                 "distinct_dids": len(tpl_dids[t]), "distinct_rooms": len(tpl_rooms[t])}
                for t, c in tpl_count.most_common(12)],
        }
        report["groups"][gname] = g
        print(f"\n=== {gname}: {len(sample)} rooms, {len(msgs)} msgs, "
              f"{g['distinct_dids']} DIDs ===", flush=True)
        print(f"  protocol frames {len(proto)}  non-protocol {len(chat)}  "
              f"distinct templates {len(tpl_count)}", flush=True)
        print(f"  SPRAY (>=10 DIDs, >=5 rooms): {len(spray)} templates, "
              f"{spray_msgs} msgs = {g['spray_share_of_non_protocol']}% of non-protocol", flush=True)
        for row in g["top_templates"][:8]:
            print(f"    x{row['messages']:<5d} dids={row['distinct_dids']:<4d} "
                  f"rooms={row['distinct_rooms']:<3d} | {row['template'][:88]}", flush=True)

    json.dump(report, open("_r70_spray.json", "w"), indent=1)
    print("\nwrote _r70_spray.json")


if __name__ == "__main__":
    main()
