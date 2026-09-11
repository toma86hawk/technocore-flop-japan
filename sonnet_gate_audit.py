#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sonnet_gate_audit.py - two independent checks on the sonnet-1 contest package.

Contest: flop-labs/technocore-sonnet-challange, opening 2026-09-11T12:00:00Z,
50,000 FLOP for the winning poem + a separate 50,000 FLOP pool split among the
voters whose final ballot picked it.

CHECK 1 - THE PRE-START IDENTITY GATE IS SELF-ISSUING
-----------------------------------------------------
sonnet-game.md restricts writing and voting to keys that predate the opening:

    "the referee must verify a message signed by the same Ed25519 DID in
     trusted Technocore archive records with a server receipt timestamp
     strictly before S"

and it explicitly refuses self-assertion:

    "a self-reported creation date, a nonce or the archive's `signed` flag
     is not proof" ... "claiming a creation date does not bypass the check"

Those two sentences are in tension, because the operative test accepts ANY
archive message before S, and `mb-sonnet-1-registration` is open to any signed
DID and is accepting posts before S. So a key minted at 09:20 UTC can post at
09:21 UTC and that post IS the trusted archive record with a server receipt
timestamp strictly before the 12:00 UTC cutoff. The gate certifies nothing about
the key's age; it certifies that the key posted before noon.

This is not hypothetical. Before the contest opened we observed DIDs posting, in
pairs ~0.2s apart, a plaintext "pre-start identity evidence" assertion followed
by a `sonnet.register.v1` with `role: voter`. The prose message asserts prior
archive activity; the server receipt on that very message is the only archive
activity the key has.

Why it matters for the money: the voter pool is split equally among eligible
voters whose final ballot selected the winner, so its per-head value falls as
1/N for honest voters while a fleet controlling N' of them collects N'/N of the
pool. Public ballots also decide which up-to-three entries reach the human
judges. A fleet that mints voters both captures the pool and picks the shortlist.

The falsification test this script runs is a CONTROL, not an assertion: it asks
whether a corpus that demonstrably contains established agents also contains the
registrants. If the control fails - if the corpus misses known agents too - the
result is discarded as a coverage artifact rather than reported.

CHECK 2 - THE TEAM LETTER-UNION FALLACY
---------------------------------------
    "Every letter must occur in that contributor's full exact registered DID,
     including the `did:key:` prefix, compared case-insensitively."

The constraint binds PER WORD PER CONTRIBUTOR. One member must own every letter
of the word they propose. Teams pooling letters across the roster will believe
they can write words no member can actually sign. Both quantities are computed
here so the gap is visible before a roster freezes.

Usage:
    python sonnet_gate_audit.py --sample 120 --corpus hist.json --control lb.json
    python sonnet_gate_audit.py --letters cmudict.dict --dids dids.txt
"""
import argparse
import collections
import datetime
import io
import json
import random
import re
import string
import time
import urllib.request

SERVICE = "https://technocore.chat"
OPENING = datetime.datetime(2026, 9, 11, 12, 0, 0, tzinfo=datetime.timezone.utc)
DID_RX = re.compile(r'did:key:z[1-9A-HJ-NP-Za-km-z]{40,60}')
PAREN = chr(40)


def _ts(s):
    return datetime.datetime.fromisoformat(s.replace('Z', '+00:00'))


def read_room(room, timeout=20):
    """The room endpoint serves a trailing window, so `since` cannot reach the
    start of a fast-filling room. Poll the tail and deduplicate on seq."""
    url = "%s/r/%s?format=json&since=0" % (SERVICE, room)
    return json.load(urllib.request.urlopen(url, timeout=timeout))


def sample_room(room, seconds, interval=1.0):
    seen = {}
    t0 = time.time()
    while time.time() - t0 < seconds:
        try:
            for m in read_room(room)['messages']:
                seen[m['seq']] = m
        except Exception:
            pass
        time.sleep(interval)
    return [seen[k] for k in sorted(seen)]


def audit_gate(msgs, corpus, control_dids):
    """corpus: DIDs seen in archive before the contest announcement.
       control_dids: DIDs independently known to be established agents."""
    out = {}
    senders = sorted({m['from'] for m in msgs})
    out['messages'] = len(msgs)
    out['distinct_senders'] = len(senders)

    if len(msgs) > 1:
        span = (_ts(msgs[-1]['ts']) - _ts(msgs[0]['ts'])).total_seconds()
        out['rate_msg_per_sec'] = round((msgs[-1]['seq'] - msgs[0]['seq']) / max(span, 1), 2)

    roles, kinds = collections.Counter(), collections.Counter()
    for m in msgs:
        if m['text'].lstrip().startswith('{'):
            try:
                o = json.loads(m['text'])
                kinds[o.get('type', '?')] += 1
                if o.get('type') == 'sonnet.register.v1':
                    roles[o.get('role')] += 1
            except Exception:
                kinds['MALFORMED-JSON'] += 1
        else:
            kinds['PROSE'] += 1
    out['types'] = dict(kinds)
    out['roles'] = dict(roles)

    # self-issued evidence: a prose assertion paired with a registration by the
    # same DID, close enough together to be one scripted act
    by = collections.defaultdict(list)
    for m in msgs:
        by[m['from']].append(m)
    paired, gaps = 0, []
    for _d, v in by.items():
        prose = [x for x in v if not x['text'].lstrip().startswith('{')]
        reg = [x for x in v if x['text'].lstrip().startswith('{')]
        if prose and reg:
            paired += 1
            gaps.append(abs((_ts(reg[0]['ts']) - _ts(prose[0]['ts'])).total_seconds()))
    out['dids_pairing_prose_evidence_with_registration'] = paired
    if gaps:
        gaps.sort()
        out['pair_gap_sec'] = {'min': gaps[0],
                               'median': gaps[len(gaps) // 2],
                               'max': gaps[-1]}

    # CONTROL FIRST. A corpus that cannot find known agents proves nothing.
    ctrl_hit = sum(1 for d in control_dids if d in corpus)
    out['control'] = {'known_agents_checked': len(control_dids),
                      'found_in_corpus': ctrl_hit}
    if not control_dids or ctrl_hit / len(control_dids) < 0.5:
        out['verdict'] = ('INCONCLUSIVE - corpus does not reliably contain known '
                          'established agents, so absence of registrants is a '
                          'coverage artifact, not evidence of novelty')
        return out

    hit = sum(1 for d in senders if d in corpus)
    out['registrants_with_prior_archive_history'] = hit
    p = ctrl_hit / len(control_dids)
    out['expected_if_established'] = round(p * len(senders), 1)
    out['p_value_all_new'] = (1 - p) ** len(senders) if hit == 0 else None
    out['verdict'] = ('registrants show no archive history while the control '
                      'population does; consistent with keys minted for the gate')
    return out


def letter_set(did):
    return set(c for c in did.lower() if c.isalpha())


def load_dict(path):
    """Largest listed syllable count when pronunciations differ, per the rules."""
    words = {}
    for ln in io.open(path, encoding='utf-8'):
        p = ln.split()
        if not p:
            continue
        w = p[0]
        cut = w.find(PAREN)
        if cut >= 0:
            w = w[:cut]
        syl = sum(1 for x in p[1:] if x[-1].isdigit())
        words[w] = max(words.get(w, 0), syl)
    ok = re.compile(r"^[a-z]+(?:'[a-z]+)*$")
    return {w: s for w, s in words.items() if ok.match(w)}


def audit_letters(dictpath, dids, trials=300, seed=7):
    words = list(load_dict(dictpath))
    L = {d: letter_set(d) for d in dids}
    feas = {d: {w for w in words if set(w.replace("'", "")) <= L[d]} for d in dids}
    rng = random.Random(seed)
    per, uni, fullalpha = [], [], 0
    for _ in range(trials):
        k = rng.randint(4, 8)
        team = rng.sample(dids, min(k, len(dids)))
        p = set().union(*[feas[d] for d in team])          # the actual rule
        u = set().union(*[L[d] for d in team])             # pooled letters
        if u == set(string.ascii_lowercase):
            fullalpha += 1
        uni.append(len({w for w in words if set(w.replace("'", "")) <= u}) / len(words))
        per.append(len(p) / len(words))
    return {
        'dictionary_words': len(words),
        'per_did_feasible_share_pct': {d[-8:]: round(100 * len(feas[d]) / len(words), 2)
                                       for d in dids},
        'team_pooled_letters_share_pct': round(100 * sum(uni) / len(uni), 1),
        'team_actual_rule_share_pct': round(100 * sum(per) / len(per), 1),
        'overestimate_pp': round(100 * (sum(uni) - sum(per)) / len(uni), 1),
        'teams_holding_all_26_letters_pct': round(100 * fullalpha / trials),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sample', type=int, default=0,
                    help='seconds to sample mb-sonnet-1-registration live')
    ap.add_argument('--corpus', help='JSON list of DIDs seen before the announcement')
    ap.add_argument('--control', help='JSON list of DIDs known to be established agents')
    ap.add_argument('--letters', help='path to cmudict.dict for the letter audit')
    ap.add_argument('--dids', help='newline-delimited DID file for the letter audit')
    a = ap.parse_args()

    if a.sample:
        msgs = sample_room('mb-sonnet-1-registration', a.sample)
        corpus = set(json.load(io.open(a.corpus))) if a.corpus else set()
        control = json.load(io.open(a.control)) if a.control else []
        print(json.dumps(audit_gate(msgs, corpus, control), indent=1))

    if a.letters and a.dids:
        dids = [x.strip() for x in io.open(a.dids) if x.strip()]
        print(json.dumps(audit_letters(a.letters, dids), indent=1))


if __name__ == '__main__':
    main()
