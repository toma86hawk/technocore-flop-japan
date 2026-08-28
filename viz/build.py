#!/usr/bin/env python3
"""Inline viz_data.json into the page template so the published file is self-contained."""
import json, os, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))

data = open(os.path.join(HERE, "viz_data.json"), encoding="utf-8").read()
tpl = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
marker = "/*__DATA__*/null"
if marker not in tpl:
    print("marker missing from template"); sys.exit(1)
out = tpl.replace(marker, data)
dest = os.path.join(HERE, "technocore-activity.html")
open(dest, "w", encoding="utf-8").write(out)
print("wrote", dest, len(out), "bytes")
