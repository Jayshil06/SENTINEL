"""
Project SENTINEL - Pytest Configuration and Global Fixtures
"""
import os
import sys
import pytest
import cv2
import numpy as np

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure project root is in sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from fastapi.testclient import TestClient
from backend.main import app
from backend.app.db.session import SessionLocal

@pytest.fixture(scope="session")
def client():
    """Provides a FastAPI TestClient instance for API tests."""
    with TestClient(app) as test_client:
        yield test_client

@pytest.fixture(scope="function")
def db_session():
    """Provides an isolated database session per test function."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(scope="session")
def synthetic_video_path(tmp_path_factory):
    """Generates a synthetic MP4 video with a moving vehicle and monotonic PTS."""
    temp_dir = tmp_path_factory.mktemp("video_feed")
    video_file = os.path.join(str(temp_dir), "test_synthetic.mp4")
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    w, h = 640, 480
    fps = 25
    duration_sec = 2
    out = cv2.VideoWriter(video_file, fourcc, fps, (w, h))
    total_frames = duration_sec * fps

    for i in range(total_frames):
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:] = (50, 50, 50)
        
        # Road lane markings
        for y in range(0, h, 60):
            cv2.line(frame, (w // 2, y), (w // 2, y + 30), (255, 255, 255), 4)

        # Moving vehicle
        car_y = int((i / total_frames) * (h - 100))
        car_x = w // 2 - 50
        cv2.rectangle(frame, (car_x, car_y), (car_x + 100, car_y + 140), (200, 50, 50), -1)
        
        # License plate
        cv2.rectangle(frame, (car_x + 10, car_y + 110), (car_x + 90, car_y + 135), (255, 255, 255), -1)
        cv2.putText(frame, "GJ01AB1234", (car_x + 12, car_y + 128), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 0), 1)
        
        # Burned PTS
        pts_text = f"PTS: {int(i * (1000.0 / fps))} ms | Frame: {i}"
        cv2.putText(frame, pts_text, (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        out.write(frame)

    out.release()
    return video_file
