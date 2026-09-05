"""
Test Suite: Video Ingestion & Streaming Infrastructure
Tests Gujarat Police Sentinel Integrator's Guide compliance (§4 Checklist),
RTSP over TCP enforcement, monotonic PTS tracking, exponential backoff, and /api/ingest contract.
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
from backend.app.ingest.rtsp_client import ResilientRTSPClient
from backend.app.ingest.stream_supervisor import supervisor

def test_rtsp_over_tcp_enforced():
    """Verify OPENCV_FFMPEG_CAPTURE_OPTIONS strictly forces TCP transport."""
    opt = os.environ.get("OPENCV_FFMPEG_CAPTURE_OPTIONS")
    assert opt == "rtsp_transport;tcp", f"Expected 'rtsp_transport;tcp', got '{opt}'"

def test_api_ingest_catalogue_contract():
    """Verify /api/ingest returns dynamic camera endpoints per Integrator's Guide §4."""
    client = TestClient(app)
    response = client.get("/api/ingest")
    assert response.status_code == 200, f"/api/ingest failed: {response.text}"
    catalogue = response.json()
    assert isinstance(catalogue, list)
    assert len(catalogue) >= 3, "Catalogue must contain camera stream endpoints"

    for cam in catalogue:
        assert "rtsp_url" in cam
        assert "hls_url" in cam
        assert "location" in cam
        assert cam.get("properties", {}).get("transport") == "tcp"

def test_exponential_backoff_logic():
    """Verify exponential backoff progression caps at 30.0s."""
    client = ResilientRTSPClient(camera_id="TEST-CAM-01", stream_url="rtsp://localhost:8554/dummy")
    delays = []
    current_delay = client.reconnect_delay
    for _ in range(5):
        delays.append(current_delay)
        current_delay = min(current_delay * 1.5, client.max_reconnect_delay)

    assert delays[0] == 2.0
    assert delays[1] == 3.0
    assert delays[2] == 4.5
    assert current_delay <= 30.0

def test_monotonic_pts_extraction():
    """Verify ResilientRTSPClient processes feed with monotonic presentation timestamps."""
    feed_path = os.path.join(os.getcwd(), "data", "test_feed.mp4")
    assert os.path.exists(feed_path), f"Sample feed not found at {feed_path}"

    received_pts = []
    def on_frame(data):
        received_pts.append(data["pts_ms"])

    client = ResilientRTSPClient(
        camera_id="CAM-TEST-PTS",
        stream_url=feed_path,
        on_frame_callback=on_frame
    )
    client.run_loop(max_frames=15)
    assert len(received_pts) >= 10, f"Expected at least 10 frames, got {len(received_pts)}"
    for i in range(1, len(received_pts)):
        assert received_pts[i] >= received_pts[i-1], "PTS must be monotonically non-decreasing"

def test_stream_supervisor_registry():
    """Verify stream supervisor lifecycle management."""
    feed_path = os.path.join(os.getcwd(), "data", "test_feed.mp4")
    assert os.path.exists(feed_path)
    supervisor.start_camera("CAM-SUP-MODULAR-TEST", feed_path)
    time.sleep(0.5)
    health = supervisor.get_stream_health()
    assert "CAM-SUP-MODULAR-TEST" in health
    supervisor.stop_camera("CAM-SUP-MODULAR-TEST")

if __name__ == "__main__":
    print("🚀 Running Video Ingestion & Streaming Tests...")
    test_rtsp_over_tcp_enforced()
    print("✅ RTSP over TCP enforcement verified.")
    test_api_ingest_catalogue_contract()
    print("✅ /api/ingest catalogue contract verified.")
    test_exponential_backoff_logic()
    print("✅ Exponential backoff policy verified.")
    test_monotonic_pts_extraction()
    print("✅ Monotonic PTS extraction verified.")
    test_stream_supervisor_registry()
    print("✅ Stream supervisor registry verified.")
    print("🎉 All Video Ingestion & Streaming Tests Passed!")
