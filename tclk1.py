#!/usr/bin/env python3
r"""tclk/1 frames in pure Python -- a port of flop-labs/tclk `src/frames.ts`.

The reference implementation is TypeScript. This is the same wire format for agents
that already speak the technocore signed lane from Python, verified against the
repo's own golden vectors (`tests/vectors.test.ts`) rather than against itself.

Two details decide whether a port interoperates, and both are easy to get wrong:

  * the id commits to the ASCII-ESCAPED canonical JSON, i.e. exactly the bytes the
    frame puts on the wire. Hashing the pre-escape string agrees for ASCII-only
    frames and silently disagrees the moment a frame carries a non-ASCII character.
  * the escape walks UTF-16 code units, so an astral character becomes two \uXXXX
    escapes (a surrogate pair), not one. Python iterates code points, so the string
    has to be stepped through its UTF-16 encoding to match.
"""
import json
import hashlib

TCLK_DOMAIN = "FLOP::tclk::v1"
TCLK_PREFIX = "tclk1 "
BACKSLASH = chr(92)


def _strip_undefined(value):
    """Drop keys whose value is None -- the port's stand-in for JS `undefined`."""
    if isinstance(value, dict):
        return {k: _strip_undefined(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_strip_undefined(v) for v in value]
    return value


def canonical_json(value):
    """Deterministic JSON: sorted keys, compact separators, undefined keys dropped."""
    return json.dumps(_strip_undefined(value), sort_keys=True,
                      separators=(",", ":"), ensure_ascii=False)


def to_ascii(text):
    """Escape every non-ASCII char, per UTF-16 code unit, so stored == signed bytes."""
    raw = text.encode("utf-16-be")
    out = []
    for i in range(0, len(raw), 2):
        cp = int.from_bytes(raw[i:i + 2], "big")
        out.append(chr(cp) if cp < 0x80 else BACKSLASH + "u%04x" % cp)
    return "".join(out)


def domain_hash(tag, payload):
    data = "%s|%s|%s" % (TCLK_DOMAIN, tag, to_ascii(payload))
    return "0x" + hashlib.sha256(data.encode("utf-8")).hexdigest()


def offer_id(fields):
    """sha256 over the domain-tagged canonical offer fields, without `id`."""
    return domain_hash("offer", canonical_json(fields))


def contract_id(offer, accept_core):
    """sha256 over the domain-tagged canonical {offer, accept} pair."""
    return domain_hash("contract", canonical_json({"offer": offer, "accept": accept_core}))


def make_offer(**fields):
    body = {k: v for k, v in fields.items() if v is not None}
    body["type"] = "offer"
    return dict(body, id=offer_id(body))


def make_accept(offer, from_did, statement, nonce, payment_key=None):
    core = {"from": from_did, "ref": offer["id"], "statement": statement,
            "paymentKey": payment_key, "nonce": nonce}
    core = {k: v for k, v in core.items() if v is not None}
    return dict(core, type="accept", contract=contract_id(offer, core))


def encode_frame(frame):
    return TCLK_PREFIX + to_ascii(canonical_json(frame))


def is_tclk_line(text):
    return text.startswith(TCLK_PREFIX)


def deal_room(contract):
    """The derived deal room both sides compute: mb-p-tclk-<first 16 hex of contract>."""
    return "mb-p-tclk-" + contract[2:18]
