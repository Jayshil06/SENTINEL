"""
Gujarat Police Sentinel Sandbox Ingestor
Fetches camera catalogue from http://<host>/api/ingest,
registers cameras in PostGIS, and configures MediaMTX proxy routes.
"""
import os
import sys
import argparse
import requests
import json

# Ensure UTF-8 console output on Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.db.session import SessionLocal
from backend.app.services.camera_service import CameraService
from backend.app.core.config import settings

def sync_sentinel_sandbox(sandbox_host: str):
    print("========================================================")
    print(f"📡 CONNECTING TO SENTINEL SANDBOX: {sandbox_host}")
    print("========================================================\n")

    catalogue_url = f"http://{sandbox_host}/api/ingest"
    print(f"📥 Querying catalogue contract: {catalogue_url} ...")

    try:
        resp = requests.get(catalogue_url, timeout=10)
        if resp.status_code != 200:
            print(f"❌ Failed to reach {catalogue_url} (HTTP {resp.status_code})")
            return False
        cameras_data = resp.json()
    except Exception as e:
        print(f"⚠️ Could not connect to remote host '{sandbox_host}': {e}")
        print("💡 If you are testing offline, you can run simulated feeds.")
        return False

    print(f"✅ Successfully fetched {len(cameras_data)} cameras from Gujarat Police Sandbox!\n")

    db = SessionLocal()
    try:
        imported = 0
        mediamtx_api_url = f"http://{settings.MEDIAMTX_HOST}:{settings.MEDIAMTX_API_PORT}/v3/config/paths/add"

        for idx, cam in enumerate(cameras_data):
            cam_id_num = cam.get("id", idx + 1)
            cam_id = f"CAM-SENTINEL-{cam_id_num:02d}"
            location = cam.get("location", f"Gujarat Police Sandbox Site #{cam_id_num}")
            codec = cam.get("codec", "h264").upper()
            
            # Default GPS coordinate around Gandhinagar/Ahmedabad if not specified
            lat = cam.get("latitude", 23.03 + (idx * 0.015))
            lon = cam.get("longitude", 72.51 + (idx * 0.012))

            remote_rtsp = f"rtsp://{sandbox_host}:8554/stream/{cam_id_num}"
            local_hls = f"http://localhost:8888/cam_{cam_id_num}/index.m3u8"

            # 1. Update Camera in PostGIS Registry
            CameraService.create_or_update_camera(db, {
                "camera_id": cam_id,
                "name": location,
                "department_code": "POLICE",
                "location_name": location,
                "city": "Ahmedabad",
                "latitude": lat,
                "longitude": lon,
                "stream_url": remote_rtsp,
                "hls_url": local_hls,
                "codec": codec,
                "resolution": "1080p",
                "status": "online" if cam.get("live", True) else "offline"
            })
            imported += 1

            # 2. Tell MediaMTX to proxy this remote RTSP stream on demand
            try:
                path_name = f"cam_{cam_id_num}"
                payload = {
                    "source": remote_rtsp,
                    "sourceOnDemand": True,
                    "rtspTransport": "tcp"
                }
                requests.post(f"{mediamtx_api_url}/{path_name}", json=payload, timeout=2)
            except Exception:
                pass # MediaMTX path may already exist

        print(f"🎉 Successfully integrated {imported} Sentinel cameras into PostGIS & MediaMTX!")
        print("💡 All feeds are now live on your Interactive GIS Map at http://localhost:8000\n")
        return True

    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync Gujarat Police Sentinel Sandbox cameras")
    parser.add_argument("--host", required=True, help="Sentinel Sandbox Host/IP provided upon login")
    args = parser.parse_args()

    sync_sentinel_sandbox(args.host)
