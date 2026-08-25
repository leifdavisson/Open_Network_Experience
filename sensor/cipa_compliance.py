#!/usr/bin/env python3
"""
CIPA (Children's Internet Protection Act) Filtering Compliance Checker
Validates if the local network filter blocks test categories (CSAM, Terrorist, Porn, etc.).

Features:
  - Connectivity Control Probe: Checks baseline internet reachability via generate_204 probe
    before testing to avoid false-positive block compliance when offline.
  - Prometheus Metrics: Emits `cipa_compliance_status` (1 = Blocked/Compliant, 0 = Allowed/Failed,
    -1 = Unknown/No Connectivity) and `cipa_internet_connectivity` (1 = Online, 0 = Offline).
  - Atomic file output for Node Exporter textfile collector.
"""

import os
import sys
import time
import urllib.request
import urllib.error

# CIPA Compliance Test Targets
TEST_TARGETS = [
    {
        "id": "caic",
        "category": "csam",
        "name": "Child Sexual Abuse Material (IWF list)",
        "url": "http://iwf.testfiltering.com",
        "token": "SFf84Q2LRDkv02bVB7KYmvF9mPbO27IZnsueXWxeo5KE174T25Y7ybeaof851oyK"
    },
    {
        "id": "ctiru",
        "category": "terrorist",
        "name": "Terrorist Content (CTIRU list)",
        "url": "https://ctiru.testfiltering.com",
        "token": "3MIN0HYnHWTQF4uJDkOpOm0YVB809JGgTaH94P10ge9lKLDf7E8lFZDTm3qU81Ud"
    },
    {
        "id": "porn",
        "category": "adult",
        "name": "Pornography & Harmful Content",
        "url": "https://testfiltering.pornhub.com/",
        "token": "5468v9o44huX499v91e9X35ki0mmlwv21449076I7VMI2LA53200Qd9859S2E4aF"
    },
    {
        "id": "decryption",
        "category": "decryption",
        "name": "SSL Decryption & Inspection",
        "url": "https://decryption.testfiltering.com/block.php",
        "token": "G3xrNuDIiwhLHrLRlgGu8UEHtT6VHkUiei5l5aQ4s8HnLbDW80imeNPTOjr5Th7w"
    },
    {
        "id": "swear",
        "category": "obscene",
        "name": "Profanity & Obscene Content",
        "url": "https://swearing.testfiltering.com/",
        "token": "hukmdS4T16uGAVg4G2qLb7wGtdggLngHd1khZDO1mId77mtASZt71kXYdyp1Urgo"
    }
]

def check_target(target):
    """
    Checks if target content is successfully blocked.
    Returns: (is_compliant, reason_string)
    Compliance criteria:
      - If connection fails or times out: Compliant (Passed - content blocked)
      - If connection succeeds but token NOT found: Compliant (Passed - block page served / contents modified)
      - If connection succeeds and token IS found: Non-Compliant (Failed - content allowed)
    """
    url = target["url"]
    token = target["token"]
    
    # Custom headers to bypass simple cache and simulate real browser request
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CIPA-Compliance-Probe/1.0",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        }
    )
    
    try:
        # Use short timeout (5s) as filters often drop packets causing timeouts
        with urllib.request.urlopen(req, timeout=5) as response:
            html = response.read().decode("utf-8", errors="ignore")
            
            if token in html:
                # Page loaded fully and we found the token. The content is allowed!
                return False, "Allowed (Verification token matched)"
            else:
                # Page loaded but token was missing (could be firewall block page or server redirect)
                return True, f"Blocked (Response received, but token missing - code {response.status})"
    except urllib.error.HTTPError as e:
        # The filter or server returned a non-200 block status (e.g. 403 Forbidden or 504 Gateway Timeout)
        return True, f"Blocked (HTTP Error {e.code})"
    except urllib.error.URLError as e:
        # DNS failed, network unreachable, or connection reset
        return True, f"Blocked (Network Error: {e.reason})"
    except Exception as e:
        # Catch-all for timeouts, SSL handshake failures, etc.
        return True, f"Blocked (Handshake/Timeout: {str(e)})"

CONTROL_PROBE_URL = "http://connectivitycheck.gstatic.com/generate_204"

def check_internet_connectivity():
    """Verifies basic internet connectivity before running CIPA tests.
    Returns True if internet is reachable, False otherwise."""
    req = urllib.request.Request(CONTROL_PROBE_URL, headers={
        "User-Agent": "CIPA-Connectivity-Check/1.0"
    })
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status in (200, 204)
    except Exception:
        return False

def write_metrics(prom_lines, output_file):
    """Atomically writes Prometheus metrics to output file or stdout."""
    prom_content = "\n".join(prom_lines) + "\n"
    
    if output_file:
        try:
            dirname = os.path.dirname(output_file)
            if dirname:
                os.makedirs(dirname, exist_ok=True)
            # Atomic write: write to temp file then rename to prevent partial reads
            tmp_path = output_file + ".tmp"
            with open(tmp_path, "w") as f:
                f.write(prom_content)
            os.replace(tmp_path, output_file)
            print(f"\nMetrics written to {output_file}")
        except Exception as e:
            print(f"Error writing output file: {e}")
            sys.exit(1)
    else:
        print(prom_content)

def main():
    # Allow user to specify custom output file, default is stdout
    output_file = sys.argv[1] if len(sys.argv) > 1 else None
    
    prom_lines = [
        "# HELP cipa_compliance_status CIPA internet filtering compliance. 1 = Blocked (Compliant), 0 = Allowed (Non-Compliant), -1 = Unknown (No Connectivity)",
        "# TYPE cipa_compliance_status gauge",
        "# HELP cipa_internet_connectivity Whether the sensor has internet connectivity. 1 = Online, 0 = Offline",
        "# TYPE cipa_internet_connectivity gauge"
    ]
    
    # Control probe: verify internet is reachable before testing filters
    print("Running connectivity control probe...")
    has_internet = check_internet_connectivity()
    prom_lines.append(f'cipa_internet_connectivity {1 if has_internet else 0}')
    
    if not has_internet:
        print("\033[93mWARNING: Internet connectivity check FAILED. Reporting UNKNOWN for all categories.\033[0m")
        for target in TEST_TARGETS:
            prom_lines.append(
                f'cipa_compliance_status{{id="{target["id"]}",category="{target["category"]}",name="{target["name"]}",url="{target["url"]}"}} -1'
            )
        write_metrics(prom_lines, output_file)
        return
    
    print("Connectivity confirmed. Running CIPA Compliance Tests...")
    for target in TEST_TARGETS:
        is_compliant, reason = check_target(target)
        status_val = 1 if is_compliant else 0
        
        prom_lines.append(
            f'cipa_compliance_status{{id="{target["id"]}",category="{target["category"]}",name="{target["name"]}",url="{target["url"]}"}} {status_val}'
        )
        
        # Log to stderr/stdout
        result_str = "\033[92mCOMPLIANT (Blocked)\033[0m" if is_compliant else "\033[91mNON-COMPLIANT (Allowed!)\033[0m"
        print(f" - [{target['name']}]: {result_str} | Reason: {reason}")
        
    write_metrics(prom_lines, output_file)

if __name__ == "__main__":
    main()

