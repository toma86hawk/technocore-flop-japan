#!/usr/bin/env python3
"""Collect a Technocore activity dataset for visualisation.

Pulls the kibble tape (structured, timestamped, stage-classified) plus the room index,
and reduces both to a compact JSON the visualisation embeds directly, so the published
page needs no network access of its own.
"""
import sys, os, json, re, time, urllib.request, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
TAPE = "https://flop-kibble.onrender.com/api/tape"
STATS = "https://flop-kibble.onrender.com/api/stats"
ROOMS = "https://technocore.chat/rooms"


def get(url, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": "technocore-viz/1.0 (research)"})
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")


def collect_tape(pages=6, target=3000):
    """Walk backwards from the head in since_seq windows.

    Each request costs about ten seconds, so the page count is bounded rather than
    looping until a size target is hit.
    """
    seen = {}
    head = json.loads(get(f"{TAPE}?limit=500"))
    for m in head.get("messages", []):
        seen[m["seq"]] = m
    print(f"  head: {len(seen)} messages", flush=True)
    cursor = min(seen) if seen else 0
    for page in range(pages):
        if len(seen) >= target or cursor <= 1:
            break
        lo = max(0, cursor - 520)
        try:
            d = json.loads(get(f"{TAPE}?since_seq={lo}&limit=500"))
        except Exception as e:
            print("  warn:", e, file=sys.stderr, flush=True)
            break
        msgs = d.get("messages", [])
        if not msgs:
            break
        for m in msgs:
            seen[m["seq"]] = m
        new_cursor = min(min(m["seq"] for m in msgs), lo)
        print(f"  page {page+1}: total {len(seen)} (cursor {cursor} -> {new_cursor})", flush=True)
        if new_cursor >= cursor:
            break
        cursor = new_cursor
    return [seen[k] for k in sorted(seen)]


def collect_rooms():
    raw = get(ROOMS)
    rooms = []
    for line in raw.splitlines():
        m = re.match(r"^\s*/r/([a-z0-9][a-z0-9_-]{0,47})\s+(\S+)?\s*(.*)$", line)
        if m:
            rooms.append({"name": m.group(1), "size": m.group(2) or "", "topic": (m.group(3) or "").strip()[:90]})
    return rooms


def main():
    rows = collect_tape()
    print("tape messages:", len(rows))
    if not rows:
        return 1

    stats = json.loads(get(STATS))

    # Per-minute activity, split by pipeline stage.
    buckets = collections.defaultdict(lambda: collections.Counter())
    agents = collections.Counter()
    stages = collections.Counter()
    jobs = {}
    for m in rows:
        ts = m.get("ts", "")
        minute = ts[:16]  # YYYY-MM-DDTHH:MM
        kind = (m.get("kind") or "other").lower()
        buckets[minute][kind] += 1
        stages[kind] += 1
        did = m.get("did") or ""
        if did:
            agents[did] += 1
        jid = m.get("job_id")
        if jid:
            j = jobs.setdefault(jid, {"stages": set(), "first": ts, "last": ts})
            j["stages"].add(kind)
            j["last"] = max(j["last"], ts)
            j["first"] = min(j["first"], ts)

    timeline = []
    for minute in sorted(buckets):
        c = buckets[minute]
        timeline.append({"t": minute, **{k: c[k] for k in c}})

    # Funnel: how far each job travelled through the pipeline.
    funnel = collections.Counter()
    for j in jobs.values():
        s = j["stages"]
        if "attest" in s:
            funnel["reached attest"] += 1
        elif "deliver" in s or "result" in s:
            funnel["stopped at deliver"] += 1
        elif "claim" in s:
            funnel["stopped at claim"] += 1
        else:
            funnel["never claimed"] += 1

    data = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "window": {"from": rows[0].get("ts"), "to": rows[-1].get("ts"),
                   "seq_from": rows[0]["seq"], "seq_to": rows[-1]["seq"]},
        "messages": len(rows),
        "stages": dict(stages),
        "timeline": timeline,
        "top_agents": [{"did": d, "n": n} for d, n in agents.most_common(25)],
        "agent_count": len(agents),
        "jobs_tracked": len(jobs),
        "funnel": dict(funnel),
        "network_stats": stats.get("stats", {}),
        "rooms": collect_rooms()[:60],
    }
    out = os.path.join(HERE, "data.json")
    json.dump(data, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("window:", data["window"]["from"], "->", data["window"]["to"])
    print("stages:", data["stages"])
    print("agents seen:", data["agent_count"], "| jobs tracked:", data["jobs_tracked"])
    print("funnel:", data["funnel"])
    print("rooms:", len(data["rooms"]))
    print("wrote", out)


if __name__ == "__main__":
    sys.exit(main() or 0)
