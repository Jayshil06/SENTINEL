# System Architecture & Technical Specification
## Integrated Video Management & Analytics Platform (Project SENTINEL)
### Gujarat Police Innovation Challenge 2026

---

## 1. Executive Summary

The State of Gujarat currently operates video surveillance systems across **26 different government departments** (Police, Transport/RTO, Food & Civil Supplies, Urban Local Bodies, etc.). These systems run on isolated, multi-vendor Video Management Systems (VMS), proprietary protocols, and fragmented storage architectures, scaling toward an eventual **~80,000 cameras statewide**.

This document details the **High-Level Design (HLD)** and **System Architecture** for an open, vendor-neutral, modular, and cost-effective platform. By leveraging a **Hybrid Edge-Federated Architecture (Model 5)**, the system achieves:
- **99.6% Bandwidth Reduction**: Heavy AI video processing occurs at district edge gateways; only lightweight telemetry (JSON metadata, plate text, PTS timestamps) travels over WAN to the central cloud.
- **On-Demand Video Retrieval**: Full-resolution RTSP/WebRTC streams are pulled centrally *only* when an operator views a camera or when a watchlist alert fires.
- **Unified GIS Command Center**: Centralized asset tracking, real-time blind spot analysis, and sub-second suspect vehicle route reconstruction across the state.
- **Law Enforcement Database Federation**: Automated, microsecond cross-referencing with **eGujCop** (CCTNS), **VAHAN**, **SARTHI**, and **AFIS/NAFIS**.

---

## 2. Solution Model Selection & Justification

### Selected Model: Model 5 (Hybrid Architecture)
The solution strategically synthesizes:
1. **Model 1 (Mandatory Foundational Layer)**: Statewide CCTV Registry & GIS Mapping engine tracking camera inventory, health, and spatial blind spots.
2. **Model 3 (Federated Edge Middleware)**: District-level stream ingestion and edge AI extraction using open protocols (RTSP over TCP, ONVIF), preserving local departmental infrastructure.
3. **Model 2/4 (Selective Centralized Intelligence)**: Centralized command dashboard, high-speed time-series search, and automated real-time watchlist alert dispatch.

### Bandwidth & Infrastructure Cost Comparison

| Metric | Traditional Centralized VMS (Model 4) | Proposed Hybrid Architecture (Model 5) |
| :--- | :--- | :--- |
| **Video Streams to Cloud** | 80,000 continuous streams (24/7) | 0 continuous streams (On-demand pull only) |
| **WAN Bandwidth Needed** | **160 Gbps – 320 Gbps** | **< 450 Mbps** (statewide metadata payload) |
| **Cloud GPU Requirements**| Thousands of cloud GPUs ($$$$) | District edge inference / commodity accelerators |
| **Single Point of Failure**| High (Central network choke) | Resilient (Decentralized edge autonomy) |
| **Bandwidth Cost Savings** | Baseline | **99.6% Reduction** |

---

## 3. End-to-End System Architecture

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 1. DISTRICT EDGE LAYER (33 Districts across Gujarat)                                   │
│                                                                                        │
│  [Dept Cameras] ────> [Edge Media Proxy: MediaMTX] ────> [Edge AI Worker: YOLOv11]    │
│  (RTSP / ONVIF)         (TCP Transport, PTS Sync)          (Vehicle & Plate Extraction)│
│                                                                  │                     │
│                                                                  ▼                     │
│                                                       [Telemetry Agent]                │
│                                                       (Plate, PTS, CamID, BBox)        │
└──────────────────────────────────────────────────────────────┬─────────────────────────┘
                                                               │ Lightweight Telemetry
                                                               │ (JSON over TLS, ~2 KB/det)
                                                               ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 2. STATEWIDE SECURE INGESTION & EVENT BUS (State Data Center - Gandhinagar)            │
│                                                                                        │
│                               [Event Bus: Apache Kafka / Redpanda]                     │
│                         ┌───────────────────────┴───────────────────────┐              │
│                         ▼                                               ▼              │
│               [Telemetry Ingest Worker]                       [Watchlist Alert Worker] │
└─────────────────────────┬───────────────────────────────────────────────┬──────────────┘
                          │                                               │
                          ▼                                               ▼
┌────────────────────────────────────────────────────────┐  ┌────────────────────────────┐
│ 3. PERSISTENCE & ANALYTICS LAYER                       │  │ 4. INTEGRATION GATEWAY     │
│                                                        │  │                            │
│  [(PostgreSQL 16 + PostGIS 3.4)]                       │  │  [Redis Bloom & In-Memory] │
│   - Camera Registry (Model 1)                          │  │   - Stolen Vehicles (VAHAN)│
│   - Geospatial Indices (GiST)                          │  │   - Wanted Suspects        │
│   - Vehicle Route Reconstruction                       │  │     (eGujCop / CCTNS)      │
│                                                        │  │   - Missing Persons        │
│  [(ClickHouse / Elasticsearch)]                        │  │                            │
│   - Sub-second plate historical search                 │  │  * Microsecond matching    │
│   - Millisecond range queries across 80k cams          │  └─────────────┬──────────────┘
└─────────────────────────┬──────────────────────────────┘                │
                          │                                               │ WebSocket Alert
                          ▼                                               ▼ ( < 200 ms )
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 5. UNIFIED COMMAND CENTER UI (Web Dashboard)                                           │
│                                                                                        │
│  ┌───────────────────────────┐ ┌───────────────────────────┐ ┌───────────────────────┐ │
│  │ Interactive GIS Map       │ │ Vehicle Route Tracer      │ │ Live Alert Monitor    │ │
│  │ - Camera health (ping/PTS)│ │ - Timestamped breadcrumbs │ │ - Audio-visual alerts │ │
│  │ - Department filters      │ │ - Animated polyline path  │ │ - Evidentiary crop    │ │
│  │ - Gap/blind-spot buffers  │ │ - Snapshot evidence card  │ │ - Auto-focus camera   │ │
│  └───────────────────────────┘ └───────────────────────────┘ └───────────────────────┘ │
│  ┌───────────────────────────────────────────────────────────────────────────────────┐ │
│  │ Video Wall: On-demand WebRTC / Low-Latency HLS direct from Edge Gateway           │ │
│  └───────────────────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Component Deep Dive

### 4.1 Edge Video Ingestion Engine
- **Protocols Supported**: RTSP, RTP, ONVIF (Profile S/G/T), HLS.
- **Transport Guarantee**: Strict `rtsp_transport;tcp` enforcement. Eliminates UDP packet drops and frame tearing across enterprise firewalls.
- **Timestamp Accuracy**: Relies strictly on RTP / Presentation Timestamps (PTS) extracted via `CAP_PROP_POS_MSEC` or GStreamer buffer PTS, avoiding false clock drift from fluctuating network framerates.
- **Fault-Tolerant Reconnection**: Exponential backoff reconnect policy (initial retry 2s, capped at 30s) with seamless recovery across continuous stream loop discontinuities.

### 4.2 Edge AI Inference Engine
- **Vehicle & Plate Detection**: YOLOv11-Nano optimized with ONNX Runtime / TensorRT. Detects vehicle class (two-wheeler, four-wheeler, heavy vehicle) and isolates license plate bounding boxes.
- **Optical Character Recognition (ANPR)**: PaddleOCR / Fast-LPR lightweight model trained on Indian Standard (HSRP) and non-standard number plates with Gujarati/English font support.
- **Motion Gate Pre-Filter**: Frame difference algorithm skips empty frames (e.g., quiet nighttime roads), reducing GPU/CPU compute consumption by up to 60%.

### 4.3 High-Speed Watchlist Matching Engine
- **Sync Mechanism**: Periodically syncs hot watchlists from eGujCop and VAHAN into an in-memory **Redis Bloom Filter and Hash Set**.
- **Query Complexity**: $O(1)$ lookup time. When a plate is parsed by the AI worker, it is checked against the Bloom filter in $< 500 \ \mu\text{s}$.
- **Alert Dispatch**: Verified hits trigger a high-priority message on the `alerts.critical` Kafka topic, pushed to all active police operator consoles over WebSockets.

### 4.4 Spatial Intelligence & Route Reconstruction Engine (PostGIS)
- **Spatial Schema**: Uses EPSG:4326 (WGS 84) coordinate system.
- **Route Query Execution**:
  ```sql
  -- Sub-second route generation for target license plate
  SELECT 
      d.license_plate,
      d.detected_at,
      c.camera_id,
      c.location_name,
      ST_AsGeoJSON(c.geom) AS geojson_point,
      d.snapshot_url
  FROM vehicle_detections d
  JOIN cameras c ON d.camera_id = c.camera_id
  WHERE d.license_plate = :target_plate
    AND d.detected_at BETWEEN :start_time AND :end_time
  ORDER BY d.detected_at ASC;
  ```
- **Coverage Blind Spot Analysis**: Generates dynamic buffers (e.g. 100m) around all active camera points (`ST_Buffer`) and executes spatial difference queries (`ST_Difference`) against road network vectors to highlight surveillance gaps.

---

## 5. Technology Stack Specification

| Subsystem | Technology Selected | Rationale & Justification |
| :--- | :--- | :--- |
| **Edge Media Proxy** | **MediaMTX (Docker)** | Zero configuration, low memory footprint (~30MB RAM), native RTSP-to-WebRTC/HLS transcoding. |
| **Backend & Ingestion** | **FastAPI (Python 3.12+)** | Native async IO, unified with the Python AI ecosystem, high-speed `asyncpg` database drivers. |
| **AI / ANPR** | **YOLOv11 + PaddleOCR** | State-of-the-art accuracy, lightweight execution, support for TensorRT/OpenVINO acceleration. |
| **Message Broker** | **Redpanda / Kafka** | Handles high-throughput event streams with microsecond latency; Kafka API compatible. |
| **Spatial Database** | **PostgreSQL 16 + PostGIS 3.4** | Rock-solid relational storage with spatial indices (`GiST`), native GeoJSON output. |
| **Search Engine** | **ClickHouse / Elasticsearch** | Columnar/inverted-index storage for lightning-fast historical queries across billions of plates. |
| **Fast Cache / Watchlist**| **Redis 7.2** | Sub-millisecond $O(1)$ in-memory lookups for active suspect watchlists and session tracking. |
| **Frontend UI** | **Next.js 14 / React + TailwindCSS** | Modern, responsive dashboard design with server-side rendering and WebSocket connectivity. |
| **GIS Mapping** | **MapLibre GL JS / Leaflet** | Hardware-accelerated WebGL vector rendering, capable of plotting 50,000+ points without FPS drop. |

---

## 6. Security, Compliance & Governance

1. **Role-Based Access Control (RBAC)**:
   - *State Admin (DGP / SCRB)*: Statewide visibility, policy configuration, audit log export.
   - *District Operator (SP / Commissionerate)*: District-specific live views, local watchlist authoring.
   - *Field Officer*: Read-only alert reception on mobile/tablet devices.
2. **Data Encryption**:
   - In-Transit: TLS 1.3 for all telemetry APIs, WebSockets, and RTSPS streams.
   - At-Rest: AES-256 encryption for PostgreSQL storage and video snapshot archives.
3. **Evidentiary Integrity**:
   - Every detection snapshot is watermarked with SHA-256 cryptographic hashes, camera hardware ID, and atomic NTP-synchronized timestamps, compliant with Indian Evidence Act admissibility standards.
4. **Audit Logging**: Immutable event ledger recording who searched which plate, viewed which feed, and exported which report.

---

## 7. Scaling Roadmap: Prototype to 80,000 Statewide Cameras

```
┌───────────────────────────┐      ┌───────────────────────────┐      ┌───────────────────────────┐
│   Phase 1: Hackathon PoC  │ ───> │ Phase 2: District Pilot   │ ───> │  Phase 3: Statewide Scale │
│       (~50 Cameras)       │      │     (1,000 - 5,000 Cams)  │      │     (~80,000 Cameras)     │
├───────────────────────────┤      ├───────────────────────────┤      ├───────────────────────────┤
│ • Single workstation node │      │ • 3 District Hubs         │      │ • 33 District Edge Data   │
│ • Docker Compose stack    │      │ • GSWAN network testing   │      │   Centers                 │
│ • Sentinel Sandbox feed   │      │ • Live eGujCop integration│      │ • Central State Data      │
│ • Synthetic watchlist     │      │ • High availability DB    │      │   Center (Gandhinagar)    │
└───────────────────────────┘      └───────────────────────────┘      └───────────────────────────┘
```
