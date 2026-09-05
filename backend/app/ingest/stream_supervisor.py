import threading
import time
import logging
from typing import Dict, Optional, Any, Callable
from backend.app.ingest.rtsp_client import ResilientRTSPClient

logger = logging.getLogger("sentinel.stream_supervisor")

class StreamSupervisor:
    """
    Manages concurrent RTSP camera stream workers across departments.
    Maintains thread safety, frame buffers, and camera health metrics.
    """
    def __init__(self):
        self.workers: Dict[str, ResilientRTSPClient] = {}
        self.threads: Dict[str, threading.Thread] = {}
        self.latest_frames: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()

    def start_camera(self, camera_id: str, stream_url: str, on_frame: Optional[Callable] = None):
        with self.lock:
            if camera_id in self.workers and self.workers[camera_id].is_running:
                logger.info(f"Camera {camera_id} is already running.")
                return

            def frame_wrapper(data):
                with self.lock:
                    self.latest_frames[camera_id] = {
                        "frame": data["frame"],
                        "pts_ms": data["pts_ms"],
                        "timestamp": time.time(),
                        "frame_number": data["frame_number"],
                        "width": data["width"],
                        "height": data["height"]
                    }
                if on_frame:
                    on_frame(data)

            worker = ResilientRTSPClient(camera_id, stream_url, on_frame_callback=frame_wrapper)
            self.workers[camera_id] = worker

            t = threading.Thread(target=worker.run_loop, daemon=True, name=f"RTSP-{camera_id}")
            self.threads[camera_id] = t
            t.start()
            logger.info(f"Started ingestion thread for camera {camera_id}.")

    def stop_camera(self, camera_id: str):
        with self.lock:
            if camera_id in self.workers:
                self.workers[camera_id].stop()
                del self.workers[camera_id]
            if camera_id in self.threads:
                del self.threads[camera_id]
            if camera_id in self.latest_frames:
                del self.latest_frames[camera_id]
            logger.info(f"Stopped camera {camera_id}.")

    def get_latest_frame(self, camera_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            return self.latest_frames.get(camera_id)

    def get_stream_health(self) -> Dict[str, Any]:
        with self.lock:
            health = {}
            for cid, worker in self.workers.items():
                health[cid] = {
                    "status": worker.status,
                    "frames_received": worker.total_frames_received,
                    "last_pts_ms": worker.last_pts_ms,
                    "is_running": worker.is_running
                }
            return health

    def stop_all(self):
        with self.lock:
            for cid, worker in list(self.workers.items()):
                worker.stop()
            self.workers.clear()
            self.threads.clear()
            self.latest_frames.clear()
            logger.info("All camera ingestion threads stopped.")

supervisor = StreamSupervisor()
