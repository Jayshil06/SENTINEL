import math
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.app.ai.plate_normalizer import IndianPlateNormalizer
from backend.app.schemas.tracking import PredictiveInterceptionResponse, InterceptionNode

logger = logging.getLogger("sentinel.predictive_interception")

class PredictiveInterceptionEngine:
    """
    Multi-Camera Predictive Interception Engine (Next-Probable-Junction AI)
    Calculates spatial velocity vectors, heading azimuth, and forward cone
    projections to alert downstream police interceptors before suspect arrival.
    """

    @staticmethod
    def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate forward azimuth bearing in degrees from Point 1 to Point 2.
        Formula: atan2(sin(Δλ) * cos(φ2), cos(φ1) * sin(φ2) - sin(φ1) * cos(φ2) * cos(Δλ))
        """
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_lambda = math.radians(lon2 - lon1)

        y = math.sin(delta_lambda) * math.cos(phi2)
        x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)

        initial_bearing = math.atan2(y, x)
        compass_bearing = (math.degrees(initial_bearing) + 360) % 360
        return round(compass_bearing, 2)

    @staticmethod
    def bearing_to_cardinal(bearing: float) -> str:
        """Convert degree bearing to human-readable cardinal direction."""
        dirs = [
            "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"
        ]
        ix = round(bearing / (360.0 / len(dirs))) % len(dirs)
        return f"{dirs[ix]} ({bearing:.1f}°)"

    @staticmethod
    def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Computes great-circle distance between two points in kilometers."""
        r = 6371.0  # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon / 2) ** 2)
        c = 2 * math.asin(math.sqrt(max(0.0, min(1.0, a))))
        return round(r * c, 3)

    @classmethod
    def predict_next_junctions(
        cls,
        db: Session,
        license_plate: str,
        max_predictions: int = 3
    ) -> Optional[PredictiveInterceptionResponse]:
        normalized = IndianPlateNormalizer.clean_raw_text(license_plate)

        # 1. Fetch latest chronological sightings (at least 2 needed for bearing vector)
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
                d.pts_ms
            FROM vehicle_detections d
            JOIN cameras c ON d.camera_id = c.camera_id
            WHERE d.normalized_plate = :plate
            ORDER BY d.detected_at DESC, d.pts_ms DESC
            LIMIT 5
        """)
        rows = db.execute(query, {"plate": normalized}).fetchall()

        if not rows:
            logger.warning(f"No sightings found for plate {normalized} to predict interception.")
            return None

        latest = rows[0]
        curr_cam_id = latest[1]
        curr_cam_name = latest[2]
        curr_loc_name = latest[3]
        curr_city = latest[4]
        curr_lat = float(latest[5])
        curr_lon = float(latest[6])
        curr_time: datetime = latest[7]

        # Find previous sighting with distinct coordinates
        distinct_prev = None
        for r in rows[1:]:
            p_lat = float(r[5])
            p_lon = float(r[6])
            if cls.haversine_distance_km(curr_lat, curr_lon, p_lat, p_lon) > 0.05:
                distinct_prev = r
                break

        has_directional_vector = False
        if distinct_prev:
            prev_lat = float(distinct_prev[5])
            prev_lon = float(distinct_prev[6])
            prev_time: datetime = distinct_prev[7]

            bearing = cls.calculate_bearing(prev_lat, prev_lon, curr_lat, curr_lon)
            distance_km = cls.haversine_distance_km(prev_lat, prev_lon, curr_lat, curr_lon)
            time_diff_sec = abs((curr_time - prev_time).total_seconds())

            if time_diff_sec > 0 and distance_km > 0.05:
                speed_kmh = round((distance_km / (time_diff_sec / 3600.0)), 1)
                speed_kmh = max(25.0, min(120.0, speed_kmh))
            else:
                speed_kmh = 45.0
            has_directional_vector = True
        else:
            bearing = 0.0
            speed_kmh = 40.0

        # 2. Query nearby cameras in the city excluding current camera
        candidates_query = text("""
            SELECT 
                camera_id,
                name,
                location_name,
                city,
                latitude,
                longitude
            FROM cameras
            WHERE camera_id != :curr_cam
              AND LOWER(status) IN ('active', 'online')
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL
        """)
        candidate_rows = db.execute(candidates_query, {"curr_cam": curr_cam_id}).fetchall()

        interception_nodes: List[InterceptionNode] = []

        for cand in candidate_rows:
            c_id = cand[0]
            c_name = cand[1]
            c_loc = cand[2]
            c_city = cand[3]
            c_lat = float(cand[4])
            c_lon = float(cand[5])

            dist_km = cls.haversine_distance_km(curr_lat, curr_lon, c_lat, c_lon)

            # Filter candidates within 0.2 km to 15.0 km radius
            if dist_km < 0.2 or dist_km > 15.0:
                continue

            cand_bearing = cls.calculate_bearing(curr_lat, curr_lon, c_lat, c_lon)
            bearing_diff = abs(cand_bearing - bearing)
            if bearing_diff > 180:
                bearing_diff = 360 - bearing_diff

            # If directional vector is established, candidate must be in forward sector (within ±85°)
            if has_directional_vector and bearing_diff > 85.0:
                continue

            eta_min = round((dist_km / max(speed_kmh, 20.0)) * 60.0, 1)

            if eta_min <= 4.0:
                priority = "IMMEDIATE"
            elif eta_min <= 10.0:
                priority = "PRIMARY"
            else:
                priority = "SECONDARY"

            interception_nodes.append(InterceptionNode(
                camera_id=c_id,
                camera_name=c_name,
                location_name=c_loc,
                city=c_city,
                latitude=c_lat,
                longitude=c_lon,
                distance_km=dist_km,
                bearing_diff_degrees=round(bearing_diff, 1),
                estimated_speed_kmh=speed_kmh,
                eta_minutes=eta_min,
                tactical_priority=priority
            ))

        # Sort candidate nodes by ETA
        interception_nodes.sort(key=lambda n: n.eta_minutes)
        top_predictions = interception_nodes[:max_predictions]

        # Generate a predictive projection line (5 km forward vector from current position)
        bearing_rad = math.radians(bearing)
        proj_dist_km = 4.5
        earth_r = 6371.0
        proj_lat = math.asin(
            math.sin(math.radians(curr_lat)) * math.cos(proj_dist_km / earth_r) +
            math.cos(math.radians(curr_lat)) * math.sin(proj_dist_km / earth_r) * math.cos(bearing_rad)
        )
        proj_lon = math.radians(curr_lon) + math.atan2(
            math.sin(bearing_rad) * math.sin(proj_dist_km / earth_r) * math.cos(math.radians(curr_lat)),
            math.cos(proj_dist_km / earth_r) - math.sin(math.radians(curr_lat)) * math.sin(proj_lat)
        )
        proj_lat_deg = math.degrees(proj_lat)
        proj_lon_deg = math.degrees(proj_lon)

        prediction_ray = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [curr_lon, curr_lat],
                    [proj_lon_deg, proj_lat_deg]
                ]
            },
            "properties": {
                "bearing": bearing,
                "speed_kmh": speed_kmh,
                "direction": cls.bearing_to_cardinal(bearing)
            }
        }

        rec_text = (
            f"Vehicle traveling {cls.bearing_to_cardinal(bearing)} along corridor at estimated {speed_kmh:.0f} km/h. "
            f"Recommend dispatching interceptor squads to {top_predictions[0].location_name if top_predictions else 'forward patrol points'}."
        )

        return PredictiveInterceptionResponse(
            target_plate=normalized,
            last_known_camera_id=curr_cam_id,
            last_known_location=curr_loc_name,
            last_known_coords=[curr_lon, curr_lat],
            last_sighted_at=curr_time,
            current_bearing_degrees=bearing,
            bearing_direction_text=cls.bearing_to_cardinal(bearing),
            estimated_speed_kmh=speed_kmh,
            predicted_nodes=top_predictions,
            prediction_ray_geojson=prediction_ray,
            tactical_recommendation=rec_text
        )
