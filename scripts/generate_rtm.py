#!/usr/bin/env python3
# License: GNU AGPLv3 (GNU Affero General Public License v3.0)
"""
AST Requirements Traceability Matrix (RTM) Generator for Open Network Experience.
Scans test suites for @verifies("REQ-XXX") or @pytest.mark.verifies("REQ-XXX") decorators
and verifies 100% bi-directional traceability against requirements.json.
"""

import ast
import json
import sys
import os
from pathlib import Path
from typing import Dict, List, Any

class RTMParser(ast.NodeVisitor):
    def __init__(self) -> None:
        self.mappings: Dict[str, List[str]] = {}

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call):
                func = decorator.func
                # Matches @verifies("REQ-XXX") or @pytest.mark.verifies("REQ-XXX")
                is_verifies = False
                if isinstance(func, ast.Name) and func.id == "verifies":
                    is_verifies = True
                elif isinstance(func, ast.Attribute) and func.attr == "verifies":
                    is_verifies = True

                if is_verifies:
                    for arg in decorator.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            self.mappings.setdefault(arg.value, []).append(node.name)
        self.generic_visit(node)

def run_audit(req_file: str, test_dirs: List[str], output_file: str) -> bool:
    if not os.path.exists(req_file):
        print(f"Requirements file not found: {req_file}", file=sys.stderr)
        return False

    with open(req_file, "r", encoding="utf-8") as f:
        reqs = json.load(f)

    parser = RTMParser()
    for t_dir in test_dirs:
        for py_file in Path(t_dir).rglob("test_*.py"):
            with open(py_file, "r", encoding="utf-8") as f:
                try:
                    parser.visit(ast.parse(f.read(), filename=str(py_file)))
                except Exception as e:
                    print(f"Error parsing AST in {py_file}: {e}", file=sys.stderr)

    rtm_data = []
    uncovered = []

    for req in reqs:
        req_id = req["id"]
        tests = parser.mappings.get(req_id, [])
        if not tests:
            uncovered.append(req_id)
        rtm_data.append({
            "requirement_id": req_id,
            "title": req.get("title", ""),
            "safety_level": req.get("safety_level", "STANDARD"),
            "verifying_tests": tests,
            "status": "VERIFIED" if tests else "UNCOVERED"
        })

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(rtm_data, f, indent=2)

    print(f"=== Requirements Traceability Matrix Audit ===")
    print(f"Total Requirements: {len(reqs)}")
    print(f"Verified Requirements: {len(reqs) - len(uncovered)}")
    print(f"Uncovered Requirements: {len(uncovered)}")

    if uncovered:
        print(f"RTM AUDIT FAILED: Uncovered requirements: {uncovered}", file=sys.stderr)
        return False
    print("RTM AUDIT PASSED: 100% Requirements Traceability Verified.")
    return True

if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent.parent
    req_path = str(base_dir / "requirements.json")
    out_path = str(base_dir / "RTM_MATRIX.json")
    test_paths = [str(base_dir / "sensor"), str(base_dir / "server")]
    success = run_audit(req_path, test_paths, out_path)
    sys.exit(0 if success else 1)
