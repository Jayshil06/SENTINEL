from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class InterceptionNode(BaseModel):
    camera_id: str
    camera_name: str
    location_name: str
    city: str
    latitude: float
    longitude: float
    distance_km: float
    bearing_diff_degrees: float
    estimated_speed_kmh: float
    eta_minutes: float
    tactical_priority: str  # IMMEDIATE, PRIMARY, SECONDARY

class PredictiveInterceptionResponse(BaseModel):
    target_plate: str
    last_known_camera_id: str
    last_known_location: str
    last_known_coords: List[float]  # [lon, lat]
    last_sighted_at: datetime
    current_bearing_degrees: float
    bearing_direction_text: str  # e.g., "NNE (24°)"
    estimated_speed_kmh: float
    predicted_nodes: List[InterceptionNode]
    prediction_ray_geojson: Optional[Dict[str, Any]] = None
    tactical_recommendation: str

class SearchResultItem(BaseModel):
    detection_id: int
    license_plate: str
    camera_id: str
    camera_name: str
    location_name: str
    city: str
    department_name: str
    detected_at: datetime
    confidence: float
    snapshot_url: Optional[str] = None
    is_alert_hit: bool

class ForensicSearchResponse(BaseModel):
    total_matches: int
    query_pattern: str
    results: List[SearchResultItem]
