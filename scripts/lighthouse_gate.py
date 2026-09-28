#!/usr/bin/env python3
import json, sys
p=sys.argv[1]
data=json.load(open(p,encoding="utf-8"))
cats=data.get("categories",{})
minimum={"performance":0.75,"accessibility":0.90,"best-practices":0.90,"seo":0.90}
bad=[]
for key,threshold in minimum.items():
    score=(cats.get(key) or {}).get("score")
    print(f"{key}: {score}")
    if score is None or score < threshold: bad.append(f"{key}={score} < {threshold}")
if bad:
    print("LIGHTHOUSE GATE FAILED:", "; ".join(bad)); sys.exit(1)
print("LIGHTHOUSE GATE PASSED")
