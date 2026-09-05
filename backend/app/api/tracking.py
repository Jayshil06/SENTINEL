from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.services.route_tracer import route_tracer
from backend.app.db.models import VehicleDetection, Camera

router = APIRouter(prefix="/tracking", tags=["Vehicle Tracking & Route Reconstruction"])

@router.get("/route")
def reconstruct_vehicle_route(
    plate: str = Query(..., description="Target vehicle registration number, e.g. GJ01AB1234"),
    start_time: Optional[datetime] = Query(None, description="Start time ISO string"),
    end_time: Optional[datetime] = Query(None, description="End time ISO string"),
    db: Session = Depends(get_db)
):
    """
    Hackathon Test Case:
    Reconstructs the full geographical route traversed by a designated vehicle,
    including timestamped movement history, camera snapshots, and GeoJSON LineString.
    """
    return route_tracer.reconstruct_route(
        db,
        license_plate=plate,
        start_time=start_time,
        end_time=end_time
    )

@router.post("/seed-evaluation-scenario")
def seed_evaluation_scenario(
    plate: str = Query("GJ01AB1234"),
    db: Session = Depends(get_db)
):
    """
    Pre-populates the 4-junction SG Highway pursuit scenario
    demonstrating the complete route reconstruction for judges.
    """
    count = route_tracer.seed_evaluation_trajectory(db, target_plate=plate)
    return {"status": "success", "seeded_detections": count, "target_plate": plate}

@router.get("/recent-detections")
def get_recent_detections(limit: int = Query(30), db: Session = Depends(get_db)):
    detections = db.query(VehicleDetection).order_by(VehicleDetection.detected_at.desc()).limit(limit).all()
    results = []
    for d in detections:
        cam = db.query(Camera).filter(Camera.camera_id == d.camera_id).first()
        results.append({
            "id": d.id,
            "camera_id": d.camera_id,
            "camera_name": cam.name if cam else "Unknown",
            "location_name": cam.location_name if cam else "Unknown",
            "license_plate": d.license_plate,
            "normalized_plate": d.normalized_plate,
            "vehicle_type": d.vehicle_type,
            "confidence": d.confidence,
            "detected_at": d.detected_at.isoformat(),
            "pts_ms": d.pts_ms,
            "is_alert_hit": d.is_alert_hit,
            "snapshot_url": d.snapshot_url
        })
    return results

@router.get("/predict/{plate}")
def predict_vehicle_interception(
    plate: str,
    max_predictions: int = Query(3, ge=1, le=5),
    db: Session = Depends(get_db)
):
    """
    Multi-Camera Predictive Interception (Next-Probable-Junction AI):
    Calculates movement bearing, travel velocity, forward cone vectors,
    and estimated times of arrival (ETA) to upcoming police interception nodes.
    """
    from backend.app.services.predictive_interception import PredictiveInterceptionEngine
    prediction = PredictiveInterceptionEngine.predict_next_junctions(db, plate, max_predictions=max_predictions)
    if not prediction:
        return {"target_plate": plate, "predicted_nodes": [], "tactical_recommendation": "Insufficient sightings to establish directional velocity vector."}
    return prediction

@router.get("/search")
def forensic_search_detections(
    pattern: Optional[str] = Query(None, description="Plate search pattern, e.g. GJ01 or GJ01AB1234"),
    city: Optional[str] = Query(None, description="Filter by city"),
    alert_only: bool = Query(False, description="Filter only watchlist hits"),
    min_confidence: float = Query(0.7, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """
    Multi-Attribute Forensic Search:
    Search across vehicle sighting history with partial plate patterns,
    geographic bounds, and alert flags.
    """
    from sqlalchemy import text
    sql = """
        SELECT 
            d.id,
            d.license_plate,
            d.normalized_plate,
            d.camera_id,
            c.name as camera_name,
            c.location_name,
            c.city,
            d.detected_at,
            d.confidence,
            d.snapshot_url,
            d.is_alert_hit
        FROM vehicle_detections d
        JOIN cameras c ON d.camera_id = c.camera_id
        WHERE d.confidence >= :min_conf
    """
    params = {"min_conf": min_confidence, "limit": limit}

    if pattern:
        clean_pat = pattern.upper().replace("-", "").replace(" ", "").replace("*", "%")
        if "%" not in clean_pat:
            clean_pat = f"%{clean_pat}%"
        sql += " AND d.normalized_plate LIKE :pat"
        params["pat"] = clean_pat

    if city:
        sql += " AND c.city ILIKE :city"
        params["city"] = f"%{city}%"

    if alert_only:
        sql += " AND d.is_alert_hit = TRUE"

    sql += " ORDER BY d.detected_at DESC LIMIT :limit"

    rows = db.execute(text(sql), params).fetchall()

    results = []
    for r in rows:
        results.append({
            "detection_id": r[0],
            "license_plate": r[1],
            "normalized_plate": r[2],
            "camera_id": r[3],
            "camera_name": r[4],
            "location_name": r[5],
            "city": r[6],
            "detected_at": r[7].isoformat() if r[7] else None,
            "confidence": float(r[8]),
            "snapshot_url": r[9],
            "is_alert_hit": bool(r[10])
        })

    return {
        "total_matches": len(results),
        "query_pattern": pattern or "ALL",
        "results": results
    }
