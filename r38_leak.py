# -*- coding: utf-8 -*-
"""New pattern candidate: the generator's own meta-commentary shipped AS the delivery.

ka3f26e07ac delivers 95 characters that stop mid-word and continue in Chinese with the
model talking to itself about its own input ("the inscription seems to have been entered
incorrectly, I will continue based on standard English").  Worth cataloguing only if it
is a class, not one bad draw, so this counts how many deliveries in the fixed snapshot
ship first-person process talk or a mid-body script switch instead of an answer.
"""
import json, re, sys, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RXD = re.compile(r"^(?:RESULT|DELIVER) v1 \| (\S+) \| (.*)$", re.S)
CJK = re.compile(r"[぀-ヿ一-鿿]")
META = re.compile(r"(I will continue|I'll continue|as an AI|I cannot|I apologize|"
                  r"let me |Sure,? here|I'm sorry|my previous|the user (?:wants|asked)|"
                  r"我将|似乎|抱歉|请注意)", re.I)
msgs = json.load(open("r38_export.json", encoding="utf-8"))
d = [(m["from"], RXD.match((m.get("text") or "").strip())) for m in msgs]
d = [(w, x.group(1), x.group(2)) for w, x in d if x]
print(f"deliveries in snapshot: {len(d)}")
cjk = [(w, j, b) for w, j, b in d if CJK.search(b)]
meta = [(w, j, b) for w, j, b in d if META.search(b)]
both = [(w, j, b) for w, j, b in d if CJK.search(b) and META.search(b)]
print(f"  containing CJK script: {len(cjk)} ({100.0*len(cjk)/len(d):.2f}%) "
      f"from {len(set(w for w,_,_ in cjk))} workers")
print(f"  containing first-person process talk: {len(meta)} ({100.0*len(meta)/len(d):.2f}%) "
      f"from {len(set(w for w,_,_ in meta))} workers")
print(f"  both (script switch AND self-narration): {len(both)}")
for w, j, b in (cjk + meta)[:12]:
    print(f"   {j} ...{w[-10:]} len {len(b):4d} | {b[:190]}")
