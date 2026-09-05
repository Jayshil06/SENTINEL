"""
Test Suite: Vehicle Route Reconstruction & Predictive Interception
Tests multi-camera trajectory tracking, PostGIS temporal reconstruction, speed/bearing calculations,
and the AI next-probable-junction predictive interception engine.
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
from backend.app.services.route_tracer import route_tracer
from backend.app.services.predictive_interception import PredictiveInterceptionEngine

def test_seed_and_reconstruct_route():
    """Verify seeding and reconstructing a multi-junction pursuit corridor."""
    db = SessionLocal()
    try:
        target_plate = "GJ-01-AB-1234"
        count = route_tracer.seed_evaluation_trajectory(db, target_plate=target_plate)
        assert count >= 4, f"Expected at least 4 seeded sightings, got {count}"

        route_data = route_tracer.reconstruct_route(db, license_plate=target_plate)
        assert route_data["license_plate"] == "GJ01AB1234"
        assert route_data["total_sightings"] >= 4
        assert route_data["total_distance_km"] > 1.0
        assert len(route_data["milestones"]) >= 4

        # Validate GeoJSON FeatureCollection
        geojson = route_data["route_geojson"]
        assert geojson["type"] == "FeatureCollection"
        assert len(geojson["features"]) >= 4
    finally:
        db.close()

def test_predictive_interception_engine():
    """Verify predictive interception calculates bearing, speed, and candidate nodes."""
    db = SessionLocal()
    try:
        plate = "GJ01AB1234"
        route_tracer.seed_evaluation_trajectory(db, plate)

        prediction = PredictiveInterceptionEngine.predict_next_junctions(db, plate)
        assert prediction is not None
        assert prediction.target_plate == plate
        assert prediction.current_bearing_degrees >= 0.0
        assert prediction.estimated_speed_kmh > 0.0
        assert prediction.prediction_ray_geojson is not None
        assert len(prediction.predicted_nodes) > 0

        top_candidate = prediction.predicted_nodes[0]
        assert top_candidate.eta_minutes > 0
        assert top_candidate.tactical_priority in ["PRIMARY", "SECONDARY", "PERIMETER"]
    finally:
        db.close()

def test_api_reconstruct_endpoint():
    """Verify GET /api/v1/tracking/route returns trajectory data."""
    client = TestClient(app)
    response = client.get("/api/v1/tracking/route?plate=GJ01AB1234")
    assert response.status_code == 200, f"Reconstruct endpoint failed: {response.text}"
    data = response.json()
    assert data["license_plate"] == "GJ01AB1234"
    assert "route_geojson" in data
    assert "milestones" in data

def test_api_predict_endpoint():
    """Verify GET /api/v1/tracking/predict/{plate} returns predictive vector and candidates."""
    client = TestClient(app)
    response = client.get("/api/v1/tracking/predict/GJ01AB1234")
    assert response.status_code == 200, f"Predict endpoint failed: {response.text}"
    data = response.json()
    assert data["target_plate"] == "GJ01AB1234"
    assert "current_bearing_degrees" in data
    assert "predicted_nodes" in data

if __name__ == "__main__":
    print("🚀 Running Vehicle Route & Predictive Interception Tests...")
    test_seed_and_reconstruct_route()
    print("✅ Route trajectory reconstruction verified.")
    test_predictive_interception_engine()
    print("✅ Predictive interception AI engine verified.")
    test_api_reconstruct_endpoint()
    print("✅ Reconstruct API endpoint verified.")
    test_api_predict_endpoint()
    print("✅ Predictive API endpoint verified.")
    print("🎉 All Tracking & Interception Tests Passed!")
