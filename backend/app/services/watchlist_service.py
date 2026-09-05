import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
import redis
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.db.models import Watchlist, Alert, VehicleDetection, Camera
from backend.app.ai.plate_normalizer import IndianPlateNormalizer

logger = logging.getLogger("sentinel.watchlist_service")

class WatchlistService:
    """
    High-Performance Watchlist Matching Service:
    - Syncs eGujCop / VAHAN / SARTHI stolen & wanted records to in-memory Redis.
    - Achieves O(1) sub-millisecond lookup latency.
    - Triggers automated real-time alerts upon positive match.
    """
    def __init__(self):
        if settings.REDIS_URL:
            self.redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        else:
            self.redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD,
                decode_responses=True
            )
        self.REDIS_WATCHLIST_SET = "sentinel:watchlist:plates"
        self.REDIS_WATCHLIST_PREFIX = "sentinel:watchlist:meta:"

    def add_to_watchlist(
        self,
        db: Session,
        license_plate: str,
        category: str,
        reason: Optional[str] = None,
        fir_number: Optional[str] = None,
        department: str = "Gujarat Police",
        priority: str = "CRITICAL"
    ) -> Watchlist:
        normalized = IndianPlateNormalizer.clean_raw_text(license_plate)
        
        # 1. Update/Insert in PostGIS DB
        existing = db.query(Watchlist).filter(Watchlist.normalized_plate == normalized).first()
        if existing:
            existing.category = category
            existing.reason = reason
            existing.fir_number = fir_number
            existing.department = department
            existing.priority = priority
            existing.is_active = True
            db.commit()
            db.refresh(existing)
            target = existing
        else:
            target = Watchlist(
                license_plate=license_plate,
                normalized_plate=normalized,
                category=category,
                reason=reason,
                fir_number=fir_number,
                department=department,
                priority=priority,
                is_active=True
            )
            db.add(target)
            db.commit()
            db.refresh(target)

        # 2. Sync to Redis for Sub-Millisecond Matching
        self.redis_client.sadd(self.REDIS_WATCHLIST_SET, normalized)
        meta_key = f"{self.REDIS_WATCHLIST_PREFIX}{normalized}"
        self.redis_client.set(meta_key, json.dumps({
            "id": target.id,
            "license_plate": target.license_plate,
            "normalized_plate": target.normalized_plate,
            "category": target.category,
            "reason": target.reason or "",
            "fir_number": target.fir_number or "",
            "department": target.department,
            "priority": target.priority
        }))

        logger.info(f"Added plate {normalized} to active watchlist ({category} - {priority}).")
        return target

    def sync_all_from_db(self, db: Session) -> int:
        """Loads all active database watchlist entries into Redis."""
        active_items = db.query(Watchlist).filter(Watchlist.is_active == True).all()
        pipe = self.redis_client.pipeline()
        pipe.delete(self.REDIS_WATCHLIST_SET)
        
        count = 0
        for item in active_items:
            pipe.sadd(self.REDIS_WATCHLIST_SET, item.normalized_plate)
            meta_key = f"{self.REDIS_WATCHLIST_PREFIX}{item.normalized_plate}"
            pipe.set(meta_key, json.dumps({
                "id": item.id,
                "license_plate": item.license_plate,
                "normalized_plate": item.normalized_plate,
                "category": item.category,
                "reason": item.reason or "",
                "fir_number": item.fir_number or "",
                "department": item.department,
                "priority": item.priority
            }))
            count += 1
        pipe.execute()
        logger.info(f"Synced {count} active watchlist records from DB to Redis cache.")
        return count

    def check_and_alert(
        self,
        db: Session,
        camera_id: str,
        plate_text: str,
        pts_ms: Optional[float] = None,
        snapshot_url: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Microsecond Watchlist Lookup.
        If match found, creates an Alert record and returns alert payload.
        """
        normalized = IndianPlateNormalizer.clean_raw_text(plate_text)
        
        # O(1) Redis Set Membership Check (< 0.5 ms)
        is_wanted = self.redis_client.sismember(self.REDIS_WATCHLIST_SET, normalized)
        
        # Also store the detection event in DB
        det = VehicleDetection(
            camera_id=camera_id,
            license_plate=plate_text,
            normalized_plate=normalized,
            pts_ms=pts_ms,
            snapshot_url=snapshot_url,
            is_alert_hit=bool(is_wanted)
        )
        db.add(det)
        db.commit()
        db.refresh(det)

        if not is_wanted:
            return None

        # Fetch metadata from Redis
        meta_key = f"{self.REDIS_WATCHLIST_PREFIX}{normalized}"
        meta_raw = self.redis_client.get(meta_key)
        meta = json.loads(meta_raw) if meta_raw else {}

        # Look up camera details
        cam = db.query(Camera).filter(Camera.camera_id == camera_id).first()
        location_name = cam.location_name if cam else "Unknown Location"
        city = cam.city if cam else "Unknown"

        # Record Alert in DB
        alert_record = Alert(
            detection_id=det.id,
            watchlist_id=meta.get("id"),
            camera_id=camera_id,
            license_plate=normalized,
            alert_type=meta.get("category", "Watchlist Hit"),
            priority=meta.get("priority", "CRITICAL")
        )
        db.add(alert_record)
        db.commit()
        db.refresh(alert_record)

        alert_payload = {
            "alert_id": alert_record.id,
            "detection_id": det.id,
            "camera_id": camera_id,
            "location_name": location_name,
            "city": city,
            "license_plate": normalized,
            "category": meta.get("category", "Stolen Vehicle"),
            "priority": meta.get("priority", "CRITICAL"),
            "fir_number": meta.get("fir_number", "N/A"),
            "department": meta.get("department", "Gujarat Police"),
            "detected_at": det.detected_at.isoformat(),
            "pts_ms": pts_ms,
            "snapshot_url": snapshot_url,
            "coordinates": [cam.longitude, cam.latitude] if cam else None
        }

        # Publish to Redis channel for WebSocket fan-out
        self.redis_client.publish("sentinel:alerts:live", json.dumps(alert_payload))
        logger.warning(f"🚨 CRITICAL ALERT: Plate {normalized} matched watchlist at {camera_id} ({location_name})!")
        return alert_payload

    def get_recent_alerts(self, db: Session, limit: int = 50) -> List[Dict[str, Any]]:
        alerts = db.query(Alert).order_by(Alert.created_at.desc()).limit(limit).all()
        results = []
        for a in alerts:
            cam = db.query(Camera).filter(Camera.camera_id == a.camera_id).first()
            results.append({
                "alert_id": a.id,
                "camera_id": a.camera_id,
                "location_name": cam.location_name if cam else "Unknown Location",
                "license_plate": a.license_plate,
                "alert_type": a.alert_type,
                "priority": a.priority,
                "acknowledged": a.acknowledged,
                "created_at": a.created_at.isoformat(),
                "coordinates": [cam.longitude, cam.latitude] if cam else None
            })
        return results

watchlist_service = WatchlistService()
