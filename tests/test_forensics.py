"""
Test Suite: Forensics & Section 65B Legal Evidence Certification
Tests multi-attribute sighting search, SHA-256 cryptographic chain of custody,
Section 65B Indian Evidence Act certification, and forensics portal.
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
from backend.app.services.forensic_service import ForensicService
from backend.app.api.tracking import forensic_search_detections

def test_forensic_multi_attribute_search():
    """Verify querying multi-camera vehicle sightings by partial plate and city."""
    db = SessionLocal()
    try:
        # Ensure test pursuit data exists
        route_tracer.seed_evaluation_trajectory(db, "GJ01AB1234")

        search_res = forensic_search_detections(
            pattern="GJ01",
            city="Ahmedabad",
            alert_only=False,
            min_confidence=0.5,
            limit=20,
            db=db
        )
        assert search_res["total_matches"] >= 4, f"Search expected >= 4 matches, got {search_res['total_matches']}"
        assert search_res["results"][0]["normalized_plate"].startswith("GJ01")
        assert search_res["results"][0]["city"] == "Ahmedabad"
    finally:
        db.close()

def test_section_65b_certificate_generation():
    """Verify Section 65B Evidence Act certificate generation with SHA-256 chain of custody."""
    db = SessionLocal()
    try:
        plate = "GJ01AB1234"
        route_tracer.seed_evaluation_trajectory(db, plate)

        cert = ForensicService.generate_certificate_for_plate(
            db,
            license_plate=plate,
            officer_name="Inspector ABC",
            officer_badge="GP-POL-001"
        )
        assert cert is not None
        assert cert.target_plate == plate
        assert cert.total_detections_certified >= 4
        assert len(cert.overall_dossier_sha256) == 64
        assert cert.certificate_id.startswith("SEC65B-")
        assert "Indian Evidence Act" in cert.statutory_declaration
        assert len(cert.evidence_chain) == cert.total_detections_certified

        # Validate each sighting contains hash and PTS clock
        for s in cert.evidence_chain:
            assert len(s.snapshot_sha256) == 64
            assert s.pts_ms >= 0
    finally:
        db.close()

def test_api_forensic_search_endpoint():
    """Verify GET /api/v1/tracking/search returns JSON list of sightings."""
    client = TestClient(app)
    response = client.get("/api/v1/tracking/search?pattern=GJ01&city=Ahmedabad")
    assert response.status_code == 200, f"Search failed: {response.text}"
    data = response.json()
    assert "results" in data
    assert len(data["results"]) >= 4

def test_api_sec65b_certificate_endpoint():
    """Verify GET /api/v1/forensics/certificate/{plate} returns valid certificate."""
    client = TestClient(app)
    response = client.get("/api/v1/forensics/certificate/GJ01AB1234")
    assert response.status_code == 200, f"Certificate failed: {response.text}"
    cert = response.json()
    assert cert["target_plate"] == "GJ01AB1234"
    assert len(cert["overall_dossier_sha256"]) == 64
    assert "evidence_chain" in cert

def test_forensics_portal_page():
    """Verify /forensics portal HTML is served."""
    client = TestClient(app)
    response = client.get("/forensics")
    assert response.status_code == 200
    assert "SENTINEL" in response.text

if __name__ == "__main__":
    print("🚀 Running Forensics & Section 65B Tests...")
    test_forensic_multi_attribute_search()
    print("✅ Multi-attribute forensic search verified.")
    test_section_65b_certificate_generation()
    print("✅ Section 65B legal certificate generation verified.")
    test_api_forensic_search_endpoint()
    print("✅ Forensic search API verified.")
    test_api_sec65b_certificate_endpoint()
    print("✅ Section 65B certificate API verified.")
    test_forensics_portal_page()
    print("✅ Forensics portal page verified.")
    print("🎉 All Forensics Tests Passed!")
