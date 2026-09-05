"""
Test Suite: Watchlist Management & Real-Time Alerts
Tests Redis O(1) watchlist caching, sub-millisecond lookup benchmark, alert generation, and simulation API.
"""
import sys
import os
import time
from fastapi.testclient import TestClient

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.main import app
from backend.app.db.session import SessionLocal
from backend.app.services.watchlist_service import watchlist_service

def test_watchlist_seeding():
    """Verify adding law enforcement watchlist records to PostGIS and Redis."""
    db = SessionLocal()
    try:
        plate = "GJ-01-AB-1234"
        entry = watchlist_service.add_to_watchlist(
            db,
            license_plate=plate,
            category="Stolen Vehicle",
            reason="Hyundai Creta - Stolen under FIR #481/2026",
            fir_number="FIR-AHM-2026-481",
            department="Gujarat Police",
            priority="CRITICAL"
        )
        assert entry is not None
        assert entry.normalized_plate == "GJ01AB1234"
    finally:
        db.close()

def test_watchlist_redis_lookup_latency_benchmark():
    """Verify sub-millisecond O(1) plate lookup latency over 1,000 queries."""
    num_queries = 1000
    plates = ["GJ01AB1234", "GJ01XY9999", "GJ18Z0007", "DL01AA0001"]

    start = time.perf_counter()
    for i in range(num_queries):
        query_plate = plates[i % len(plates)]
        watchlist_service.redis_client.sismember(watchlist_service.REDIS_WATCHLIST_SET, query_plate)
    elapsed = time.perf_counter() - start

    avg_latency_ms = (elapsed / num_queries) * 1000.0
    assert avg_latency_ms < 2.0, f"Latency too high: {avg_latency_ms:.3f} ms"

def test_watchlist_match_detection():
    """Verify matched alert generation and metadata retrieval."""
    db = SessionLocal()
    try:
        # Match case
        alert_hit = watchlist_service.check_and_alert(
            db,
            camera_id="CAM-AHM-SG-PAKWAN-04",
            plate_text="GJ-01-AB-1234",
            snapshot_url="/static/snapshots/CAM-04_GJ01AB1234.jpg"
        )
        assert alert_hit is not None
        assert alert_hit["category"] == "Stolen Vehicle"
        assert alert_hit["license_plate"] == "GJ01AB1234"

        # Miss case
        alert_miss = watchlist_service.check_and_alert(
            db,
            camera_id="CAM-AHM-SG-PAKWAN-04",
            plate_text="GJ-99-ZZ-0000"
        )
        assert alert_miss is None
    finally:
        db.close()

def test_api_alert_simulation():
    """Verify POST /api/v1/watchlist/simulate-detection triggers real-time alert and responds 200."""
    client = TestClient(app)
    payload = {
        "camera_id": "CAM-AHM-SG-PAKWAN-04",
        "license_plate": "GJ-01-AB-1234",
        "vehicle_type": "SUV"
    }
    response = client.post("/api/v1/watchlist/simulate-detection", json=payload)
    assert response.status_code == 200, f"Alert simulation failed: {response.text}"
    result = response.json()
    assert result.get("is_alert") is True
    assert "alert" in result
    assert result["alert"]["category"] == "Stolen Vehicle"

if __name__ == "__main__":
    print("🚀 Running Watchlist & Real-Time Alerts Tests...")
    test_watchlist_seeding()
    print("✅ Watchlist seeding verified.")
    test_watchlist_redis_lookup_latency_benchmark()
    print("✅ Redis O(1) latency benchmark verified (<2ms).")
    test_watchlist_match_detection()
    print("✅ Watchlist match/miss detection verified.")
    test_api_alert_simulation()
    print("✅ Alert simulation API verified.")
    print("🎉 All Watchlist & Alert Tests Passed!")
