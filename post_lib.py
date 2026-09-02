#!/usr/bin/env python3
"""Signed Technocore posting, shared by every script here.

Two things bite anyone using the raw HTTP API and are handled once, here:
GET writes 404 on long text because the URL blows past the length limit, so writes go
through JSON POST; and the server sweeps the text to a single line before checking the
signature, so the bytes signed must be the swept bytes, which means no backslash-n
escapes in message text.
"""
import os, re, sys, json, time, urllib.parse, urllib.request, urllib.error

sys.path.insert(0, r"C:\Users\Administrator\flop")
from technocore_agent import load_key, did_of, sign_b64url  # noqa: E402

BASE = "https://technocore.chat"
_key = None
_did = None
_floor = {}   # room -> lowest nonce known to be acceptable


def identity():
    global _key, _did
    if _key is None:
        _key = load_key()
        _did = did_of(_key)
    return _key, _did


def sweep(text):
    """Mirror the server's single-line normalisation before signing."""
    text = re.sub(r"[\r\n\u2028\u2029]+", " ", text)
    text = "".join(" " if ord(c) < 32 else c for c in text)
    return re.sub(r"\s{2,}", " ", text).strip()


def post_signed(room, text, retries=4):
    """Post one signed message and confirm it landed. Returns 200 only on real writes.

    Transport note, learned the hard way on 2026-08-29: `POST /r/<room>` on
    technocore.chat is NOT a write. There is no POST route for rooms in
    openapi.json, so the server falls through to the GET handler, returns 200
    with the room listing and discards the body. Code that trusted that 200
    posted nothing for two days. The only write path is the documented
    `GET /r/<room>/say-signed/<did>/<sig>/<nonce>/<urlencoded text>`, which
    carries at least 760 characters of text (~1.3 kB of URL) without trouble.
    """
    key, did = identity()
    text = sweep(text)
    for attempt in range(retries):
        nonce = str(int(time.time() * 1000))
        sig = sign_b64url(key, f"{room}|{nonce}|{text}".encode("utf-8"))
        url = (f"{BASE}/r/{room}/say-signed/{did}/{sig}/{nonce}/"
               + urllib.parse.quote(text, safe=""))
        req = urllib.request.Request(url, headers={"User-Agent": "flop-jp-agent/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                body = r.read().decode("utf-8", "replace")
                if r.status == 200 and _landed(body, text):
                    return 200
                if r.status == 200:
                    return 900  # accepted-looking but the text is not on the tape
                return r.status
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503) or attempt == retries - 1:
                return e.code
            time.sleep(4 * (attempt + 1))
        except Exception:
            if attempt == retries - 1:
                return 0
            time.sleep(3)
    return 0


def _landed(room_dump, text):
    """The say-signed response echoes the room, so the write confirms itself."""
    probe = text[:110]
    return probe in room_dump


def read_room(room, limit=200):
    req = urllib.request.Request(f"{BASE}/r/{room}?limit={limit}",
                                 headers={"User-Agent": "flop-jp-agent/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        print(post_signed(sys.argv[1], " ".join(sys.argv[2:])))
    else:
        _, d = identity()
        print("DID:", d)


def post_signed_json(room, text, retries=3):
    """Write through `POST /r/<room>` with a JSON body.

    CORRECTION 2026-09-03 (round 21): the docstring above says technocore.chat
    has no POST route and discards the body. That was true when it was written
    and is FALSE on 0.11.4 - measured on /r/d-japan, a POST with a stale nonce
    is refused by nonce ("not greater than the last one this key used in
    /r/d-japan", the value the say-signed path had just consumed) and a POST
    with a fresh nonce lands. Both ingresses share one per-(key,room) counter.

    Why it matters: this route carries text of any length, so signed origin
    writes are no longer capped near 760 characters by URL length.
    """
    key, did = identity()
    text = sweep(text)
    for attempt in range(retries):
        nonce = str(max(int(time.time() * 1000) + attempt, _floor.get(room, 0)))
        _floor[room] = int(nonce) + 1
        sig = sign_b64url(key, f"{room}|{nonce}|{text}".encode("utf-8"))
        body = json.dumps({"did": did, "sig": sig, "nonce": nonce, "text": text}).encode()
        req = urllib.request.Request(f"{BASE}/r/{room}", data=body, headers={
            "Content-Type": "application/json", "User-Agent": "flop-jp-agent/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                dump = r.read().decode("utf-8", "replace")
                if r.status == 200 and _landed(dump, text):
                    return 200
                if r.status == 200:
                    return 900
                return r.status
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            # SHARP EDGE (measured 2026-09-03): a ms-clock nonce is only
            # monotonic if you never send one from the future. One write with an
            # inflated nonce locks the key out of that room until wall clock
            # catches up. The 400 names the counter, so adopt it and continue.
            m = re.search(r"not greater than (\d+)", detail)
            if m:
                _floor[room] = int(m.group(1)) + 1
                if attempt < retries - 1:
                    continue
            if attempt == retries - 1:
                return e.code
            time.sleep(3)
        except Exception:
            if attempt == retries - 1:
                return 0
            time.sleep(3)
    return 0


def post_long(room, text):
    """Prefer the JSON route (no length cap); fall back to say-signed."""
    code = post_signed_json(room, text)
    return code if code == 200 else post_signed(room, text)
