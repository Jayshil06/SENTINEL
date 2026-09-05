from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.services.watchlist_service import watchlist_service
from backend.app.ai.plate_normalizer import IndianPlateNormalizer
from backend.app.db.models import Watchlist, Alert

router = APIRouter(prefix="/watchlist", tags=["Watchlist & Law Enforcement Alerts"])

class WatchlistCreate(BaseModel):
    license_plate: str
    category: str = "Stolen Vehicle" # Stolen Vehicle, Wanted Suspect, Missing Person
    reason: Optional[str] = "Reported stolen in FIR"
    fir_number: Optional[str] = "FIR-2026-AHM-9021"
    department: str = "Gujarat Police"
    priority: str = "CRITICAL"

class SimulatedDetection(BaseModel):
    camera_id: str
    license_plate: str
    vehicle_type: str = "Car"
    snapshot_url: Optional[str] = None

@router.get("")
def list_watchlist(db: Session = Depends(get_db)):
    items = db.query(Watchlist).filter(Watchlist.is_active == True).all()
    return [
        {
            "id": w.id,
            "license_plate": w.license_plate,
            "normalized_plate": w.normalized_plate,
            "category": w.category,
            "reason": w.reason,
            "fir_number": w.fir_number,
            "department": w.department,
            "priority": w.priority,
            "created_at": w.created_at.isoformat()
        }
        for w in items
    ]

@router.post("")
def add_plate(data: WatchlistCreate, db: Session = Depends(get_db)):
    item = watchlist_service.add_to_watchlist(
        db,
        license_plate=data.license_plate,
        category=data.category,
        reason=data.reason,
        fir_number=data.fir_number,
        department=data.department,
        priority=data.priority
    )
    return {"status": "success", "item": item.normalized_plate}

@router.delete("/{plate}")
def remove_plate(plate: str, db: Session = Depends(get_db)):
    norm = IndianPlateNormalizer.clean_raw_text(plate)
    item = db.query(Watchlist).filter(Watchlist.normalized_plate == norm).first()
    if not item:
        raise HTTPException(status_code=404, detail="Plate not in watchlist")
    item.is_active = False
    db.commit()
    watchlist_service.redis_client.srem(watchlist_service.REDIS_WATCHLIST_SET, norm)
    return {"status": "success", "removed": norm}

@router.get("/alerts")
def get_alerts(limit: int = Query(50), db: Session = Depends(get_db)):
    return watchlist_service.get_recent_alerts(db, limit=limit)

@router.post("/simulate-detection")
def simulate_detection(data: SimulatedDetection, db: Session = Depends(get_db)):
    """
    Simulates a live ANPR hit for evaluation testing.
    Checks against watchlist and emits real-time WebSocket alert if matched.
    """
    alert = watchlist_service.check_and_alert(
        db,
        camera_id=data.camera_id,
        plate_text=data.license_plate,
        snapshot_url=data.snapshot_url
    )
    return {
        "status": "processed",
        "camera_id": data.camera_id,
        "plate": data.license_plate,
        "is_alert": alert is not None,
        "alert": alert
    }

@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.acknowledged = True
    db.commit()
    return {"status": "acknowledged", "alert_id": alert_id}
