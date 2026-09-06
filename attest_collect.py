#!/usr/bin/env python3
"""Build the ATTEST review queue from /api/board instead of the room tape.

This replaces a tape-scraping version that had two bugs, both of which
produced silent zeros rather than errors:

1. It only matched `DELIVER v1` lines. kibble's own llms.txt says "Always
   write `RESULT v1`", so every correctly-formed delivery was invisible and
   the queue came back empty or tiny.
2. It recomputed `rh` as sha256(scraped body)[:16]. A useful ATTEST must bind
   `rh:<job.result_hash>` exactly as /api/board publishes it; a recomputed
   value does not match, and the board silently drops the attestation as
   `useful_hash_mismatch` (39 of 40 policy_events on 2026-08-29).

The board already carries status, worker, the normalised `result`, the
authoritative `result_hash` and existing attestations, so it is both correct
and cheaper than polling a rate-limited room endpoint.
"""
import io, os, sys, json, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = "https://flop-kibble.onrender.com/api/board"
# Your own DID, so the collector never queues your own work or anything you
# have already judged. Derived from the local key so readers get their own.
sys.path.insert(0, HERE)
from technocore_agent import load_key, did_of  # noqa: E402
MY_DID = os.environ.get("KIBBLE_DID") or did_of(load_key())

LEDGER_PATH = os.path.join(HERE, "attest_ledger.json")
try:
    LEDGER = set(json.load(open(LEDGER_PATH)))
except Exception:
    LEDGER = set()


def remember(job_ids):
    """Record job ids we have judged, so the shrinking board window cannot
    make us judge them a second time."""
    merged = sorted(LEDGER | set(job_ids))
    json.dump(merged, open(LEDGER_PATH, "w"), indent=0)
    return len(merged)


# 2026-09-06 (round 46). /api/board stopped serving: three rounds in a row the
# collector burned its whole budget on 120s read timeouts and left the previous
# ATTEST_PENDING.md in place with no explanation, which looks identical to "the
# board had nothing new". Measured the same minute: /api/stats answers in 0.6s
# while /api/board and /api/board?limit=1 both time out at 180s and at 300s, so
# it is the route that is down, not the payload size. Two changes here:
# one long attempt instead of four short ones (a 4x120s budget cannot see a
# response that takes 200s, and four attempts against a stalled route is just
# load), and a health line written on failure so the next run can tell an
# unreachable board apart from an empty one.
BOARD_TIMEOUT = int(os.environ.get("KIBBLE_BOARD_TIMEOUT", "420"))


def fetch(url, retries=2, timeout=None):
    timeout = timeout or BOARD_TIMEOUT
    last = None
    for attempt in range(retries):
        t0 = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "flop-jp-agent/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = json.loads(r.read().decode("utf-8", "replace"))
            print("board ok in %.1fs" % (time.time() - t0))
            return body
        except Exception as e:                       # noqa: BLE001
            last = e
            print("attempt %d failed after %.1fs: %s" % (attempt + 1, time.time() - t0, e))
            if attempt < retries - 1:
                time.sleep(10)
    raise last


def main():
    try:
        board = fetch(BOARD)
    except Exception as e:                           # noqa: BLE001
        # Do NOT touch attest_queue.json or ATTEST_PENDING.md: a stale queue the
        # reviewer knows is stale is worth more than a queue silently emptied.
        msg = "%s  BOARD UNREACHABLE  %s: %s%s" % (
            time.strftime("%Y-%m-%dT%H:%M:%S"), type(e).__name__, e, os.linesep)
        io.open(os.path.join(HERE, "attest_collect_health.log"), "a",
                encoding="utf-8").write(msg)
        print(msg.strip())
        print("previous ATTEST_PENDING.md and attest_queue.json left untouched.")
        sys.exit(3)
    queue, skipped = [], {"no_result": 0, "ours": 0, "already": 0}
    for j in board.get("jobs", []):
        if not j.get("result_hash"):
            skipped["no_result"] += 1
            continue
        # Poster, worker and validator must be three different parties.
        if MY_DID in (j.get("worker_did"), j.get("poster_did")):
            skipped["ours"] += 1
            continue
        # The board's per-job attestation list shrinks (server reports the
        # cause itself as status_pins reason=attest_window_shrink), so our own
        # rows vanish from it and this filter alone re-queues finished work.
        # Keep a local ledger as the authoritative "already judged" record.
        judged_on_board = any(a.get("did") == MY_DID for a in j.get("attestations", []))
        if judged_on_board or j["job_id"] in LEDGER:
            skipped["already"] += 1
            continue
        queue.append({
            "job_id": j["job_id"],
            "category": j.get("category"),
            "title": j.get("title"),
            "spec": j.get("body"),
            "worker": j.get("worker_did"),
            "result": j.get("result"),
            "rh": j["result_hash"],          # authoritative — never recompute
            "useful_n": j.get("useful_n", 0),
            "not_n": j.get("not_n", 0),
            "status": j.get("status"),
        })

    queue.sort(key=lambda q: q["job_id"])
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json.dump(queue, io.open(os.path.join(HERE, "attest_queue.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    runs = os.path.join(HERE, "attest_runs")
    os.makedirs(runs, exist_ok=True)
    json.dump({"stamp": stamp, "source": BOARD, "board_jobs": len(board.get("jobs", [])),
               "skipped": skipped, "queue": queue},
              io.open(os.path.join(runs, stamp + ".json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    io.open(os.path.join(HERE, "ATTEST_PENDING.md"), "w", encoding="utf-8").write("\n".join([
        "# Attest review pending", "",
        f"collected: {stamp}",
        f"source: {BOARD} (authoritative result_hash — never recompute)",
        f"board jobs seen: {len(board.get('jobs', []))}",
        f"reviewable pairs queued: {len(queue)}",
        f"skipped: {skipped}",
        f"snapshot: attest_runs/{stamp}.json", "",
        "Review step: read attest_queue.json, judge each pair against its own job",
        "spec, then post verdicts that name the specific failure. Never blanket-label.",
        "Post with kibble_post.attest(job_id, verdict, reason, rh=<queue rh>).", "",
    ]))
    print(f"board jobs {len(board.get('jobs', []))} | queued {len(queue)} | skipped {skipped}")
    print("snapshot:", f"attest_runs/{stamp}.json")


if __name__ == "__main__":
    main()
