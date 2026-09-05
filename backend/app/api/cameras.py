import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.services.camera_service import CameraService
from backend.app.services.gap_analysis_service import GapAnalysisService

router = APIRouter(prefix="/cameras", tags=["Cameras & GIS Registry"])

@router.get("")
def list_cameras(
    department: Optional[str] = Query(None, description="Department code: POLICE, RTO, PDS, MUNICIPAL, PRIVATE"),
    status: Optional[str] = Query(None, description="Status: online, offline, degraded"),
    city: Optional[str] = Query(None, description="Filter by city name"),
    db: Session = Depends(get_db)
):
    """Retrieve list of cameras with metadata for statewide inventory."""
    cameras = CameraService.get_all_cameras(db, department_code=department, status=status, city=city)
    return [
        {
            "camera_id": c.camera_id,
            "name": c.name,
            "department_code": c.department_code,
            "location_name": c.location_name,
            "city": c.city,
            "latitude": c.latitude,
            "longitude": c.longitude,
            "stream_url": c.stream_url,
            "hls_url": c.hls_url,
            "codec": c.codec,
            "resolution": c.resolution,
            "fov_angle": c.fov_angle,
            "heading": c.heading,
            "status": c.status,
            "storage_retention_days": c.storage_retention_days,
            "last_ping": c.last_ping.isoformat() if c.last_ping else None
        }
        for c in cameras
    ]

@router.get("/geojson")
def get_cameras_geojson(
    department: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Returns PostGIS-rendered GeoJSON FeatureCollection for MapLibre / Leaflet UI."""
    return CameraService.get_cameras_geojson(db, department_code=department, status=status)

@router.get("/health-diagnostics")
def get_camera_health_diagnostics(db: Session = Depends(get_db)):
    """
    Automated Computer Vision Camera Health Diagnostics:
    Returns blur metrics (Laplacian variance), occlusion/glare metrics,
    and anti-tampering recommendations across the CCTV network.
    """
    from backend.app.services.camera_health_service import CameraHealthService
    return CameraHealthService.get_all_camera_diagnostics(db)

@router.get("/gap-analysis")
def get_gap_analysis(
    city: Optional[str] = Query("Ahmedabad"),
    radius_meters: int = Query(150, ge=50, le=1000),
    db: Session = Depends(get_db)
):
    """Computes spatial coverage buffers and surveillance blind spots."""
    return GapAnalysisService.get_coverage_and_blindspots(db, city=city, buffer_radius_meters=radius_meters)

@router.get("/{camera_id}")
def get_camera_detail(camera_id: str, db: Session = Depends(get_db)):
    cam = CameraService.get_camera_by_id(db, camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    return {
        "camera_id": cam.camera_id,
        "name": cam.name,
        "department_code": cam.department_code,
        "location_name": cam.location_name,
        "city": cam.city,
        "latitude": cam.latitude,
        "longitude": cam.longitude,
        "stream_url": cam.stream_url,
        "hls_url": cam.hls_url,
        "codec": cam.codec,
        "resolution": cam.resolution,
        "fov_angle": cam.fov_angle,
        "heading": cam.heading,
        "status": cam.status,
        "storage_retention_days": cam.storage_retention_days
    }

@router.post("/seed-sample")
def seed_sample_cameras(db: Session = Depends(get_db)):
    """Seeds the initial 20+ sample cameras across Gujarat cities."""
    data_path = os.path.join(os.getcwd(), "data", "sample_gujarat_cameras.json")
    if not os.path.exists(data_path):
        raise HTTPException(status_code=404, detail="Sample cameras file not found")
    count = CameraService.bulk_import_from_json(db, data_path)
    return {"status": "success", "imported_cameras": count}
