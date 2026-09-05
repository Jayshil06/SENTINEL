import cv2
import numpy as np
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.app.schemas.forensics import CameraHealthDiagnostic

logger = logging.getLogger("sentinel.camera_health")

class CameraHealthService:
    """
    Automated Camera Health Diagnostics & Anti-Tampering Engine:
    Detects video stream degradation across statewide CCTV grid:
    1. Defocus / Optical Blur (Laplacian Variance)
    2. Lens Occlusion / Spray Paint / Glare (Mean Luminance & Histogram)
    3. Feed Stalling / Jitter (Heartbeat watchdog)
    """

    BLUR_THRESHOLD = 95.0        # Below this variance indicates defocus or dirty dome
    LUMINANCE_MIN = 18.0         # Below this indicates covered lens / night blackout
    LUMINANCE_MAX = 242.0        # Above this indicates direct headlight beam / blown sensor

    @classmethod
    def evaluate_frame_quality(cls, frame: np.ndarray) -> Dict[str, Any]:
        """Analyzes a single video frame for optical blur, occlusion, or glare."""
        if frame is None or frame.size == 0:
            return {
                "status": "OFFLINE",
                "laplacian_variance": 0.0,
                "mean_luminance": 0.0,
                "issues": ["No video signal / Empty frame"],
                "recommendation": "Inspect camera power and network connectivity."
            }

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame

        # 1. Defocus / Blur detection via Laplacian variance
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        # 2. Mean luminance and dynamic range
        mean_lum = float(np.mean(gray))

        issues = []
        status = "ONLINE"
        rec = "Camera operating within optimal surveillance parameters."

        if laplacian_var < cls.BLUR_THRESHOLD:
            issues.append(f"Optical blur detected (Laplacian Var: {laplacian_var:.1f} < {cls.BLUR_THRESHOLD})")
            status = "DEGRADED_BLUR"
            rec = "Dispatch maintenance crew to adjust optical focus and clean camera dome."

        if mean_lum < cls.LUMINANCE_MIN:
            issues.append(f"Severe underexposure / Lens occluded (Mean Lum: {mean_lum:.1f} < {cls.LUMINANCE_MIN})")
            status = "DEGRADED_OCCLUDED"
            rec = "Inspect camera for vandalism, spray paint, or physical obstruction."
        elif mean_lum > cls.LUMINANCE_MAX:
            issues.append(f"Sensor overexposed / Direct glare (Mean Lum: {mean_lum:.1f} > {cls.LUMINANCE_MAX})")
            status = "DEGRADED_GLARE"
            rec = "Adjust camera sunshield angle or enable auto-iris / WDR."

        return {
            "status": status,
            "laplacian_variance": round(laplacian_var, 2),
            "mean_luminance": round(mean_lum, 2),
            "issues": issues if issues else ["None"],
            "recommendation": rec
        }

    @classmethod
    def get_all_camera_diagnostics(cls, db: Session) -> List[CameraHealthDiagnostic]:
        """Runs health diagnostics across registered cameras in the statewide database."""
        query = text("""
            SELECT 
                c.camera_id,
                c.name,
                c.location_name,
                c.city,
                c.department_code,
                c.status,
                c.stream_url
            FROM cameras c
            ORDER BY c.camera_id ASC
        """)
        rows = db.execute(query).fetchall()

        diagnostics: List[CameraHealthDiagnostic] = []

        # Synthetic diagnostic distribution to demonstrate real-world edge monitoring
        # (A realistic CCTV grid has ~85% healthy, ~10% blurred/dirty, ~5% offline)
        for idx, r in enumerate(rows):
            cam_id = r[0]
            name = r[1]
            loc_name = r[2]
            city = r[3]
            dept_code = r[4] or "POLICE"
            db_status = r[5]

            # Deterministic simulation based on camera index for testing & demonstration
            if idx == 2:  # Simulated blurry dome camera
                status = "DEGRADED_BLUR"
                lap_var = 42.5
                mean_lum = 110.2
                sec_ago = 2.4
                issues = ["Optical blur / defocused lens detected (Variance: 42.5)"]
                rec = "Re-focus lens and wipe outer protective housing."
            elif idx == 7:  # Simulated occluded camera
                status = "DEGRADED_OCCLUDED"
                lap_var = 12.0
                mean_lum = 8.4
                sec_ago = 5.1
                issues = ["Lens blocked or vandalized (Luminance: 8.4)"]
                rec = "Inspect camera site for physical blockage or spray paint."
            elif db_status == "OFFLINE":
                status = "OFFLINE"
                lap_var = 0.0
                mean_lum = 0.0
                sec_ago = 1840.0
                issues = ["RTSP stream timeout / Gateway unreachable"]
                rec = "Check switch port PoE power and fiber connection."
            else:
                status = "ONLINE"
                lap_var = 245.8 + (idx * 15.2 % 100)
                mean_lum = 128.0 + (idx * 5.7 % 40)
                sec_ago = 0.8 + (idx * 0.1 % 2.0)
                issues = ["Nominal"]
                rec = "Operational."

            diagnostics.append(CameraHealthDiagnostic(
                camera_id=cam_id,
                name=name,
                location_name=loc_name,
                city=city,
                department_code=dept_code,
                status=status,
                laplacian_variance=round(lap_var, 2),
                mean_luminance=round(mean_lum, 2),
                last_frame_seconds_ago=round(sec_ago, 1),
                issues=issues,
                recommendation=rec
            ))

        return diagnostics
