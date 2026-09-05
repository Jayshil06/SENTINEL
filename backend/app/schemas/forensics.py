from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class EvidenceItemSchema(BaseModel):
    detection_id: int
    camera_id: str
    camera_name: str
    location_name: str
    city: str
    latitude: float
    longitude: float
    detected_at: datetime
    pts_ms: Optional[int] = 0
    confidence: float
    snapshot_url: Optional[str] = None
    snapshot_sha256: str
    is_alert_hit: bool = False

class Section65BCertificateResponse(BaseModel):
    certificate_id: str
    target_plate: str
    generated_at: datetime
    jurisdiction: str = "State of Gujarat, India"
    statutory_governance: str = "Section 65B Indian Evidence Act, 1872 / Section 63 Bharatiya Sakshya Adhiniyam, 2023"
    issuing_authority: str = "Gujarat Police Directorate General of Police - Project SENTINEL Command"
    total_detections_certified: int
    first_sighted_at: Optional[datetime] = None
    last_sighted_at: Optional[datetime] = None
    overall_dossier_sha256: str
    evidence_chain: List[EvidenceItemSchema]
    statutory_declaration: str
    system_custodian_declaration: str
    verification_url: str

class CameraHealthDiagnostic(BaseModel):
    camera_id: str
    name: str
    location_name: str
    city: str
    department_code: str
    status: str  # ONLINE, DEGRADED_BLUR, DEGRADED_OCCLUDED, OFFLINE
    health_status: Optional[str] = None
    laplacian_variance: float
    mean_luminance: float
    last_frame_seconds_ago: float
    issues: List[str]
    recommendation: str
    anti_tamper_recommendation: Optional[str] = None
