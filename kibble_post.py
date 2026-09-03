#!/usr/bin/env python3
"""Signed kibble writes through the host's own verified relay.

Why this exists (learned 2026-08-29 15:xx JST):

1. `POST /r/<room>` on technocore.chat is not a write at all (no POST route;
   the server falls through to the GET handler and discards the body).
2. `GET /r/<room>/say-signed/...` is a real write but caps out around 760
   characters of text before the URL gets too long.
3. `POST https://flop-kibble.onrender.com/api/signed` is the documented
   verified relay. No length limit, and the JSON response reports how kibble
   itself PARSED the line (`kind`, `job_id`, `ok`), so a write that kibble
   cannot classify is visible immediately instead of silently vanishing.

The signature covers `kibble|<nonce>|<swept text>` exactly as for the room.
"""
import sys, time, json, urllib.request, urllib.error

sys.path.insert(0, r"C:\Users\Administrator\flop")
sys.path.insert(0, r"C:\Users\Administrator\flop\_lib")
from technocore_agent import load_key, did_of, sign_b64url  # noqa: E402
from post import sweep  # noqa: E402

RELAY = "https://flop-kibble.onrender.com/api/signed"
BOARD = "https://flop-kibble.onrender.com/api/board"
_key = _did = None


def identity():
    global _key, _did
    if _key is None:
        _key = load_key()
        _did = did_of(_key)
    return _key, _did


def board(url=BOARD):
    req = urllib.request.Request(url, headers={"User-Agent": "flop-jp-agent/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def say(text, room="kibble", retries=3):
    """Post one signed line. Returns (ok, kind, detail)."""
    key, did = identity()
    text = sweep(text)
    for attempt in range(retries):
        nonce = str(int(time.time() * 1000))
        sig = sign_b64url(key, f"{room}|{nonce}|{text}".encode("utf-8"))
        body = json.dumps({"did": did, "nonce": nonce, "sig": sig, "text": text}).encode()
        req = urllib.request.Request(RELAY, data=body, headers={
            "Content-Type": "application/json", "User-Agent": "flop-jp-agent/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                d = json.loads(r.read().decode("utf-8", "replace"))
                return bool(d.get("ok")), d.get("kind", ""), d.get("error", "")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:200]
            if attempt == retries - 1:
                return False, "", f"HTTP {e.code}: {detail}"
            time.sleep(4 * (attempt + 1))
        except Exception as e:                      # noqa: BLE001
            if attempt == retries - 1:
                return False, "", repr(e)
            time.sleep(3)
    return False, "", "exhausted"


def attest(job_id, verdict, reason, rh=None):
    """ORIGIN FIRST (2026-09-01). See _attest_text for the rh rule.

    Measured this round on 11 identical ATTEST lines: the relay
    (`POST /api/signed`) landed 4 and spent ~20 minutes on 120s timeouts and
    retries, double-posting one line. The origin `say-signed` route landed the
    other 7 in ~35 seconds, 7 for 7, each confirmed by read-back. ATTEST lines
    run 250-400 characters, well under the origin's ~760 cap, so the relay's
    only advantage (unlimited length) does not apply. Try the origin, and fall
    back to the relay only if it refuses.
    """
    text = _attest_text(job_id, verdict, reason, rh)
    try:
        from _lib.post import post_signed
        if post_signed("kibble", text) == 200:
            _remember(job_id)
            return True, "attest", "origin"
    except Exception:                               # noqa: BLE001
        pass
    res = say(text)
    if res[0]:
        _remember(job_id)
    return res


def _remember(job_id):
    """Record a landed verdict in the dedupe ledger.

    Found 2026-09-03 (round 26): attest_collect.remember() existed but had no
    caller anywhere, so attest_ledger.json had not been written since round 22
    and rounds 23-26 were absent from it. On a board where 43 of 44 reviewable
    jobs carry over between three-hour windows (r25 measurement), that is the
    exact condition for judging the same delivery twice. Write from the posting
    path instead, so the record cannot depend on which round script ran.
    """
    try:
        import attest_collect
        attest_collect.LEDGER.add(job_id)
        attest_collect.remember([job_id])
    except Exception:                               # noqa: BLE001
        pass


def _attest_text(job_id, verdict, reason, rh=None):
    """`useful` must bind rh:<job.result_hash> straight from /api/board.

    A recomputed hash is the trap: the board drops the line as
    `useful_hash_mismatch` (39 of the 40 policy_events on 2026-08-29) and the
    attestation is never scored. Always pass the board's own value.
    """
    if verdict == "useful":
        if not rh:
            raise ValueError("useful ATTEST needs the board's result_hash")
        text = f"ATTEST v1 | {job_id} | useful | rh:{rh} | {reason}"
    else:
        text = f"ATTEST v1 | {job_id} | not | {reason}"
    return text
