import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.app.db.models import Camera, Department

class CameraService:
    @staticmethod
    def get_all_cameras(
        db: Session,
        department_code: Optional[str] = None,
        status: Optional[str] = None,
        city: Optional[str] = None
    ) -> List[Camera]:
        query = db.query(Camera)
        if department_code:
            query = query.filter(Camera.department_code == department_code.upper())
        if status:
            query = query.filter(Camera.status == status.lower())
        if city:
            query = query.filter(Camera.city.ilike(f"%{city}%"))
        return query.all()

    @staticmethod
    def get_camera_by_id(db: Session, camera_id: str) -> Optional[Camera]:
        return db.query(Camera).filter(Camera.camera_id == camera_id).first()

    @staticmethod
    def create_or_update_camera(db: Session, cam_data: Dict[str, Any]) -> Camera:
        cam_id = cam_data["camera_id"]
        existing = db.query(Camera).filter(Camera.camera_id == cam_id).first()

        lat = float(cam_data["latitude"])
        lon = float(cam_data["longitude"])
        geom_wkt = f"SRID=4326;POINT({lon} {lat})"

        if existing:
            for key, val in cam_data.items():
                if key not in ["camera_id", "latitude", "longitude"]:
                    setattr(existing, key, val)
            existing.latitude = lat
            existing.longitude = lon
            existing.geom = geom_wkt
            existing.last_ping = datetime.utcnow()
            db.commit()
            db.refresh(existing)
            return existing
        else:
            new_cam = Camera(
                camera_id=cam_id,
                name=cam_data.get("name", f"Camera {cam_id}"),
                department_code=cam_data.get("department_code", "POLICE"),
                location_name=cam_data.get("location_name", ""),
                city=cam_data.get("city", "Gandhinagar"),
                latitude=lat,
                longitude=lon,
                geom=geom_wkt,
                stream_url=cam_data.get("stream_url", ""),
                hls_url=cam_data.get("hls_url", ""),
                codec=cam_data.get("codec", "H264"),
                resolution=cam_data.get("resolution", "1080p"),
                fov_angle=float(cam_data.get("fov_angle", 60.0)),
                heading=float(cam_data.get("heading", 0.0)),
                status=cam_data.get("status", "online"),
                storage_retention_days=int(cam_data.get("storage_retention_days", 15))
            )
            db.add(new_cam)
            db.commit()
            db.refresh(new_cam)
            return new_cam

    @staticmethod
    def bulk_import_from_json(db: Session, file_path: str) -> int:
        with open(file_path, "r", encoding="utf-8") as f:
            cameras = json.load(f)

        dept_names = {
            "POLICE": ("Home Department / Gujarat Police", "Statewide Police Surveillance Grid"),
            "RTO": ("Transport & RTO Department", "State Highways & RTO Checkposts"),
            "PDS": ("Food & Civil Supplies (PDS)", "Fair Price Shops & State Warehouses"),
            "MUNICIPAL": ("Urban Development & Smart City", "City Municipal Corporation Cameras"),
            "PRIVATE": ("Private Commercial Infrastructure", "Commercial Complexes & Residential ANPR"),
            "FOREST": ("Forest & Wildlife Department", "Sanctuary & National Park Perimeters")
        }

        # Ensure all referenced departments exist in the database (deduplicated)
        unique_codes = {cam.get("department_code", "POLICE").upper() for cam in cameras}
        for code in unique_codes:
            existing_dept = db.query(Department).filter(Department.code == code).first()
            if not existing_dept:
                name, desc = dept_names.get(code, (f"{code} Department", f"{code} Surveillance Network"))
                new_dept = Department(code=code, name=name, description=desc)
                db.add(new_dept)
        db.commit()

        count = 0
        for item in cameras:
            CameraService.create_or_update_camera(db, item)
            count += 1
        return count

    @staticmethod
    def get_cameras_geojson(db: Session, department_code: Optional[str] = None, status: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes native PostGIS ST_AsGeoJSON to return a GeoJSON FeatureCollection
        for immediate hardware-accelerated mapping in Leaflet or MapLibre GL.
        """
        query_str = """
            SELECT 
                c.camera_id,
                c.name,
                c.department_code,
                d.name as department_name,
                c.location_name,
                c.city,
                c.latitude,
                c.longitude,
                c.stream_url,
                c.hls_url,
                c.codec,
                c.resolution,
                c.fov_angle,
                c.heading,
                c.status,
                c.storage_retention_days,
                ST_AsGeoJSON(c.geom) as geometry_json
            FROM cameras c
            LEFT JOIN departments d ON c.department_code = d.code
            WHERE 1=1
        """
        params = {}
        if department_code:
            query_str += " AND c.department_code = :dept"
            params["dept"] = department_code.upper()
        if status:
            query_str += " AND c.status = :status"
            params["status"] = status.lower()

        rows = db.execute(text(query_str), params).fetchall()

        features = []
        for r in rows:
            geom = json.loads(r[16]) if r[16] else {"type": "Point", "coordinates": [r[7], r[6]]}
            features.append({
                "type": "Feature",
                "geometry": geom,
                "properties": {
                    "camera_id": r[0],
                    "name": r[1],
                    "department_code": r[2],
                    "department_name": r[3],
                    "location_name": r[4],
                    "city": r[5],
                    "latitude": r[6],
                    "longitude": r[7],
                    "stream_url": r[8],
                    "hls_url": r[9],
                    "codec": r[10],
                    "resolution": r[11],
                    "fov_angle": r[12],
                    "heading": r[13],
                    "status": r[14],
                    "storage_retention_days": r[15]
                }
            })

        return {
            "type": "FeatureCollection",
            "features": features
        }
