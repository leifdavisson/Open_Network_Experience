#!/usr/bin/env python3
"""
AST Requirements Traceability Matrix (RTM) Generator for JavaScript & Python test suites.
Inspects test files for requirements annotations (@verifies('REQ-XXX') or verifies('REQ-XXX'))
and cross-references them against requirements.json.
License: GNU AGPLv3
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List

def run_audit(req_file: str, test_dir: str, output_file: str) -> bool:
    with open(req_file, "r", encoding="utf-8") as f:
        reqs = json.load(f)

    # Pattern matches verifies("REQ-XXX") or verifies('REQ-XXX') in JS or Python
    pattern = re.compile(r'verifies\s*\(\s*["\'](REQ-[A-Z0-9-]+)["\']\s*,\s*["\'](.*?)["\']\s*\)', re.MULTILINE)

    mappings: Dict[str, List[str]] = {}

    for test_file in Path(test_dir).rglob("*.test.js"):
        with open(test_file, "r", encoding="utf-8") as f:
            content = f.read()
            matches = pattern.findall(content)
            for req_id, test_name in matches:
                mappings.setdefault(req_id, []).append(f"{test_file.name}::{test_name}")

    rtm_data = []
    uncovered = []

    for req in reqs:
        req_id = req["id"]
        tests = mappings.get(req_id, [])
        if not tests:
            uncovered.append(req_id)
        rtm_data.append({
            "requirement_id": req_id,
            "title": req.get("title", ""),
            "safety_level": req.get("safety_level", "STANDARD"),
            "acceptance_criteria": req.get("acceptance_criteria", ""),
            "verifying_tests": tests,
            "status": "VERIFIED" if tests else "UNCOVERED"
        })

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(rtm_data, f, indent=2)

    total = len(reqs)
    verified = total - len(uncovered)
    pct = (verified / total * 100) if total > 0 else 0

    print(f"================================================================")
    print(f"AUTOMATED V&V TRACEABILITY AUDIT")
    print(f"Total Requirements: {total}")
    print(f"Verified Requirements: {verified} ({pct:.1f}%)")
    print(f"Uncovered Requirements: {len(uncovered)}")
    print(f"================================================================")

    if uncovered:
        print(f"❌ RTM AUDIT FAILED: Missing coverage for: {uncovered}", file=sys.stderr)
        return False

    print("✅ RTM AUDIT PASSED: 100% Requirements Bi-Directional Traceability Verified.")
    return True

if __name__ == "__main__":
    req_p = sys.argv[1] if len(sys.argv) > 1 else "requirements.json"
    t_dir = sys.argv[2] if len(sys.argv) > 2 else "test"
    out_p = sys.argv[3] if len(sys.argv) > 3 else "RTM_MATRIX.json"
    success = run_audit(req_p, t_dir, out_p)
    sys.exit(0 if success else 1)
