#!/usr/bin/env python3
import glob
import json
import os
import re

RESULTS_DIR = "/data/Open_Network_Experience/uat-results"
files = sorted(glob.glob(os.path.join(RESULTS_DIR, "ONE-*-results.md")))

components_data = []

for fpath in files:
    with open(fpath, "r", encoding="utf-8") as f:
        text = f.read()
    
    # Component ID and Name
    m = re.search(r"# UAT Test Execution:\s*\[(\d+)\]\s*(.+)", text)
    comp_id = m.group(1) if m else "??"
    comp_name = m.group(2).strip() if m else os.path.basename(fpath)
    
    # Sub-components tested
    sub_matches = re.findall(r"SUB-COMPONENT:\s*(.+)", text)
    sub_components = list(dict.fromkeys(sub_matches))
    
    # Statuses
    passes = len(re.findall(r"STATUS:\s*✅\s*PASS", text))
    fails = len(re.findall(r"STATUS:\s*❌\s*FAIL", text))
    partials = len(re.findall(r"STATUS:\s*⚠️\s*PARTIAL", text))
    blockeds = len(re.findall(r"STATUS:\s*🚫\s*BLOCKED", text))
    
    # UX notes
    ux_notes = re.findall(r"UX (?:IMPROVEMENT|NOTE):\s*(.+)", text)
    
    components_data.append({
        "id": comp_id,
        "name": comp_name,
        "sub_count": len(sub_components),
        "pass": passes,
        "fail": fails,
        "partial": partials,
        "blocked": blockeds,
        "ux": ux_notes
    })

print(json.dumps(components_data, indent=2))
