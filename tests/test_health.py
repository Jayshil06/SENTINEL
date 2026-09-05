"""
Test Suite: Camera Health & NOC Diagnostics
Tests automated camera health diagnostics, optical blur detection (Laplacian variance),
mean luminance (occlusion/glare), and the NOC health monitor portal.
"""
import sys
import os
import cv2
import numpy as np
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
from backend.app.services.camera_health_service import CameraHealthService

def test_camera_health_optical_blur_detection():
    """Verify Laplacian variance flags optical blur on smooth or defocused images."""
    # Synthetic blurry frame
    blurry_frame = np.full((480, 640, 3), 128, dtype=np.uint8)
    res_blur = CameraHealthService.evaluate_frame_quality(blurry_frame)
    assert res_blur["status"] == "DEGRADED_BLUR", f"Blur frame not detected: {res_blur}"
    assert res_blur["laplacian_variance"] < CameraHealthService.BLUR_THRESHOLD

def test_camera_health_occlusion_detection():
    """Verify low luminance triggers occlusion warning."""
    dark_frame = np.full((480, 640, 3), 5, dtype=np.uint8)
    res_dark = CameraHealthService.evaluate_frame_quality(dark_frame)
    assert res_dark["status"] == "DEGRADED_OCCLUDED", f"Occluded frame not detected: {res_dark}"
    assert res_dark["mean_luminance"] < CameraHealthService.LUMINANCE_MIN

def test_camera_health_glare_detection():
    """Verify extreme luminance triggers glare warning."""
    glare_frame = np.full((480, 640, 3), 250, dtype=np.uint8)
    glare_result = CameraHealthService.evaluate_frame_quality(glare_frame)
    assert glare_result["status"] == "DEGRADED_GLARE"
    assert glare_result["mean_luminance"] > CameraHealthService.LUMINANCE_MAX

def test_camera_health_get_all_diagnostics():
    """Verify database-backed diagnostics scan returns health list."""
    db = SessionLocal()
    try:
        diagnostics = CameraHealthService.get_all_camera_diagnostics(db)
        assert len(diagnostics) >= 20, f"Expected >= 20 cameras diagnosed, got {len(diagnostics)}"
        statuses = {d.status for d in diagnostics}
        assert "ONLINE" in statuses
    finally:
        db.close()

def test_health_monitor_portal():
    """Verify /health-monitor HTML NOC portal is served."""
    client = TestClient(app)
    response = client.get("/health-monitor")
    assert response.status_code == 200
    assert "SENTINEL" in response.text

if __name__ == "__main__":
    print("🚀 Running Camera Health & NOC Diagnostics Tests...")
    test_camera_health_optical_blur_detection()
    print("✅ Optical blur detection verified.")
    test_camera_health_occlusion_detection()
    print("✅ Occlusion detection verified.")
    test_camera_health_glare_detection()
    print("✅ Glare detection verified.")
    test_camera_health_get_all_diagnostics()
    print("✅ Statewide camera health diagnostics verified.")
    test_health_monitor_portal()
    print("✅ Health NOC portal page verified.")
    print("🎉 All Camera Health Tests Passed!")
