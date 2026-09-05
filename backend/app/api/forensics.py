from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import Optional
from backend.app.db.session import get_db
from backend.app.services.forensic_service import ForensicService
from backend.app.schemas.forensics import Section65BCertificateResponse

router = APIRouter(prefix="/api/v1/forensics", tags=["Forensic Chain of Custody (Section 65B)"])

@router.get("/certificate/{license_plate}", response_model=Section65BCertificateResponse)
def get_section_65b_certificate(
    license_plate: str,
    officer_name: str = Query("Inspector ABC", description="Certifying Law Enforcement Officer"),
    officer_badge: str = Query("GP-POL-001", description="Officer Police Identification Badge"),
    db: Session = Depends(get_db)
):
    """
    Generates a legally certified Section 65B Indian Evidence Act Dossier
    with cryptographic SHA-256 hashes for digital evidence admissibility in Court.
    """
    cert = ForensicService.generate_certificate_for_plate(
        db=db,
        license_plate=license_plate,
        officer_name=officer_name,
        officer_badge=officer_badge
    )
    if not cert:
        raise HTTPException(status_code=404, detail=f"No forensic sighting records found for vehicle '{license_plate}'")
    return cert

@router.get("/certificate/{license_plate}/print", response_class=HTMLResponse)
def get_printable_certificate_html(
    license_plate: str,
    officer_name: str = Query("Inspector ABC"),
    officer_badge: str = Query("GP-POL-001"),
    db: Session = Depends(get_db)
):
    """
    Renders a formal, print-ready Section 65B Certificate
    formatted according to Indian High Court & Supreme Court evidentiary guidelines.
    """
    cert = ForensicService.generate_certificate_for_plate(
        db=db,
        license_plate=license_plate,
        officer_name=officer_name,
        officer_badge=officer_badge
    )
    if not cert:
        raise HTTPException(status_code=404, detail="No evidence records found")

    items_html = ""
    for idx, item in enumerate(cert.evidence_chain, start=1):
        items_html += f"""
        <tr style="border-bottom: 1px solid #ddd; font-size: 13px;">
            <td style="padding: 8px; text-align: center;">{idx}</td>
            <td style="padding: 8px;"><strong>{item.camera_id}</strong><br><span style="color:#555;">{item.location_name}, {item.city}</span></td>
            <td style="padding: 8px; font-family: monospace;">{item.detected_at.strftime('%Y-%m-%d %H:%M:%S')} (PTS: {item.pts_ms}ms)</td>
            <td style="padding: 8px; font-family: monospace; font-size: 11px; word-break: break-all; color: #003366;">{item.snapshot_sha256}</td>
            <td style="padding: 8px; text-align: center;">{item.confidence * 100:.1f}%</td>
        </tr>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Section 65B Certificate - {cert.certificate_id}</title>
        <style>
            body {{ font-family: 'Times New Roman', serif; margin: 40px; color: #111; line-height: 1.5; }}
            .header {{ text-align: center; border-bottom: 2px solid #000; padding-bottom: 12px; margin-bottom: 24px; }}
            .title {{ font-size: 20px; font-weight: bold; text-transform: uppercase; margin-bottom: 4px; }}
            .subtitle {{ font-size: 14px; font-weight: bold; color: #333; }}
            .meta-table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
            .meta-table td {{ padding: 6px; font-size: 14px; vertical-align: top; }}
            .evidence-table {{ width: 100%; border-collapse: collapse; margin-top: 15px; margin-bottom: 25px; }}
            .evidence-table th {{ background: #f0f0f0; border: 1px solid #999; padding: 8px; font-size: 13px; text-align: left; }}
            .evidence-table td {{ border: 1px solid #ccc; }}
            .statutory-box {{ background: #f9f9f9; border-left: 4px solid #003366; padding: 14px; margin-bottom: 25px; font-size: 13px; text-align: justify; }}
            .signatures {{ margin-top: 40px; display: flex; justify-content: space-between; }}
            .sig-block {{ width: 45%; border-top: 1px solid #000; padding-top: 8px; font-size: 13px; }}
            @media print {{
                .no-print {{ display: none; }}
                body {{ margin: 20px; }}
            }}
        </style>
    </head>
    <body>
        <div class="no-print" style="margin-bottom: 20px; text-align: right;">
            <button onclick="window.print()" style="background: #003366; color: white; padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; font-weight: bold;">
                🖨️ Print Certificate (Save as PDF)
            </button>
        </div>

        <div class="header">
            <div style="font-size: 13px; font-weight: bold; letter-spacing: 1px;">GOVERNMENT OF GUJARAT • HOME DEPARTMENT • GUJARAT POLICE</div>
            <div class="title">Certificate Under Section 65B of the Indian Evidence Act, 1872</div>
            <div class="subtitle">(Read with Section 63 of Bharatiya Sakshya Adhiniyam, 2023)</div>
            <div style="font-size: 12px; margin-top: 4px; color: #555;">STATEWIDE INTEGRATED VIDEO MANAGEMENT & ANALYTICS PLATFORM (PROJECT SENTINEL)</div>
        </div>

        <table class="meta-table">
            <tr>
                <td style="width: 25%;"><strong>Certificate Identifier:</strong></td>
                <td style="width: 25%; font-family: monospace; font-weight: bold;">{cert.certificate_id}</td>
                <td style="width: 25%;"><strong>Date of Certification:</strong></td>
                <td style="width: 25%;">{cert.generated_at.strftime('%d-%m-%Y %H:%M:%S UTC')}</td>
            </tr>
            <tr>
                <td><strong>Target Vehicle Plate:</strong></td>
                <td style="font-weight: bold; color: #b30000; font-size: 16px;">{cert.target_plate}</td>
                <td><strong>Total Certified Sightings:</strong></td>
                <td>{cert.total_detections_certified} Sightings</td>
            </tr>
            <tr>
                <td><strong>First Recorded Sighting:</strong></td>
                <td>{cert.first_sighted_at.strftime('%Y-%m-%d %H:%M:%S') if cert.first_sighted_at else 'N/A'}</td>
                <td><strong>Last Recorded Sighting:</strong></td>
                <td>{cert.last_sighted_at.strftime('%Y-%m-%d %H:%M:%S') if cert.last_sighted_at else 'N/A'}</td>
            </tr>
            <tr>
                <td><strong>Master SHA-256 Hash:</strong></td>
                <td colspan="3" style="font-family: monospace; font-size: 12px; color: #003366; word-break: break-all;">{cert.overall_dossier_sha256}</td>
            </tr>
        </table>

        <div class="statutory-box">
            <strong>STATUTORY SOLEMN DECLARATION:</strong><br>
            {cert.statutory_declaration}
        </div>

        <h3 style="font-size: 15px; text-transform: uppercase; margin-bottom: 8px;">Schedule of Certified Electronic Evidence (CCTV Ingestion Records):</h3>
        <table class="evidence-table">
            <thead>
                <tr>
                    <th style="width: 5%;">#</th>
                    <th style="width: 30%;">Camera & Location</th>
                    <th style="width: 25%;">Atomic Capture Timestamp</th>
                    <th style="width: 30%;">SHA-256 Digital Fingerprint</th>
                    <th style="width: 10%;">AI Conf.</th>
                </tr>
            </thead>
            <tbody>
                {items_html}
            </tbody>
        </table>

        <div class="signatures">
            <div class="sig-block">
                <strong>(Certifying Law Enforcement Officer)</strong><br>
                Name: {officer_name}<br>
                Rank/Badge: {officer_badge}<br>
                District: Ahmedabad / Gandhinagar Range<br>
                Signature / Digital Token: ___________________
            </div>
            <div class="sig-block" style="text-align: right;">
                <strong>(System Custodian / Tech In-Charge)</strong><br>
                Project SENTINEL State Data Center<br>
                Directorate of Police Communications, Gandhinagar<br>
                Digital Verification Seal: [VERIFIED SHA-256]<br>
                Official Seal & Date: ___________________
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)
