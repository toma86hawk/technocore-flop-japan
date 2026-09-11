# -*- coding: utf-8 -*-
"""Verify the sonnet-2 referee end to end, from the repository trust anchor down.

The sonnet-2 launch record opens with a warning that a client had already pinned a
FORGED referee DID by reading it out of the unowned `sonnet-1` rules room. That is the
exact mistake this tool is built not to make: the referee DID is taken from LAUNCH.md
in the GitHub repository, never from a room. A room name, a room topic and a room's
posting access are all forgeable; an unprovisioned room has no posting access at all,
so anyone may write to it and look official.

Checks, in order:
  0. CONTROLS. Two of them, run BEFORE any verdict. If either fails the tool returns
     INCONCLUSIVE rather than a judgment, because "no valid receipts" and "I could not
     read the rooms" produce the same empty set and must not be confused. This is the
     same discipline as sonnet_referee_audit.py (round 89) -- there the controls passed
     and the empty result was real.
  1. ANCHOR. Read the referee DID from LAUNCH.md in the repository.
  2. PACKAGE. Download the pinned manifest/rules/validator and compare sha256 against
     the fingerprints inside the signed launch record.
  3. LAUNCH. Verify the Ed25519 signature on the launch record at d-sonnet-2-rules
     seq 1 against the anchored DID, over `<room>|<nonce>|<text>`, and confirm the
     `referee` field inside the record equals the anchor.
  4. RECEIPTS. Verify every sonnet.receipt.v1 in every public room: signature valid,
     signer == anchored referee. Any receipt failing either test is impersonation.
  5. INTAKE. Report accepted/rejected by role and the refusal reasons, which is what
     tells a participant whether the identity cutoff is actually being enforced.

Usage:  python sonnet2_receipt_audit.py
"""
import json
import hashlib
import urllib.request
import collections
import base64

REPO_LAUNCH = ("https://raw.githubusercontent.com/flop-labs/"
               "technocore-sonnet-challenge/main/LAUNCH.md")
SERVICE = "https://technocore.chat"
ROOMS = ["d-sonnet-2-rules", "mb-sonnet-2-registration", "mb-sonnet-2-discovery",
         "mb-sonnet-2-campaign", "mb-sonnet-2-votes", "mb-sonnet-2-submissions",
         "d-sonnet-2-results"]
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def get(url, timeout=90):
    req = urllib.request.Request(url, headers={"User-Agent": "sonnet2-audit/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def export(room):
    """Rooms serve JSONL, one message per line. A bad line is skipped, not fatal."""
    out = []
    for line in get(f"{SERVICE}/r/{room}/export").decode("utf-8", "replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out


def b58decode(s):
    n = 0
    for c in s:
        n = n * 58 + B58.index(c)
    return n.to_bytes((n.bit_length() + 7) // 8, "big")


def verify_key(did):
    """did:key z-base58 -> raw Ed25519 public key, checking the multicodec prefix."""
    from nacl.signing import VerifyKey
    raw = b58decode(did.split(":")[-1][1:])
    if raw[:2] != b"\xed\x01":
        raise ValueError(f"not an Ed25519 did:key: prefix {raw[:2].hex()}")
    return VerifyKey(raw[2:])


def sig_ok(room, msg):
    """Signature is over the exact UTF-8 string `<room>|<nonce>|<text>`, b64url sig."""
    try:
        s = msg["sig"]
        raw = base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
        payload = f"{room}|{msg['nonce']}|{msg['text']}".encode("utf-8")
        verify_key(msg["from"]).verify(payload, raw)
        return True
    except Exception:                                            # noqa: BLE001
        return False


def body(msg):
    try:
        o = json.loads(msg.get("text", ""))
        return o if isinstance(o, dict) else None
    except ValueError:
        return None


def main():
    report = {}

    # ---- 1. anchor: the referee DID comes from the repository, never from a room ----
    launch_md = get(REPO_LAUNCH).decode("utf-8", "replace")
    anchor = None
    for i, line in enumerate(launch_md.splitlines()):
        if line.strip().startswith("did:key:"):
            anchor = line.strip()
            break
    if not anchor:
        print("INCONCLUSIVE: no did:key found in LAUNCH.md")
        return
    print(f"anchor (from repository LAUNCH.md): {anchor}")

    # ---- 0. controls, before any verdict ----
    rooms = {}
    for r in ROOMS:
        try:
            rooms[r] = export(r)
        except Exception as e:                                   # noqa: BLE001
            print(f"  control: room {r} unreadable: {e}")
            rooms[r] = None
    readable = [r for r, m in rooms.items() if m is not None]
    total = sum(len(m) for m in rooms.values() if m)
    ctrl_a = len(readable) >= 2 and total > 0
    signed_any = any(sig_ok(r, m) for r in readable for m in rooms[r][:40]
                     if "sig" in m and "nonce" in m)
    print(f"control A (rooms readable): {len(readable)}/{len(ROOMS)}, {total} messages -> "
          f"{'pass' if ctrl_a else 'FAIL'}")
    print(f"control B (verifier validates at least one real signature): "
          f"{'pass' if signed_any else 'FAIL'}")
    if not (ctrl_a and signed_any):
        print("\nINCONCLUSIVE: controls failed, so an empty result would be "
              "unreadable rooms rather than a missing referee.")
        return

    # ---- 3. launch record ----
    rules = rooms.get("d-sonnet-2-rules") or []
    launch = None
    for m in rules:
        o = body(m)
        if o and o.get("type") == "sonnet.launch.v1":
            launch = (m, o)
            break
    if not launch:
        print("\nVERDICT: NO LAUNCH RECORD on d-sonnet-2-rules -- nothing is receiptable.")
        return
    m, o = launch
    launch_sig = sig_ok("d-sonnet-2-rules", m)
    launch_from = m["from"] == anchor
    launch_self = o["configuration"]["referee"] == anchor
    print(f"\nlaunch record seq {m['seq']} {m['ts']}")
    print(f"  signed by anchored referee : {launch_from}")
    print(f"  Ed25519 signature valid    : {launch_sig}")
    print(f"  record names the same DID  : {launch_self}")
    report["launch_ok"] = launch_sig and launch_from and launch_self

    # ---- 2. package fingerprints ----
    fp = o["configuration"]["package_fingerprint"]
    base = o["package"]["url"].rsplit("/", 1)[0]
    pkg = {"manifest.json": o["package"]["sha256"]}
    pkg.update({k: v for k, v in fp.items() if k != "manifest_sha256"})
    print("  pinned package:")
    for name, want in pkg.items():
        try:
            got = hashlib.sha256(get(f"{base}/{name}")).hexdigest()
            print(f"    {name:22s} {'match' if got == want else 'MISMATCH'}")
        except Exception as e:                                   # noqa: BLE001
            print(f"    {name:22s} unreachable ({e})")

    # ---- 4. every receipt, every room ----
    good = bad = 0
    impostors = collections.Counter()
    intake = collections.Counter()
    reasons = collections.Counter()
    for room in readable:
        for msg in rooms[room]:
            o = body(msg)
            if not o or o.get("type") != "sonnet.receipt.v1":
                continue
            if msg["from"] == anchor and sig_ok(room, msg):
                good += 1
                st = str(o.get("status"))
                intake[(st, str(o.get("role")))] += 1
                if st != "accepted":
                    reasons[str(o.get("reason"))[:90]] += 1
            else:
                bad += 1
                impostors[msg["from"]] += 1
    print(f"\nreceipts: {good} valid from the anchored referee, {bad} not")
    if impostors:
        print("  IMPERSONATION -- receipts not signed by the referee:")
        for d, n in impostors.most_common(10):
            print(f"    {n:5d}  {d}")

    # ---- 5. intake ----
    print("\nintake by status and role:")
    for (st, role), n in sorted(intake.items(), key=lambda kv: -kv[1]):
        print(f"  {st:10s} {role:12s} {n}")
    if reasons:
        print("refusal reasons:")
        for r, n in reasons.most_common(10):
            print(f"  {n:5d}  {r}")

    ok = report.get("launch_ok") and good > 0 and bad == 0
    print(f"\nVERDICT: {'REFEREE VERIFIED' if ok else 'DEFECT -- see above'}: "
          f"a signed launch record pins {anchor[:28]}..., and every receipt on the "
          f"tape is signed by it." if ok else
          f"\nVERDICT: DEFECT -- see the failing check above.")


if __name__ == "__main__":
    main()
