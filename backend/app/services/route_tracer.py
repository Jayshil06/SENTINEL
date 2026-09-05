import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.app.ai.plate_normalizer import IndianPlateNormalizer
from backend.app.db.models import VehicleDetection, Camera

logger = logging.getLogger("sentinel.route_tracer")

class RouteTracerService:
    """
    Temporal-Spatial Route Reconstruction Engine:
    Identifies, traces, and presents the movement of a designated vehicle
    across the integrated CCTV network with timestamps, snapshots, and speed estimation.
    """
    @staticmethod
    def reconstruct_route(
        db: Session,
        license_plate: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        normalized = IndianPlateNormalizer.clean_raw_text(license_plate)
        logger.info(f"Reconstructing route for vehicle plate: {normalized}")

        if not start_time:
            start_time = datetime.utcnow() - timedelta(days=7)
        if not end_time:
            end_time = datetime.utcnow() + timedelta(days=1)

        # PostGIS query fetching chronological detections and camera coordinates
        query = text("""
            SELECT 
                d.id,
                d.camera_id,
                c.name as camera_name,
                c.location_name,
                c.city,
                c.latitude,
                c.longitude,
                d.detected_at,
                d.pts_ms,
                d.confidence,
                d.snapshot_url,
                d.is_alert_hit
            FROM vehicle_detections d
            JOIN cameras c ON d.camera_id = c.camera_id
            WHERE d.normalized_plate = :plate
              AND d.detected_at BETWEEN :start_time AND :end_time
            ORDER BY d.detected_at ASC, d.pts_ms ASC
        """)

        rows = db.execute(query, {
            "plate": normalized,
            "start_time": start_time,
            "end_time": end_time
        }).fetchall()

        if not rows:
            return {
                "license_plate": normalized,
                "total_sightings": 0,
                "route_geojson": None,
                "milestones": [],
                "summary": "No sightings found for this vehicle in the specified time window."
            }

        milestones = []
        coordinates_path = []
        total_distance_km = 0.0

        for idx, r in enumerate(rows):
            det_id = r[0]
            cam_id = r[1]
            cam_name = r[2]
            loc_name = r[3]
            city = r[4]
            lat = float(r[5])
            lon = float(r[6])
            det_time: datetime = r[7]
            pts_ms = r[8]
            conf = r[9]
            snapshot = r[10]
            is_alert = r[11]

            coords = [lon, lat]
            coordinates_path.append(coords)

            # Compute segment distance and estimated speed between consecutive sightings
            segment_km = 0.0
            speed_kmh = 0.0
            if idx > 0:
                prev_lat = rows[idx - 1][5]
                prev_lon = rows[idx - 1][6]
                prev_time: datetime = rows[idx - 1][7]
                
                # Haversine distance in km
                from math import radians, cos, sin, asin, sqrt
                dlat = radians(lat - prev_lat)
                dlon = radians(lon - prev_lon)
                a = sin(dlat/2)**2 + cos(radians(prev_lat)) * cos(radians(lat)) * sin(dlon/2)**2
                segment_km = 2 * 6371 * asin(sqrt(a))
                total_distance_km += segment_km

                time_diff_hours = (det_time - prev_time).total_seconds() / 3600.0
                if time_diff_hours > 0.001:
                    speed_kmh = round(segment_km / time_diff_hours, 1)

            milestones.append({
                "sequence": idx + 1,
                "detection_id": det_id,
                "camera_id": cam_id,
                "camera_name": cam_name,
                "location_name": loc_name,
                "city": city,
                "coordinates": coords,
                "timestamp": det_time.strftime("%Y-%m-%d %H:%M:%S"),
                "pts_ms": pts_ms,
                "confidence": conf,
                "snapshot_url": snapshot,
                "is_alert_hit": is_alert,
                "segment_distance_km": round(segment_km, 2),
                "estimated_speed_kmh": speed_kmh
            })

        # GeoJSON FeatureCollection containing:
        # 1. LineString of the complete traversed trajectory
        # 2. Points of each milestone camera
        features = []

        if len(coordinates_path) >= 2:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": coordinates_path
                },
                "properties": {
                    "license_plate": normalized,
                    "total_distance_km": round(total_distance_km, 2),
                    "start_time": milestones[0]["timestamp"],
                    "end_time": milestones[-1]["timestamp"],
                    "type": "vehicle_trajectory"
                }
            })

        for m in milestones:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": m["coordinates"]
                },
                "properties": {
                    "type": "trajectory_milestone",
                    "sequence": m["sequence"],
                    "camera_id": m["camera_id"],
                    "location": m["location_name"],
                    "timestamp": m["timestamp"],
                    "speed_kmh": m["estimated_speed_kmh"],
                    "snapshot_url": m["snapshot_url"],
                    "is_alert": m["is_alert_hit"]
                }
            })

        # Compute Predictive Interception (Next Probable Junctions)
        from backend.app.services.predictive_interception import PredictiveInterceptionEngine
        prediction = PredictiveInterceptionEngine.predict_next_junctions(db, normalized)

        # If predictive ray feature exists, append to GeoJSON features
        prediction_dict = None
        if prediction:
            prediction_dict = prediction.model_dump()
            if prediction.prediction_ray_geojson:
                ray_feature = prediction.prediction_ray_geojson
                ray_feature["properties"]["type"] = "predictive_ray"
                features.append(ray_feature)

        return {
            "license_plate": normalized,
            "total_sightings": len(milestones),
            "total_distance_km": round(total_distance_km, 2),
            "first_sighted": milestones[0]["timestamp"],
            "last_sighted": milestones[-1]["timestamp"],
            "route_geojson": {
                "type": "FeatureCollection",
                "features": features
            },
            "milestones": milestones,
            "predictive_interception": prediction_dict
        }

    @staticmethod
    def seed_evaluation_trajectory(db: Session, target_plate: str = "GJ01AB1234") -> int:
        """
        Seeds the exact Hackathon evaluation scenario:
        A designated vehicle traveling down the SG Highway corridor across 4 camera junctions.
        """
        normalized = IndianPlateNormalizer.clean_raw_text(target_plate)
        base_time = datetime.utcnow() - timedelta(minutes=45)

        # Clear any prior test sightings and related alerts for a clean benchmark
        from backend.app.db.models import Alert
        det_ids = [d[0] for d in db.query(VehicleDetection.id).filter(VehicleDetection.normalized_plate == normalized).all()]
        if det_ids:
            db.query(Alert).filter(Alert.detection_id.in_(det_ids)).delete(synchronize_session=False)
        db.query(VehicleDetection).filter(VehicleDetection.normalized_plate == normalized).delete(synchronize_session=False)
        db.commit()

        scenario = [
            ("CAM-AHM-SG-ISCON-05", 0, "/static/snapshots/CAM-05_ISCON_01.jpg", 1000.0),
            ("CAM-AHM-ALPHAONE-14", 8, "/static/snapshots/CAM-14_VASTRAPUR_02.jpg", 481000.0),
            ("CAM-AHM-SG-PAKWAN-04", 17, "/static/snapshots/CAM-04_PAKWAN_03.jpg", 1021000.0),
            ("CAM-AHM-SG-THALTEJ-06", 26, "/static/snapshots/CAM-06_THALTEJ_04.jpg", 1561000.0)
        ]

        count = 0
        for cam_id, min_offset, snapshot, pts in scenario:
            det_time = base_time + timedelta(minutes=min_offset)
            det = VehicleDetection(
                camera_id=cam_id,
                license_plate=target_plate,
                normalized_plate=normalized,
                vehicle_type="SUV",
                confidence=0.95,
                pts_ms=pts,
                detected_at=det_time,
                snapshot_url=snapshot,
                is_alert_hit=True
            )
            db.add(det)
            count += 1
        db.commit()
        logger.info(f"Seeded {count} chronological evaluation sightings for vehicle {normalized}.")
        return count

route_tracer = RouteTracerService()
