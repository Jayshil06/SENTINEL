"""
Test Suite: Database, PostGIS & Infrastructure
Tests PostGIS extension, spatial tables, geometry operations, and Redis caching.
"""
import sys
import os
import redis
from sqlalchemy import text

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.core.config import settings
from backend.app.db.session import engine, SessionLocal
from backend.app.db.models import Department, Camera, VehicleDetection, Watchlist, Alert

def test_database_connection():
    """Verify PostgreSQL engine connects successfully."""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
        assert result == 1, "Database connection failed"

def test_postgis_extension():
    """Verify PostGIS spatial extension is active and returns version."""
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        conn.commit()
        version = conn.execute(text("SELECT PostGIS_Full_Version();")).scalar()
        assert version is not None, "PostGIS extension is not installed"
        assert "POSTGIS" in version.upper(), f"Unexpected PostGIS version string: {version}"

def test_spatial_tables_exist():
    """Verify all core tables exist in the database."""
    with engine.connect() as conn:
        tables = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)).fetchall()
        table_names = [t[0] for t in tables]
        
        expected_tables = ["departments", "cameras", "vehicle_detections", "watchlist", "alerts"]
        for table in expected_tables:
            assert table in table_names, f"Expected table '{table}' not found in database"

def test_spatial_point_geometry_operations():
    """Verify spatial geometry point insertion and ST_AsText query."""
    with engine.connect() as conn:
        pt = conn.execute(text("SELECT ST_AsText(ST_SetSRID(ST_MakePoint(72.6369, 23.2156), 4326));")).scalar()
        assert pt == "POINT(72.6369 23.2156)", f"Spatial geometry point mismatch: {pt}"

def test_redis_cache_connectivity():
    """Verify Redis in-memory cache responds to PING and handles key/value pairs."""
    r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True)
    assert r.ping() is True, "Redis ping failed"
    
    test_key = "sentinel:test:ping"
    r.set(test_key, "active", ex=10)
    val = r.get(test_key)
    assert val == "active", f"Redis read/write mismatch: expected 'active', got '{val}'"
    r.delete(test_key)

if __name__ == "__main__":
    print("🚀 Running Database & PostGIS Tests...")
    test_database_connection()
    print("✅ Database connection verified.")
    test_postgis_extension()
    print("✅ PostGIS extension verified.")
    test_spatial_tables_exist()
    print("✅ Core spatial tables verified.")
    test_spatial_point_geometry_operations()
    print("✅ Spatial point geometry verified.")
    test_redis_cache_connectivity()
    print("✅ Redis cache connectivity verified.")
    print("🎉 All Database & Infrastructure Tests Passed!")
