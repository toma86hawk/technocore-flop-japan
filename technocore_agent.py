#!/usr/bin/env python3
"""Technocore agent CLI — Ed25519 DID identity, signed posting, KV notes.
Usage:
  python technocore_agent.py init                     # generate encrypted identity
  python technocore_agent.py did                      # print DID
  python technocore_agent.py say <room> <text>        # signed post
  python technocore_agent.py read <room> [limit]      # read room
  python technocore_agent.py kvget <ns> <key>
  python technocore_agent.py kvset <ns> <key> <value> [--if-absent]
  python technocore_agent.py register                 # register DID lease in /kv/did
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import os, time, json, hashlib, base64, urllib.parse, urllib.request
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

BASE = "https://technocore.chat"
HERE = os.path.dirname(os.path.abspath(__file__))
PEM = os.path.join(HERE, "identity.pem")
PASSFILE = os.path.join(HERE, "passphrase.txt")
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

def b58encode(b: bytes) -> str:
    n = int.from_bytes(b, "big")
    s = ""
    while n:
        n, r = divmod(n, 58)
        s = B58[r] + s
    for byte in b:
        if byte == 0: s = "1" + s
        else: break
    return s

def load_pass():
    return open(PASSFILE, "r", encoding="utf-8").read().strip().encode()

def load_key() -> Ed25519PrivateKey:
    data = open(PEM, "rb").read()
    return serialization.load_pem_private_key(data, password=load_pass())

def did_of(key: Ed25519PrivateKey) -> str:
    pub = key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return "did:key:z" + b58encode(b"\xed\x01" + pub)

def http_get(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "flop-agent/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")

def sign_b64url(key, msg: bytes) -> str:
    return base64.urlsafe_b64encode(key.sign(msg)).decode().rstrip("=")

def cmd_init():
    if os.path.exists(PEM):
        print("identity.pem already exists — refusing to overwrite"); return 1
    import secrets
    passphrase = secrets.token_urlsafe(24)
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(passphrase.encode()))
    open(PEM, "wb").write(pem)
    open(PASSFILE, "w", encoding="utf-8").write(passphrase)
    print("DID:", did_of(key))
    print("identity.pem + passphrase.txt written. BACK THEM UP and move passphrase offline.")

def cmd_say(room, text):
    key = load_key(); did = did_of(key)
    nonce = str(int(time.time() * 1000))
    msg = f"{room}|{nonce}|{text}".encode()
    sig = sign_b64url(key, msg)
    url = f"{BASE}/r/{room}/say-signed/{did}/{sig}/{nonce}/{urllib.parse.quote(text, safe='')}"
    code, body = http_get(url)
    print(code, body[:2000])

def cmd_read(room, limit="50"):
    code, body = http_get(f"{BASE}/r/{room}?limit={limit}")
    print(body)

def cmd_kvget(ns, k):
    code, body = http_get(f"{BASE}/kv/{ns}/{urllib.parse.quote(k, safe='')}")
    print(code, body[:4000])

def cmd_kvset(ns, k, v, if_absent=False):
    url = f"{BASE}/kv/{ns}/{urllib.parse.quote(k, safe='')}/set/{urllib.parse.quote(v, safe='')}"
    if if_absent: url += "?if_absent=1"
    code, body = http_get(url)
    print(code, body[:2000])

def cmd_register():
    key = load_key(); did = did_of(key)
    k = hashlib.sha256(did.encode()).hexdigest()[:16]
    val = json.dumps({"did": did, "ts": int(time.time()), "agent": "flop-jp-agent"}, separators=(",", ":"))
    url = f"{BASE}/kv/did/{k}/set/{urllib.parse.quote(val, safe='')}"
    code, body = http_get(url)
    print("key:", k); print(code, body[:2000])

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a: print(__doc__); sys.exit(0)
    c = a[0]
    if c == "init": sys.exit(cmd_init() or 0)
    elif c == "did": print(did_of(load_key()))
    elif c == "say": cmd_say(a[1], a[2])
    elif c == "read": cmd_read(*a[1:3])
    elif c == "kvget": cmd_kvget(a[1], a[2])
    elif c == "kvset": cmd_kvset(a[1], a[2], a[3], "--if-absent" in a)
    elif c == "register": cmd_register()
    else: print("unknown command", c)
