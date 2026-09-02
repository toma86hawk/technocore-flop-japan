#!/usr/bin/env python3
"""Verify tclk1.py against the golden vectors in flop-labs/tclk tests/vectors.test.ts.

The vectors were generated from the TypeScript reference, so a port that disagrees
is wrong. Run: python test_tclk1_vectors.py
"""
import re
import sys

from tclk1 import make_offer, make_accept, encode_frame, deal_room

PAYER = "did:key:z6Mk" + "f" * 44
PAYEE = "did:key:z6Mk" + "g" * 44
OFFER_ID = "0xd001fbbf4fa36d9ab8ea88df02a8b3303539e9d59f7ff9d9bfeb679318e9ce75"
CONTRACT_ID = "0x2768bf32b455317879796093ff2e5882371cbec238611ca71f555a7fcbe58e1c"
NON_ASCII_OFFER_ID = "0xfdad69c602bef151596e3e914cc3ca05b1ccd009211b57c4fdbf0ba0e0d4635b"

OFFER_LINE = (
    'tclk1 {"amount":"1000000","asset":"FLOP","claimByMs":1756703600000,'
    '"expiresMs":1756700600000,'
    '"from":"did:key:z6Mkffffffffffffffffffffffffffffffffffffffffffff",'
    '"id":"%s",'
    '"job":{"context":"ctx-1","id":"task-3f","proto":"a2a"},"lock":"hash",'
    '"nonce":"9f2c81d04c9e1f7a","rails":["flop-htlc","x402"],'
    '"refundAfterMs":1756707200000,"role":"payer","type":"offer"}' % OFFER_ID)

ACCEPT_LINE = (
    '{"contract":"' + CONTRACT_ID + '",'
    '"from":"did:key:z6Mkgggggggggggggggggggggggggggggggggggggggggggg",'
    '"nonce":"0011223344556677","ref":"' + OFFER_ID + '",'
    '"statement":"0x' + "ab" * 32 + '",'
    '"type":"accept"}')
ACCEPT_LINE = "tclk1 " + ACCEPT_LINE

offer = make_offer(**{
    "from": PAYER, "role": "payer", "amount": "1000000", "asset": "FLOP",
    "lock": "hash", "rails": ["flop-htlc", "x402"],
    "claimByMs": 1756703600000, "refundAfterMs": 1756707200000,
    "expiresMs": 1756700600000,
    "job": {"proto": "a2a", "id": "task-3f", "context": "ctx-1"},
    "nonce": "9f2c81d04c9e1f7a"})
accept = make_accept(offer, PAYEE, "0x" + "ab" * 32, "0011223344556677")

# The vector that matters most for a Japanese-language agent: any non-ASCII field
# (a job title in Japanese, say) takes the escaping path, and a port that hashes the
# pre-escape string agrees on every ASCII frame and silently disagrees here.
na = make_offer(**{
    "from": PAYER, "role": "payer", "lock": "hash", "amount": "100", "asset": "FLOP",
    "rails": ["flop-htlc"], "claimByMs": 1756703600000,
    "refundAfterMs": 1756707200000, "expiresMs": 1756700600000,
    "job": {"proto": "a2a", "id": "t" + chr(0xe2) + "che-1"},
    "nonce": "9f2c81d04c9e1f7a"})
na_line = encode_frame(na)

CHECKS = [
    ("offer id", offer["id"], OFFER_ID),
    ("offer line", encode_frame(offer), OFFER_LINE),
    ("contract id", accept["contract"], CONTRACT_ID),
    ("accept line", encode_frame(accept), ACCEPT_LINE),
    ("non-ASCII offer id", na["id"], NON_ASCII_OFFER_ID),
    ("non-ASCII line is pure ASCII", bool(re.match(r"^[ -~]*$", na_line)), True),
    ("non-ASCII line carries the escape", (chr(92) + "u00e2") in na_line, True),
    ("derived deal room", deal_room(CONTRACT_ID), "mb-p-tclk-2768bf32b4553178"),
]

failed = 0
for name, got, want in CHECKS:
    if got == want:
        print("PASS  " + name)
    else:
        failed += 1
        print("FAIL  " + name)
        print("   got :", got)
        print("   want:", want)

print()
print("%d/%d vectors pass" % (len(CHECKS) - failed, len(CHECKS)))
sys.exit(1 if failed else 0)
