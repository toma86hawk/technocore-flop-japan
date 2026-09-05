import json, urllib.request
req = urllib.request.Request("https://technocore.chat/r/kibble/export?limit=30000",
                             headers={"User-Agent": "flop-jp-agent/1.0"})
raw = urllib.request.urlopen(req, timeout=300).read().decode("utf-8", "replace")
m = [json.loads(l) for l in raw.splitlines() if l.strip().startswith("{")]
json.dump(m, open("r38_export.json", "w"))
print(len(m), m[0]["seq"], m[-1]["seq"], m[0]["ts"], m[-1]["ts"])
