from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from backend.app.db.session import Base

class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False) # e.g. POLICE, RTO, PDS, MUNICIPAL, PRIVATE
    name = Column(String(150), nullable=False) # e.g. Home Department / Gujarat Police
    description = Column(Text, nullable=True)

    cameras = relationship("Camera", back_populates="department")


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(String(100), unique=True, index=True, nullable=False) # e.g. CAM-AHM-SG-01
    name = Column(String(200), nullable=False)
    department_code = Column(String(50), ForeignKey("departments.code"), nullable=False, index=True)
    location_name = Column(String(200), nullable=True)
    city = Column(String(100), default="Gandhinagar", index=True)
    
    # Geographic Coordinates & PostGIS Point
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    geom = Column(Geometry(geometry_type='POINT', srid=4326), nullable=True)
    
    # Stream Details
    stream_url = Column(String(500), nullable=False) # RTSP endpoint
    hls_url = Column(String(500), nullable=True)     # HLS playback fallback
    codec = Column(String(20), default="H264")        # H264 or H265
    resolution = Column(String(20), default="1080p")
    
    # Physical FOV & Orientation
    fov_angle = Column(Float, default=60.0)           # Field of view coverage angle (degrees)
    heading = Column(Float, default=0.0)              # Compass direction (0-360 degrees)
    
    # Operational Status & Retention
    status = Column(String(30), default="online", index=True) # online, offline, degraded
    last_ping = Column(DateTime, default=datetime.utcnow)
    storage_retention_days = Column(Integer, default=15)
    created_at = Column(DateTime, default=datetime.utcnow)

    department = relationship("Department", back_populates="cameras")
    detections = relationship("VehicleDetection", back_populates="camera")

    # Spatial Index is automatically created by GeoAlchemy2 on geom column


class VehicleDetection(Base):
    __tablename__ = "vehicle_detections"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(String(100), ForeignKey("cameras.camera_id"), nullable=False, index=True)
    license_plate = Column(String(50), index=True, nullable=False)        # Raw OCR text: e.g. GJ-01-AB-1234
    normalized_plate = Column(String(50), index=True, nullable=False)     # Cleaned: GJ01AB1234
    vehicle_type = Column(String(50), default="Car")                      # Car, Two-Wheeler, Truck, Bus
    confidence = Column(Float, default=0.90)                              # AI confidence (0.0 - 1.0)
    
    pts_ms = Column(Float, nullable=True)                                 # Monotonic Presentation Timestamp
    detected_at = Column(DateTime, default=datetime.utcnow, index=True)  # System timestamp
    snapshot_url = Column(String(500), nullable=True)                     # Vehicle/plate crop path
    is_alert_hit = Column(Boolean, default=False, index=True)

    camera = relationship("Camera", back_populates="detections")

    __table_args__ = (
        Index('idx_plate_detected_at', 'normalized_plate', 'detected_at'),
    )


class Watchlist(Base):
    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True, index=True)
    license_plate = Column(String(50), nullable=False)
    normalized_plate = Column(String(50), unique=True, index=True, nullable=False)
    category = Column(String(100), nullable=False)                        # Stolen Vehicle, Wanted Criminal, Missing Person
    reason = Column(Text, nullable=True)
    fir_number = Column(String(100), nullable=True)
    department = Column(String(100), default="Gujarat Police")
    priority = Column(String(20), default="CRITICAL")                     # CRITICAL, HIGH, MEDIUM
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    detection_id = Column(Integer, ForeignKey("vehicle_detections.id"), nullable=True)
    watchlist_id = Column(Integer, ForeignKey("watchlist.id"), nullable=True)
    camera_id = Column(String(100), nullable=False, index=True)
    license_plate = Column(String(50), nullable=False, index=True)
    alert_type = Column(String(100), nullable=False)
    priority = Column(String(20), default="CRITICAL")
    acknowledged = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
