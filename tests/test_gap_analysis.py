"""
Test Suite: Spatial Gap Analysis & Blind Spot Analytics
Tests PostGIS ST_Buffer generation, multi-camera coverage zones, blind spots, and API endpoints.
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
from backend.app.services.gap_analysis_service import GapAnalysisService

def test_gap_analysis_service_computation():
    """Verify PostGIS ST_Buffer 200m spatial coverage computation."""
    db = SessionLocal()
    try:
        gap_report = GapAnalysisService.get_coverage_and_blindspots(
            db,
            city="Ahmedabad",
            buffer_radius_meters=200
        )
        assert "coverage_geojson" in gap_report
        assert "department_breakdown" in gap_report
        assert "overall_online_health_percentage" in gap_report

        features = gap_report["coverage_geojson"]["features"]
        assert len(features) > 0, "No coverage buffer features generated"
        first = features[0]
        assert first["type"] == "Feature"
        assert first["geometry"]["type"] in ["Polygon", "MultiPolygon"]
    finally:
        db.close()

def test_gap_analysis_api_endpoint():
    """Verify GET /api/v1/cameras/gap-analysis returns valid buffer polygons."""
    client = TestClient(app)
    response = client.get("/api/v1/cameras/gap-analysis?city=Ahmedabad&radius_meters=150")
    assert response.status_code == 200, f"Gap analysis API failed: {response.text}"
    data = response.json()
    assert "coverage_geojson" in data
    assert "department_breakdown" in data
    assert len(data["coverage_geojson"]["features"]) > 0

def test_gap_analysis_dedicated_page():
    """Verify /gap-analysis portal HTML loads properly."""
    client = TestClient(app)
    response = client.get("/gap-analysis")
    assert response.status_code == 200
    assert "SENTINEL" in response.text

if __name__ == "__main__":
    print("🚀 Running Spatial Gap Analysis Tests...")
    test_gap_analysis_service_computation()
    print("✅ PostGIS buffer calculation verified.")
    test_gap_analysis_api_endpoint()
    print("✅ Gap analysis API verified.")
    test_gap_analysis_dedicated_page()
    print("✅ Gap analysis portal page verified.")
    print("🎉 All Gap Analysis Tests Passed!")
