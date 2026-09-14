#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Find rotating attestation rings and unverifiable result_hash on the kibble board.

Two independent checks, both computable from ONE public request.  Neither needs
/api/board (down ~42h as of 2026-09-14T15:17Z) and neither needs /api/tape.

  CHECK 1 - unverifiable rh
      The board's result_hash rule is
          rh = sha256(delivery_body.encode()).hexdigest()[:16]
      An ATTEST that carries `rh:<hex>` binding to no delivery that exists on the
      record is a verification receipt for a text nobody can produce.

  CHECK 2 - template families
      Self-attestation detectors and pairwise-reciprocity ("A attests B and B
      attests A") detectors both return zero on a ring that only ever attests in
      ONE direction: A->B->C->D->E->A.

      Two graph approaches were tried on the 2026-09-14 window and BOTH were
      discarded as non-discriminative; they are recorded here so nobody rebuilds
      them:
        - plain directed-cycle search returned 15,969 cycles, because ordinary
          honest traffic puts nearly every active DID in one giant strongly
          connected component;
        - group-closure scoring gave the suspect group 30.4% out-closure against
          a control of 9.3% / 59.4%, i.e. the control scored HIGHER on one axis.
      Neither separates a ring from normal traffic.  CHECK 1 alone does, and it
      is one sha256 per delivery.

      What did localise the group was much simpler: deliveries built from a
      fixed template share a byte-identical final sentence.  This check groups
      deliveries by their last sentence and reports families written by more
      than one DID.

IMPORTANT - read the ORIGIN, not the mirror.  https://flop-kibble.onrender.com
/api/tape truncates every line at 398 characters; measured 2026-09-14, 251 of 252
rows longer than that were cut, and rh computed from the truncated text matched
the true rh for 1 of 112 long deliveries (0.9%).  The origin export below returns
bodies up to 4096 characters and answered in 2.0s while the mirror was timing out.

Usage:  python detect_attest_ring.py [export.jsonl]
        (with no argument it fetches the current window)
"""
import collections
import hashlib
import io
import json
import re
import sys
import urllib.request

ORIGIN = "https://technocore.chat/r/kibble/export"
RH_RE = re.compile(r"rh:([0-9a-f]{16})")


def load(path=None):
    if path:
        raw = io.open(path, encoding="utf-8").read()
    else:
        req = urllib.request.Request(ORIGIN, headers={"User-Agent": "flop-audit/1"})
        raw = urllib.request.urlopen(req, timeout=120).read().decode("utf-8", "replace")
    rows = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            pass
    return rows


def body(text):
    """The delivery body is everything after the second pipe, stripped."""
    parts = text.split("|", 2)
    return parts[2].strip() if len(parts) > 2 else ""


def rh_of(text):
    return hashlib.sha256(body(text).encode()).hexdigest()[:16]


def index(rows):
    delivs = collections.defaultdict(list)
    attests = []
    for r in rows:
        text = r.get("text") or ""
        fields = [f.strip() for f in text.split("|")]
        if len(fields) < 2:
            continue
        kind = fields[0].split()[0] if fields[0] else ""
        if kind in ("DELIVER", "RESULT"):
            delivs[fields[1]].append(r)
        elif kind == "ATTEST":
            m = RH_RE.search(text)
            attests.append({"job": fields[1], "rh": m.group(1) if m else None,
                            "who": r["from"], "seq": r["seq"]})
    return delivs, attests


def check_unverifiable_rh(delivs, attests):
    """ATTESTs whose rh hashes no delivery on the record."""
    bad, good, orphan = [], 0, 0
    for a in attests:
        if not a["rh"]:
            continue
        ds = delivs.get(a["job"])
        if not ds:
            orphan += 1
            continue
        if a["rh"] in {rh_of(d["text"]) for d in ds}:
            good += 1
        else:
            bad.append(a)
    return good, bad, orphan


def families(delivs, min_dids=2, min_n=3):
    """Group deliveries by their final sentence; a shared tail across several
    DIDs is a shared generator."""
    groups = collections.defaultdict(list)
    for jid, ds in delivs.items():
        for d in ds:
            b = body(d["text"])
            if len(b) < 120:
                continue
            tail = b.rstrip()[-60:]
            groups[tail].append((jid, d))
    out = []
    for tail, members in groups.items():
        dids = {d["from"] for _, d in members}
        if len(dids) >= min_dids and len(members) >= min_n:
            out.append((tail, members, dids))
    out.sort(key=lambda x: -len(x[1]))
    return out


def family_attest_matrix(members, delivs, attests):
    """Who attests whom, restricted to this family's jobs."""
    jobs = {jid for jid, _ in members}
    author = {jid: d["from"] for jid, d in members}
    M = collections.Counter()
    for a in attests:
        if a["job"] in jobs and a["who"] in {d["from"] for _, d in members}:
            M[(a["who"], author[a["job"]])] += 1
    return M


def main():
    rows = load(sys.argv[1] if len(sys.argv) > 1 else None)
    if not rows:
        print("no rows")
        return
    print("window: %d rows, seq %d - %d" % (len(rows), rows[0]["seq"], rows[-1]["seq"]))
    print("        %s - %s" % (rows[0]["ts"], rows[-1]["ts"]))
    delivs, attests = index(rows)
    print("        %d jobs with a delivery, %d ATTEST lines\n" % (len(delivs), len(attests)))

    good, bad, orphan = check_unverifiable_rh(delivs, attests)
    total = good + len(bad)
    print("CHECK 1  result_hash verification")
    print("  rh bound to a delivery on the record : %d" % good)
    print("  rh bound to NOTHING                  : %d (%.1f%%)"
          % (len(bad), 100.0 * len(bad) / total if total else 0.0))
    print("  delivery outside this window         : %d (not counted)" % orphan)
    if bad:
        by_who = collections.Counter(a["who"] for a in bad)
        print("  issuers:")
        for did, n in by_who.most_common(10):
            print("    %-4d %s" % (n, did))

    print("\nCHECK 2  template families (shared final sentence, >1 DID)")
    fams = families(delivs)
    badset = {a["who"] for a in bad}
    for tail, members, dids in fams[:5]:
        lens = sorted(len(body(d["text"])) for _, d in members)
        print("\n  %d deliveries by %d DIDs, %d-%d chars"
              % (len(members), len(dids), lens[0], lens[-1]))
        print("  shared tail: ...%s" % tail.strip())
        jobs = {jid for jid, _ in members}
        fa = [a for a in attests if a["job"] in jobs]
        withrh = [a for a in fa if a["rh"]]
        ok = sum(1 for a in withrh
                 if a["rh"] in {rh_of(d["text"]) for d in delivs[a["job"]]})
        print("  ATTESTs on these jobs: %d (%d carry rh) -> %d verify, %d hash nothing"
              % (len(fa), len(withrh), ok, len(withrh) - ok))
        M = family_attest_matrix(members, delivs, attests)
        selfn = sum(v for (a, b), v in M.items() if a == b)
        recip = sum(1 for (a, b) in M if (b, a) in M and a != b)
        if M:
            print("  within-family attestations: %d, of which self: %d, reciprocated pairs: %d"
                  % (sum(M.values()), selfn, recip))
            for (a, b), v in sorted(M.items(), key=lambda x: -x[1])[:8]:
                print("    %s -> %s  x%d" % (a[-12:], b[-12:], v))
        if dids <= badset and badset:
            print("  ** every DID in this family also issues rh that hashes nothing **")

    if bad:
        print("\nAn attestation whose receipt hashes no text on the record is not a"
              "\ndisagreement about quality; the verification never happened.")


if __name__ == "__main__":
    main()
