#!/usr/bin/env python3
"""
Project SENTINEL - Unified Test Suite Runner
Executes all modular unit and integration tests across the SENTINEL codebase.
Can also be executed with: pytest tests/ -v
"""
import sys
import os
import time
import subprocess

# Ensure UTF-8 console output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

TEST_MODULES = [
    ("Database & PostGIS Infrastructure", "test_db.py"),
    ("Authentication & Session Security", "test_auth.py"),
    ("Camera Registry & GIS Mapping", "test_cameras.py"),
    ("Spatial Gap Analysis", "test_gap_analysis.py"),
    ("Video Ingest & Streaming Contract", "test_ingest.py"),
    ("AI Pipeline & ANPR Normalization", "test_ai.py"),
    ("Watchlist Latency & Real-Time Alerts", "test_watchlist.py"),
    ("Vehicle Tracking & Predictive Interception", "test_tracking.py"),
    ("Camera Health & NOC Diagnostics", "test_health.py"),
    ("Forensics & Section 65B Certification", "test_forensics.py"),
]

def run_suite():
    print("==================================================================")
    print("PROJECT SENTINEL - COMPLETE MODULAR TEST SUITE RUNNER")
    print("==================================================================\n")

    passed_count = 0
    failed_count = 0
    total_start = time.perf_counter()

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"

    for idx, (title, filename) in enumerate(TEST_MODULES, 1):
        file_path = os.path.join(ROOT_DIR, "tests", filename)
        print(f"[{idx}/{len(TEST_MODULES)}] Testing {title} ({filename})...")
        mod_start = time.perf_counter()
        
        result = subprocess.run(
            [sys.executable, file_path],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            env=env
        )
        mod_duration = time.perf_counter() - mod_start

        if result.returncode == 0:
            passed_count += 1
            print(f"    [PASSED] ({mod_duration:.2f}s)")
        else:
            failed_count += 1
            print(f"    [FAILED] ({mod_duration:.2f}s)")
            print("\n--- Output ---")
            print(result.stdout)
            print(result.stderr)
            print("--------------\n")

    total_duration = time.perf_counter() - total_start
    print("\n==================================================================")
    print(f"SUMMARY: {passed_count} Passed | {failed_count} Failed | Total Time: {total_duration:.2f}s")
    print("==================================================================")

    if failed_count == 0:
        print("ALL TEST MODULES PASSED SUCCESSFULLY! (EXIT 0)\n")
        sys.exit(0)
    else:
        print(f"{failed_count} TEST MODULE(S) FAILED. (EXIT 1)\n")
        sys.exit(1)

if __name__ == "__main__":
    run_suite()
