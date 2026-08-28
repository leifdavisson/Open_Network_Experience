#!/usr/bin/env python3
"""
Playwright Browser Transaction Tester (Phase 2 Enhanced)
Performs synthetic transactions on web pages and APIs.
Measures rendering/response timings and identifies if blocked third-party
domains (like ads or trackers) are causing page slowness or timeouts.
Captures failure screenshots and HAR network waterfalls on errors.
Outputs results in Prometheus format for scraping.
"""

import os
import sys
import json
import time
from urllib.parse import urlparse

SNAPSHOTS_DIR = "/var/lib/sensor/snapshots"

# Ensure playwright is imported; print error and exit if missing
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright is not installed. Run 'pip install playwright' and 'playwright install' first.")
    sys.exit(1)

def ensure_snapshot_dir():
    os.makedirs(SNAPSHOTS_DIR, exist_ok=True)

def run_api_test(url, method="GET", headers=None, data=None):
    """Measures API endpoint performance."""
    start_time = time.time()
    success = 0
    status_code = 0

    with sync_playwright() as p:
        request_context = p.request.new_context()
        try:
            if method.upper() == "POST":
                response = request_context.post(url, headers=headers, data=data, timeout=5000)
            else:
                response = request_context.get(url, headers=headers, timeout=5000)

            status_code = response.status
            if response.ok:
                success = 1
        except Exception as e:
            print(f"API Request Failed: {e}", file=sys.stderr)
            status_code = -1

    duration = time.time() - start_time
    return {
        "success": success,
        "duration_seconds": duration,
        "status_code": status_code,
        "failed_requests": {}
    }

def run_page_test(url, timeout_ms=30000):
    """
    Measures full browser page load, logs failed/blocked assets,
    and captures HAR waterfall + failure screenshots on error.
    """
    ensure_snapshot_dir()
    start_time = time.time()
    success = 0
    dcl_time = 0.0  # DOMContentLoaded
    load_time = 0.0
    failed_requests = {}  # Maps domain -> count
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    har_temp_path = f"/tmp/browser_run_{timestamp}.har"

    with sync_playwright() as p:
        # Launch headless browser (Chromium) with HAR recording
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Open-UX-Browser-Transaction/1.0",
            record_har_path=har_temp_path
        )
        page = context.new_page()

        # Intercept failed requests to identify blocked ads, trackers, or CDNs
        def handle_request_failed(request):
            req_url = request.url
            failure = request.failure or "Unknown Error"
            domain = urlparse(req_url).netloc
            failed_requests[domain] = failed_requests.get(domain, 0) + 1
            print(f"Asset Failed to Load: {req_url} | Reason: {failure}", file=sys.stderr)

        page.on("requestfailed", handle_request_failed)

        try:
            # Navigate to target page
            response = page.goto(url, timeout=timeout_ms, wait_until="load")

            # Extract performance timing from window.performance API
            performance_timing = page.evaluate("() => JSON.stringify(window.performance.timing)")
            timing = json.loads(performance_timing)

            nav_start = timing.get("navigationStart", 0)
            dcl_end = timing.get("domContentLoadedEventEnd", 0)
            load_end = timing.get("loadEventEnd", 0)

            if nav_start > 0:
                if dcl_end > 0:
                    dcl_time = (dcl_end - nav_start) / 1000.0
                if load_end > 0:
                    load_time = (load_end - nav_start) / 1000.0

            # Fallback to python-side timer if performance.timing is incomplete
            if load_time == 0:
                load_time = time.time() - start_time

            if response and response.status < 400:
                success = 1

        except Exception as e:
            print(f"Page navigation failed for {url}: {e}", file=sys.stderr)
            # Capture failure screenshot and preserve HAR file in snapshots directory
            screenshot_path = os.path.join(SNAPSHOTS_DIR, f"browser_failure_{timestamp}.png")
            try:
                page.screenshot(path=screenshot_path)
                print(f"Saved failure screenshot to {screenshot_path}", file=sys.stderr)
            except Exception:
                pass
        finally:
            context.close()
            browser.close()

    total_duration = time.time() - start_time

    # If test failed, promote HAR file to snapshots; otherwise delete temp HAR to conserve disk
    if not success and os.path.exists(har_temp_path):
        target_har = os.path.join(SNAPSHOTS_DIR, f"browser_failure_{timestamp}.har")
        try:
            os.replace(har_temp_path, target_har)
            print(f"Preserved failure HAR waterfall: {target_har}")
        except Exception:
            pass
    elif os.path.exists(har_temp_path):
        try:
            os.remove(har_temp_path)
        except Exception:
            pass

    return {
        "success": success,
        "duration_seconds": total_duration,
        "dcl_seconds": dcl_time if dcl_time > 0 else total_duration,
        "load_seconds": load_time if load_time > 0 else total_duration,
        "status_code": 200 if success else 500,
        "failed_requests": failed_requests
    }

def main():
    if len(sys.argv) < 3:
        print("Usage: ./browser_transaction.py <url> <page|api> [output_file.prom]")
        sys.exit(1)

    target_url = sys.argv[1]
    test_type = sys.argv[2].lower()
    output_file = sys.argv[3] if len(sys.argv) > 3 else None

    if test_type == "api":
        results = run_api_test(target_url)
    elif test_type == "page":
        results = run_page_test(target_url)
    else:
        print(f"Unknown test type: {test_type}. Use 'page' or 'api'.")
        sys.exit(1)

    # Generate Prometheus metrics
    prom_lines = [
        f'# HELP browser_transaction_success Status of transaction to {target_url}. 1 = Success, 0 = Fail',
        f'# TYPE browser_transaction_success gauge',
        f'browser_transaction_success{{url="{target_url}",type="{test_type}"}} {results["success"]}',

        f'# HELP browser_transaction_duration_seconds Total transaction time in seconds',
        f'# TYPE browser_transaction_duration_seconds gauge',
        f'browser_transaction_duration_seconds{{url="{target_url}",type="{test_type}"}} {results["duration_seconds"]:.4f}',

        f'# HELP browser_transaction_status_code HTTP status code or -1 on network failure',
        f'# TYPE browser_transaction_status_code gauge',
        f'browser_transaction_status_code{{url="{target_url}",type="{test_type}"}} {results["status_code"]}'
    ]

    if test_type == "page":
        prom_lines.extend([
            f'# HELP browser_page_dom_content_loaded_seconds DOMContentLoaded timing in seconds',
            f'# TYPE browser_page_dom_content_loaded_seconds gauge',
            f'browser_page_dom_content_loaded_seconds{{url="{target_url}"}} {results["dcl_seconds"]:.4f}',

            f'# HELP browser_page_load_seconds Full window load event timing in seconds',
            f'# TYPE browser_page_load_seconds gauge',
            f'browser_page_load_seconds{{url="{target_url}"}} {results["load_seconds"]:.4f}'
        ])

        # Add failed requests by domain
        if results["failed_requests"]:
            prom_lines.append('# HELP browser_blocked_asset_requests_total Blocked or failed resource requests by third-party domain')
            prom_lines.append('# TYPE browser_blocked_asset_requests_total gauge')
            for domain, count in results["failed_requests"].items():
                prom_lines.append(f'browser_blocked_asset_requests_total{{target_url="{target_url}",domain="{domain}"}} {count}')

    content = "\n".join(prom_lines) + "\n"

    if output_file:
        tmp_file = output_file + ".tmp"
        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
        with open(tmp_file, "w") as f:
            f.write(content)
        os.replace(tmp_file, output_file)
        print(f"Metrics atomically written to {output_file}")
    else:
        print(content)

if __name__ == "__main__":
    main()
