"""
Test Suite: AI Pipeline & Plate Normalization
Tests MotionGate pre-filter, Indian license plate normalization (pos errors, BH series, HSRP), and ANPR engine.
"""
import sys
import os
import cv2
import numpy as np

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.ai.motion_detector import MotionGate
from backend.app.ai.plate_normalizer import IndianPlateNormalizer
from backend.app.ai.detector import ANPREngine

def test_motion_gate_idle_vs_motion():
    """Verify MotionGate ignores static scenes and triggers on moving vehicles."""
    gate = MotionGate(min_contour_area=300, threshold=25)
    
    # Baseline frame (empty canvas)
    f1 = np.zeros((480, 640, 3), dtype=np.uint8)
    gate.has_motion(f1)
    
    # Second identical frame (no motion)
    f2 = np.zeros((480, 640, 3), dtype=np.uint8)
    m2, area2 = gate.has_motion(f2)
    assert m2 is False, f"Static frame should not trigger motion (area={area2})"
    
    # Third frame with moving object
    f3 = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.rectangle(f3, (200, 200), (400, 350), (255, 255, 255), -1)
    m3, area3 = gate.has_motion(f3)
    assert m3 is True, "Moving vehicle rectangle must trigger motion"
    assert area3 >= 300

def test_plate_normalizer_standard_plates():
    """Verify standard Indian vehicle plates normalize correctly."""
    cases = [
        ("GJ-01-AB-1234", "GJ01AB1234", True, "STANDARD"),
        ("gj 05 cd 9999", "GJ05CD9999", True, "STANDARD"),
        ("GJ-18-Z-0007", "GJ18Z0007", True, "STANDARD"),
        ("22BH1234AA", "22BH1234AA", True, "BH_SERIES"),
        ("GJ-O1-AB-1234", "GJ01AB1234", True, "STANDARD"), # Letter O -> Digit 0
        ("GJ-01-AB-123B", "GJ01AB1238", True, "STANDARD"), # Letter B -> Digit 8
    ]
    for raw, expected_norm, expected_valid, expected_type in cases:
        res = IndianPlateNormalizer.normalize_plate(raw)
        assert res["normalized"] == expected_norm, f"Failed for {raw}: expected {expected_norm}, got {res['normalized']}"
        assert res["is_valid"] == expected_valid
        assert res.get("plate_type") == expected_type

def test_anpr_engine_detection_simulation():
    """Verify ANPREngine detection and evidentiary snapshot creation."""
    engine = ANPREngine(snapshot_dir="data/snapshots")
    det = engine.simulate_plate_detection(
        camera_id="CAM-GNR-SEC18-01",
        plate_text="GJ-01-AB-1234",
        vehicle_type="SUV",
        pts_ms=1725432000000.0
    )
    assert det["normalized_plate"] == "GJ01AB1234"
    assert det["confidence"] > 0.8
    assert os.path.exists(det["snapshot_path"])
    img = cv2.imread(det["snapshot_path"])
    assert img is not None and img.shape[0] > 0

if __name__ == "__main__":
    print("🚀 Running AI Pipeline & Plate Normalization Tests...")
    test_motion_gate_idle_vs_motion()
    print("✅ MotionGate pre-filter verified.")
    test_plate_normalizer_standard_plates()
    print("✅ Standard & heuristic plate normalization verified.")
    test_anpr_engine_detection_simulation()
    print("✅ ANPR engine detection & snapshot verified.")
    print("🎉 All AI Pipeline Tests Passed!")
