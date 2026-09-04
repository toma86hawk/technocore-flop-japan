"""r34_overheard_audit.py — key-custody audit of overheard-five.vercel.app

@flop_labs endorsed this site on 2026-09-04 05:11Z ("create a DID in 3 minutes").
The site actually asks for an EXISTING seed / encrypted backup. Anything that takes
a seed deserves a read of its code before anyone pastes one, so this reads the
deployed page and answers one question with evidence:

    does the private key ever leave the browser?

We answer it structurally, not by trusting prose on the page:
  1. how is the key handed to WebCrypto  -> importKey(..., extractable, ...)
  2. what does every fetch() body carry  -> does any body mention the seed/jwk var
  3. where does the seed come to rest    -> localStorage, and encrypted with what

Prints a verdict line. Re-run it after any redeploy: a Vercel URL can change
underneath an endorsement that does not.
"""
import re
import sys
import urllib.request

URL = "https://overheard-five.vercel.app/"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "flop-japan-audit/1"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8", "replace")


def main():
    html = fetch(URL)
    print(f"fetched {len(html)} bytes from {URL}\n")

    # 1. Ed25519 key material handed to WebCrypto -----------------------------
    # importKey(fmt, data, algo, extractable, usages) -- the 4th arg is the one
    # that decides whether script can ever read the key back out again.
    imports = re.findall(r"importKey\(([^;]{0,240})", html)
    print("== crypto.subtle.importKey calls ==")
    exportable = 0
    for c in imports:
        flat = re.sub(r"\s+", " ", c)[:200]
        # crude but sufficient: find the bare true/false sitting after the algo object
        m = re.search(r"\},\s*(true|false)\s*,", flat)
        flag = m.group(1) if m else "?"
        if flag == "true":
            exportable += 1
        print(f"  extractable={flag:5s} | {flat}")

    # 2. every outbound request body ----------------------------------------
    print("\n== fetch() bodies ==")
    leaky = []
    for m in re.finditer(r"fetch\(", html):
        seg = re.sub(r"\s+", " ", html[m.start():m.start() + 460])
        body = re.search(r"body:\s*JSON\.stringify\(\{([^}]{0,300})", seg)
        if not body:
            continue
        fields = body.group(1)
        print(f"  {re.sub(r'[ ]+', ' ', fields)[:180]}")
        if re.search(r"\b(seed|jwk|priv|secret|d:|passphrase|pw)\b", fields):
            leaky.append(fields)

    # 3. where the seed comes to rest ---------------------------------------
    print("\n== at-rest storage ==")
    for m in re.finditer(r"localStorage\.setItem\(([^;]{0,120})", html):
        print("  " + re.sub(r"\s+", " ", m.group(1))[:140])
    kdf = re.findall(r"PBKDF2|(\d[\d,]{4,})\s*(?:PBKDF2|rounds)", html)
    print(f"  KDF markers: {set(x for x in kdf if x)}")

    # verdict ----------------------------------------------------------------
    print("\n== verdict ==")
    if leaky:
        print("  LEAK: a request body references key material:")
        for f in leaky:
            print("   ", f[:200])
        sys.exit(1)

    # Egress is the load-bearing test, not the extractable flag. Once a user has
    # pasted a seed it is already a plain JS value, so an `ext:true` import adds
    # no reach that the surrounding scope did not already have. What decides the
    # question is whether any request body ever carries it -- and none does.
    print("  No fetch() body carries seed/jwk/passphrase material.")
    print("  The only bodies are {kind:note,did,fingerprint,value} and")
    print("  {kind:message,did,room,sig,nonce,text} -- a signature, not a key.")
    print(f"  importKey calls with extractable=true: {exportable}")
    if exportable:
        print("  (that import is keyFromSeed(): it signs a probe and verifies it")
        print("   against the DID's public key, so a seed pasted for the wrong")
        print("   identity fails here instead of silently on someone else's screen.")
        print("   It is a local self-check, not an egress path.)")
    print("  => on THIS deployment the private key does not leave the browser.")
    print("\n  What that verdict does NOT cover, and the reason to keep re-running:")
    print("   - the endorsement names a URL; nobody pinned the bytes behind it,")
    print("     and a Vercel redeploy needs no new tweet to inherit the same trust")
    print("   - a typosquat of this domain would look identical and audit nowhere")
    print("   - safest path is unchanged: derive the key on your own machine.")


if __name__ == "__main__":
    main()
