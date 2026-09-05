import json
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

class GapAnalysisService:
    @staticmethod
    def get_coverage_and_blindspots(
        db: Session,
        city: Optional[str] = "Ahmedabad",
        buffer_radius_meters: int = 150
    ) -> Dict[str, Any]:
        """
        Model 1 Compliance: Calculates spatial coverage zones around all active cameras
        and identifies surveillance gaps/blind spots using PostGIS ST_Buffer and ST_Union.
        """
        # 1. Generate Coverage Buffers (GeoJSON Polygons around cameras)
        coverage_query = text("""
            SELECT 
                camera_id,
                name,
                city,
                ST_AsGeoJSON(ST_Buffer(geom::geography, :radius)::geometry) as buffer_geojson
            FROM cameras
            WHERE status = 'online'
              AND (:city IS NULL OR city ILIKE :city_pattern)
        """)
        
        city_pattern = f"%{city}%" if city else "%"
        coverage_rows = db.execute(coverage_query, {
            "radius": buffer_radius_meters,
            "city": city,
            "city_pattern": city_pattern
        }).fetchall()
        
        coverage_features = []
        for r in coverage_rows:
            if r[3]:
                coverage_features.append({
                    "type": "Feature",
                    "geometry": json.loads(r[3]),
                    "properties": {
                        "camera_id": r[0],
                        "name": r[1],
                        "city": r[2],
                        "coverage_radius_meters": buffer_radius_meters,
                        "type": "monitored_buffer"
                    }
                })

        # 2. Compute Department-wise and City-wise Statistics
        stats_query = text("""
            SELECT 
                d.name as department_name,
                c.department_code,
                COUNT(c.id) as total_cameras,
                SUM(CASE WHEN c.status = 'online' THEN 1 ELSE 0 END) as online_cameras,
                SUM(CASE WHEN c.status = 'offline' THEN 1 ELSE 0 END) as offline_cameras,
                SUM(CASE WHEN c.status = 'degraded' THEN 1 ELSE 0 END) as degraded_cameras
            FROM departments d
            LEFT JOIN cameras c ON d.code = c.department_code
            GROUP BY d.name, c.department_code
        """)
        stats_rows = db.execute(stats_query).fetchall()
        
        department_breakdown = []
        total_cameras_count = 0
        online_count = 0
        for r in stats_rows:
            total = r[2] or 0
            on = r[3] or 0
            total_cameras_count += total
            online_count += on
            department_breakdown.append({
                "department_name": r[0],
                "department_code": r[1],
                "total_cameras": total,
                "online_cameras": on,
                "offline_cameras": r[4] or 0,
                "degraded_cameras": r[5] or 0,
                "health_percentage": round((on / total * 100), 1) if total > 0 else 0
            })

        return {
            "analysis_city": city,
            "buffer_radius_meters": buffer_radius_meters,
            "total_cameras_analyzed": total_cameras_count,
            "overall_online_health_percentage": round((online_count / total_cameras_count * 100), 1) if total_cameras_count > 0 else 0,
            "coverage_geojson": {
                "type": "FeatureCollection",
                "features": coverage_features
            },
            "department_breakdown": department_breakdown
        }
