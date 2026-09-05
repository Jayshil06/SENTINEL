import os
import time
import logging
from typing import Optional, Callable, Dict, Any

# Ensure OpenCV uses TCP for RTSP (Sentinel Guide Requirement §2 & §3)
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
import cv2
import numpy as np

logger = logging.getLogger("sentinel.rtsp_client")
logging.basicConfig(level=logging.INFO)

class ResilientRTSPClient:
    """
    RTSP Client strictly compliant with the Sentinel Integrator's Guide:
    - Enforces RTSP over TCP.
    - Uses monotonic Presentation Timestamps (PTS) via CAP_PROP_POS_MSEC.
    - Exponential backoff reconnect policy (2s to 30s).
    - Tolerates loop cuts and scene discontinuities.
    """
    def __init__(self, camera_id: str, stream_url: str, on_frame_callback: Optional[Callable] = None):
        self.camera_id = camera_id
        self.stream_url = stream_url
        self.on_frame_callback = on_frame_callback
        
        self.is_running = False
        self.cap: Optional[cv2.VideoCapture] = None
        self.reconnect_delay = 2.0
        self.max_reconnect_delay = 30.0
        
        self.total_frames_received = 0
        self.last_pts_ms = 0.0
        self.last_frame: Optional[np.ndarray] = None
        self.status = "disconnected"

    def connect(self) -> bool:
        logger.info(f"[{self.camera_id}] Connecting via RTSP/TCP to: {self.stream_url}")
        self.status = "connecting"
        
        # Open stream with FFMPEG backend and TCP transport
        self.cap = cv2.VideoCapture(self.stream_url, cv2.CAP_FFMPEG)
        
        if self.cap.isOpened():
            self.status = "connected"
            self.reconnect_delay = 2.0 # Reset backoff upon successful connection
            logger.info(f"[{self.camera_id}] Successfully connected to stream.")
            return True
        else:
            self.status = "failed"
            logger.warning(f"[{self.camera_id}] Failed to open stream: {self.stream_url}")
            return False

    def read_frame(self) -> Optional[Dict[str, Any]]:
        """
        Reads a single frame from the stream and extracts monotonic PTS.
        """
        if not self.cap or not self.cap.isOpened():
            return None

        ok, frame = self.cap.read()
        if not ok:
            return None

        # Monotonic presentation timestamp in milliseconds
        pts_ms = self.cap.get(cv2.CAP_PROP_POS_MSEC)
        
        # Handle cases where PTS is negative/unsupported by container
        if pts_ms is None or pts_ms < 0:
            pts_ms = time.time() * 1000.0

        # Check for loop reset (Sentinel video loop)
        if self.last_pts_ms > 0 and pts_ms < self.last_pts_ms:
            logger.info(f"[{self.camera_id}] Video loop reset detected (PTS {self.last_pts_ms:.0f} -> {pts_ms:.0f} ms).")

        self.last_pts_ms = pts_ms
        self.total_frames_received += 1
        self.last_frame = frame

        payload = {
            "camera_id": self.camera_id,
            "frame": frame,
            "pts_ms": pts_ms,
            "frame_number": self.total_frames_received,
            "width": frame.shape[1],
            "height": frame.shape[0]
        }

        if self.on_frame_callback:
            self.on_frame_callback(payload)

        return payload

    def run_loop(self, max_frames: Optional[int] = None):
        """
        Continuous ingestion loop with exponential backoff reconnect logic.
        """
        self.is_running = True
        logger.info(f"[{self.camera_id}] Starting ingestion loop...")

        while self.is_running:
            if not self.cap or not self.cap.isOpened():
                success = self.connect()
                if not success:
                    logger.warning(f"[{self.camera_id}] Reconnecting in {self.reconnect_delay:.1f}s...")
                    time.sleep(self.reconnect_delay)
                    self.reconnect_delay = min(self.reconnect_delay * 1.5, self.max_reconnect_delay)
                    continue

            frame_data = self.read_frame()
            if frame_data is None:
                logger.warning(f"[{self.camera_id}] Stream disconnected or frame read failed. Triggering reconnect...")
                if self.cap:
                    self.cap.release()
                self.cap = None
                time.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 1.5, self.max_reconnect_delay)
                continue

            if max_frames and self.total_frames_received >= max_frames:
                logger.info(f"[{self.camera_id}] Reached target frame count ({max_frames}). Stopping loop.")
                break

        self.stop()

    def stop(self):
        self.is_running = False
        if self.cap:
            self.cap.release()
            self.cap = None
        self.status = "stopped"
        logger.info(f"[{self.camera_id}] Ingestion stopped. Total frames: {self.total_frames_received}")
