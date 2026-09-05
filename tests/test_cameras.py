"""
Test Suite: Camera Registry & GIS Mapping
Tests bulk camera ingestion, departmental filtering, GeoJSON spatial serialization, and API endpoints.
"""
import sys
import os
from fastapi.testclient import TestClient

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.main import app
from backend.app.db.session import SessionLocal
from backend.app.services.camera_service import CameraService

def test_camera_bulk_import():
    """Verify loading Gujarat statewide camera inventory into PostGIS."""
    db = SessionLocal()
    try:
        sample_file = os.path.join(os.getcwd(), "data", "sample_gujarat_cameras.json")
        assert os.path.exists(sample_file), f"Camera dataset missing at {sample_file}"
        imported_count = CameraService.bulk_import_from_json(db, sample_file)
        assert imported_count >= 20, f"Expected at least 20 cameras, got {imported_count}"
    finally:
        db.close()

def test_camera_department_filtering():
    """Verify department-wise filtering returns expected camera subsets."""
    db = SessionLocal()
    try:
        police_cams = CameraService.get_all_cameras(db, department_code="POLICE")
        rto_cams = CameraService.get_all_cameras(db, department_code="RTO")
        pds_cams = CameraService.get_all_cameras(db, department_code="PDS")

        assert len(police_cams) > 0, "No police cameras found in registry"
        assert len(rto_cams) > 0, "No RTO cameras found in registry"
        assert len(pds_cams) > 0, "No PDS cameras found in registry"
    finally:
        db.close()

def test_camera_geojson_generation():
    """Verify PostGIS ST_AsGeoJSON FeatureCollection generation."""
    db = SessionLocal()
    try:
        geojson_data = CameraService.get_cameras_geojson(db)
        assert geojson_data.get("type") == "FeatureCollection"
        features = geojson_data.get("features", [])
        assert len(features) >= 20, f"Expected >= 20 features, got {len(features)}"

        first = features[0]
        assert first["type"] == "Feature"
        assert "geometry" in first and first["geometry"]["type"] == "Point"
        assert "properties" in first
        props = first["properties"]
        for required in ["camera_id", "name", "city", "department_code", "stream_url"]:
            assert required in props, f"Missing required property: {required}"
    finally:
        db.close()

def test_api_cameras_geojson_endpoint():
    """Verify GET /api/v1/cameras/geojson returns 200 and valid GeoJSON."""
    client = TestClient(app)
    response = client.get("/api/v1/cameras/geojson")
    assert response.status_code == 200, f"GeoJSON endpoint error: {response.text}"
    geojson = response.json()
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) >= 20

def test_api_cameras_list_endpoint():
    """Verify GET /api/v1/cameras returns JSON list of cameras."""
    client = TestClient(app)
    response = client.get("/api/v1/cameras")
    assert response.status_code == 200
    cameras = response.json()
    assert isinstance(cameras, list)
    assert len(cameras) >= 20

if __name__ == "__main__":
    print("🚀 Running Camera Registry & GIS Mapping Tests...")
    test_camera_bulk_import()
    print("✅ Camera bulk import verified.")
    test_camera_department_filtering()
    print("✅ Department filtering verified.")
    test_camera_geojson_generation()
    print("✅ PostGIS GeoJSON generation verified.")
    test_api_cameras_geojson_endpoint()
    print("✅ Camera GeoJSON API endpoint verified.")
    test_api_cameras_list_endpoint()
    print("✅ Camera list API endpoint verified.")
    print("🎉 All Camera Registry Tests Passed!")
