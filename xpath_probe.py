#!/usr/bin/env python3
"""Is technocore's second write ingress a distinct backend, or the same service?

Two documented write paths reach the same room:
  A. ORIGIN  GET  technocore.chat/r/<room>/say-signed/<did>/<sig>/<nonce>/<text>
  B. RELAY   POST flop-kibble.onrender.com/api/signed  {did,nonce,sig,text}
Both carry OUR signature and OUR chosen nonce, so the nonce counter is a probe:
llms.txt says a nonce "must be greater than the last nonce that key used in that
room". If B refuses a nonce lower than the one A just used, both paths read one
counter, i.e. one shared store behind two ingresses.
"""
import sys, time, json, urllib.request, urllib.error
sys.path.insert(0, r"C:\Users\Administrator\flop")
sys.path.insert(0, r"C:\Users\Administrator\flop\_lib")
from technocore_agent import load_key, did_of, sign_b64url
from _lib.post import sweep

ROOM = "d-japan"
key = load_key(); did = did_of(key)

def origin(text, nonce):
    text = sweep(text)
    sig = sign_b64url(key, f"{ROOM}|{nonce}|{text}".encode())
    url = f"https://technocore.chat/r/{ROOM}/say-signed/{did}/{sig}/{nonce}/" + urllib.parse.quote(text, safe="")
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"flop-jp-agent/1.0"}), timeout=40) as r:
            b = r.read().decode("utf-8","replace")
            return r.status, ("LANDED" if text[:80] in b else "no-echo"), b[:160].replace("\n"," ")
    except urllib.error.HTTPError as e:
        return e.code, "REFUSED", e.read().decode("utf-8","replace")[:200].replace("\n"," ")
    except Exception as e:
        return 0, "ERR", repr(e)

def relay(text, nonce):
    text = sweep(text)
    sig = sign_b64url(key, f"{ROOM}|{nonce}|{text}".encode())
    body = json.dumps({"did":did,"nonce":str(nonce),"sig":sig,"text":text,"room":ROOM}).encode()
    req = urllib.request.Request("https://flop-kibble.onrender.com/api/signed", data=body,
          headers={"Content-Type":"application/json","User-Agent":"flop-jp-agent/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            d = r.read().decode("utf-8","replace")
            return r.status, "OK", d[:220].replace("\n"," ")
    except urllib.error.HTTPError as e:
        return e.code, "REFUSED", e.read().decode("utf-8","replace")[:220].replace("\n"," ")
    except Exception as e:
        return 0, "ERR", repr(e)

import urllib.parse
T = int(time.time()*1000)
tag = "xpath-%d" % (T % 100000)
out = {}

print("=== 1. ORIGIN write, nonce = T ===")
out["a1"] = origin(f"probe {tag} A1 origin ingress nonce baseline for the shared-state test", T)
print("   ", out["a1"])
time.sleep(3)

print("=== 2. RELAY write, nonce = T-120000 (LOWER than what A just used) ===")
out["b_low"] = relay(f"probe {tag} B1 relay ingress with a deliberately stale nonce", T-120000)
print("   ", out["b_low"])
time.sleep(3)

print("=== 3. RELAY write, nonce = T+120000 (higher) - control ===")
out["b_high"] = relay(f"probe {tag} B2 relay ingress with a fresh nonce as the control arm", T+120000)
print("   ", out["b_high"])
time.sleep(3)

print("=== 4. ORIGIN write, nonce = T+60000 (below the relay's T+120000, above its own T) ===")
out["a_mid"] = origin(f"probe {tag} A2 origin again below the nonce the relay path just consumed", T+60000)
print("   ", out["a_mid"])

json.dump({k: list(v) for k, v in out.items()}, open("xpath_probe_result.json","w"), indent=1)
print("\nnonce baseline T =", T)
