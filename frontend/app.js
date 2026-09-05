// Project SENTINEL — Frontend Command Center Engine
const API_BASE = "/api/v1";

// 1. Initialize Leaflet Map centered on Gandhinagar & Ahmedabad
const map = L.map('map', { zoomControl: false }).setView([23.12, 72.58], 11);
L.control.zoom({ position: 'bottomright' }).addTo(map);

// 100% Free Base Maps (Zero API Key, Zero Watermarks)
const darkTiles = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
  attribution: '&copy; Esri &mdash; Open GIS Data',
  maxZoom: 16
}).addTo(map);

const osmTiles = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '&copy; OpenStreetMap contributors',
  maxZoom: 19
});

const satelliteTiles = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
  attribution: '&copy; Esri World Imagery',
  maxZoom: 19
});

// Layer Switcher (Bottom Left)
L.control.layers({
  "Dark Tactical": darkTiles,
  "OpenStreetMap": osmTiles,
  "Satellite": satelliteTiles
}, null, { position: 'bottomleft' }).addTo(map);

// Layer Groups
const cameraMarkersLayer = L.layerGroup().addTo(map);
const cameraMarkersMap = new Map();
const gapAnalysisLayer = L.layerGroup();
const routeTrajectoryLayer = L.layerGroup().addTo(map);

let allCamerasGeoJSON = null;
let currentRoutePolyline = null;
let activeStreamAnimId = null;

// Department Colors
const DEPT_COLORS = {
  POLICE: '#3b82f6',    // Blue
  RTO: '#f59e0b',       // Amber
  PDS: '#10b981',       // Emerald
  MUNICIPAL: '#a855f7', // Purple
  PRIVATE: '#ec4899'    // Pink
};

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/[&<>"']/g, m => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  })[m]);
}

// 2. Fetch and Render Cameras (Model 1 Compliance)
async function loadCameras() {
  try {
    const res = await fetch(`${API_BASE}/cameras/geojson`);
    allCamerasGeoJSON = await res.json();
    filterCameras();
  } catch (err) {
    console.error("Failed to load camera registry:", err);
  }
}

function renderCameraMarkers(featuresToRender = null) {
  cameraMarkersLayer.clearLayers();
  cameraMarkersMap.clear();
  if (!allCamerasGeoJSON) return;

  const features = featuresToRender || allCamerasGeoJSON.features;
  const activeDepts = Array.from(document.querySelectorAll('.dept-checkbox:checked')).map(cb => cb.value);

  features.forEach(feat => {
    const props = feat.properties;
    if (!activeDepts.includes(props.department_code)) return;

    const [lon, lat] = feat.geometry.coordinates;
    const color = DEPT_COLORS[props.department_code] || '#6b7280';
    const isOnline = (props.status || '').toLowerCase() === 'online';

    // Custom circle icon
    const icon = L.divIcon({
      className: 'custom-cam-pin',
      html: `
        <div style="background-color: ${color}; width: 14px; height: 14px; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 8px ${color};"></div>
      `,
      iconSize: [14, 14],
      iconAnchor: [7, 7]
    });

    const marker = L.marker([lat, lon], { icon }).addTo(cameraMarkersLayer);

    // Popup with camera info & stream launcher
    const popupContent = `
      <div class="text-gray-900 text-xs p-1" style="min-width: 220px;">
        <div class="flex items-center justify-between font-bold text-sm mb-1">
          <span>${props.camera_id}</span>
          <span class="text-[10px] uppercase px-1.5 py-0.5 rounded text-white" style="background:${color}">${props.department_code}</span>
        </div>
        <div class="text-gray-700 font-semibold mb-0.5">${props.name}</div>
        <div class="text-gray-500 mb-2 text-[11px]"><i class="fa-solid fa-location-dot text-red-500 mr-1"></i>${props.location_name ? props.location_name + ', ' : ''}${props.city}</div>
        <div class="grid grid-cols-2 gap-1 text-[11px] bg-gray-100 p-1.5 rounded mb-2 font-mono">
          <div>Status: <b class="${isOnline ? 'text-emerald-600' : 'text-rose-600'}">${props.status.toUpperCase()}</b></div>
          <div>Codec: <b>${props.codec}</b></div>
          <div>Resolution: <b>${props.resolution}</b></div>
          <div>FOV: <b>${props.fov_angle}°</b></div>
        </div>
        <button onclick="openLiveStreamModal('${props.camera_id}', '${props.name.replace(/'/g, "\\'")}', '${props.codec}', '${props.resolution}', '${props.hls_url || ''}')" 
                class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-1.5 px-3 rounded flex items-center justify-center space-x-1 transition shadow">
          <i class="fa-solid fa-play text-xs"></i>
          <span>Open Live Stream</span>
        </button>
      </div>
    `;

    marker.bindPopup(popupContent);
    marker.camProperties = props;
    cameraMarkersMap.set(props.camera_id, marker);
  });
}

function updateCameraListSidebar(features, query = '') {
  const container = document.getElementById('camera-list');
  const countBadge = document.getElementById('camera-count');
  if (!container || !countBadge) return;

  const totalCount = allCamerasGeoJSON && allCamerasGeoJSON.features ? allCamerasGeoJSON.features.length : 0;
  if (query) {
    countBadge.textContent = `${features.length} / ${totalCount} Found`;
    countBadge.className = features.length > 0
      ? 'text-[11px] font-mono text-cyan-400 font-semibold'
      : 'text-[11px] font-mono text-rose-400 font-semibold';
  } else {
    countBadge.textContent = `${features.length} Cameras`;
    countBadge.className = 'text-[11px] text-gray-400 font-mono';
  }

  container.innerHTML = '';

  if (features.length === 0) {
    container.innerHTML = `
      <div class="text-center py-8 px-3 space-y-2.5">
        <i class="fa-solid fa-camera-slash text-2xl text-gray-600 block"></i>
        <div class="text-xs text-gray-400 font-medium">No matching cameras found</div>
        <div class="text-[11px] text-gray-500">No cameras match "<span class="text-gray-300 font-mono">${escapeHtml(query)}</span>"</div>
        <button id="reset-cam-search-btn" class="mt-2 inline-flex items-center space-x-1 text-[11px] text-indigo-400 hover:text-indigo-300 bg-gray-800 hover:bg-gray-700 px-2.5 py-1 rounded border border-gray-700 transition">
          <i class="fa-solid fa-rotate-left text-[10px]"></i>
          <span>Reset search</span>
        </button>
      </div>
    `;
    const resetBtn = document.getElementById('reset-cam-search-btn');
    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        const input = document.getElementById('cam-search-input');
        if (input) {
          input.value = '';
          filterCameras();
          input.focus();
        }
      });
    }
    return;
  }

  features.forEach(f => {
    const p = f.properties;
    const color = DEPT_COLORS[p.department_code] || '#6b7280';
    const isOnline = (p.status || '').toLowerCase() === 'online';
    const statusDot = isOnline ? 'bg-emerald-400 ring-emerald-950' : 'bg-rose-500 ring-rose-950';

    const item = document.createElement('div');
    item.dataset.camId = p.camera_id;
    item.className = 'group p-2.5 rounded-lg bg-gray-800/40 hover:bg-gray-800 cursor-pointer border border-gray-700/40 hover:border-gray-600 flex items-center justify-between transition-all duration-150 shadow-sm';
    item.innerHTML = `
      <div class="min-w-0 flex-1 pr-2">
        <div class="flex items-center space-x-1.5 mb-0.5">
          <span class="w-2 h-2 rounded-full ${statusDot} ring-2 shrink-0" title="Status: ${p.status}"></span>
          <span class="font-bold text-gray-200 font-mono tracking-tight group-hover:text-white truncate">${p.camera_id}</span>
        </div>
        <div class="text-[11px] text-gray-300 font-medium truncate">${p.name}</div>
        <div class="text-[10px] text-gray-500 truncate flex items-center gap-1 mt-0.5">
          <i class="fa-solid fa-location-dot text-gray-400 text-[9px]"></i>
          <span>${p.location_name ? p.location_name + ', ' : ''}${p.city || ''}</span>
        </div>
      </div>
      <div class="flex flex-col items-end shrink-0 space-y-1">
        <span class="text-[9px] font-mono uppercase font-bold px-1.5 py-0.5 rounded text-white shadow-xs" style="background:${color}">${p.department_code}</span>
        <span class="text-[9px] font-mono text-gray-400">${p.resolution || '1080p'}</span>
      </div>
    `;

    item.addEventListener('click', () => {
      const [lon, lat] = f.geometry.coordinates;
      map.flyTo([lat, lon], 16, { duration: 0.8 });
      const marker = cameraMarkersMap.get(p.camera_id);
      if (marker) {
        setTimeout(() => marker.openPopup(), 400);
      }
    });

    container.appendChild(item);
  });
}

// 3. Gap Analysis Toggle (Model 1 Blind Spots)
let isGapAnalysisActive = false;
const toggleGapBtn = document.getElementById('toggle-gap-btn');
if (toggleGapBtn) {
  toggleGapBtn.addEventListener('click', async () => {
    isGapAnalysisActive = !isGapAnalysisActive;
    const btn = toggleGapBtn;

  if (isGapAnalysisActive) {
    btn.classList.add('bg-amber-600', 'text-white');
    btn.classList.remove('bg-gray-800', 'text-amber-300');
    btn.innerHTML = `<i class="fa-solid fa-eye-slash"></i><span>Hide Coverage Buffers</span>`;

    try {
      const res = await fetch(`${API_BASE}/cameras/gap-analysis?city=Ahmedabad&radius_meters=200`);
      const data = await res.json();
      gapAnalysisLayer.clearLayers();

      data.coverage_geojson.features.forEach(feat => {
        L.geoJSON(feat, {
          style: {
            color: '#f59e0b',
            weight: 1.5,
            fillColor: '#f59e0b',
            fillOpacity: 0.15,
            dashArray: '4, 4'
          }
        }).addTo(gapAnalysisLayer);
      });

      gapAnalysisLayer.addTo(map);
    } catch (err) {
      console.error("Gap analysis failed:", err);
    }
  } else {
    btn.classList.remove('bg-amber-600', 'text-white');
    btn.classList.add('bg-gray-800', 'text-amber-300');
    btn.innerHTML = `<i class="fa-solid fa-radar"></i><span>Show Coverage & Blind Spots</span>`;
    map.removeLayer(gapAnalysisLayer);
  }
});
}

// 4. Vehicle Route Reconstruction (The Hackathon Test Scenario)
async function traceVehicleRoute(plate) {
  if (!plate) return;
  const traceBtn = document.getElementById('trace-route-btn');
  traceBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i>`;

  try {
    const res = await fetch(`${API_BASE}/tracking/route?plate=${encodeURIComponent(plate)}`);
    const data = await res.json();

    routeTrajectoryLayer.clearLayers();
    const summaryBox = document.getElementById('route-summary');
    const sightingsElem = document.getElementById('route-sightings');
    const distanceElem = document.getElementById('route-distance');
    const timelineElem = document.getElementById('route-timeline');

    if (data.total_sightings === 0) {
      alert(`No sightings found for plate: ${plate}. Click 'Load Demo Pursuit' to test the scenario.`);
      summaryBox.classList.add('hidden');
      return;
    }

    summaryBox.classList.remove('hidden');
    sightingsElem.textContent = `${data.total_sightings} Junctions`;
    distanceElem.textContent = `${data.total_distance_km} km`;
    timelineElem.innerHTML = '';

    // Render Milestones in Timeline
    data.milestones.forEach((m, idx) => {
      const card = document.createElement('div');
      card.className = 'p-2 bg-gray-950/80 rounded border border-gray-800 flex items-center justify-between';
      card.innerHTML = `
        <div class="flex items-center space-x-2">
          <span class="w-5 h-5 rounded-full bg-cyan-600 text-white flex items-center justify-center font-bold text-[10px]">${idx + 1}</span>
          <div>
            <div class="font-semibold text-gray-200">${m.location_name}</div>
            <div class="text-[10px] text-gray-500 font-mono">${m.timestamp.split(' ')[1]} • ${m.estimated_speed_kmh} km/h</div>
          </div>
        </div>
        <button class="text-cyan-400 hover:text-cyan-300 text-xs px-2 py-1" onclick="focusRoutePoint(${m.coordinates[1]}, ${m.coordinates[0]})">
          <i class="fa-solid fa-crosshairs"></i>
        </button>
      `;
      timelineElem.appendChild(card);
    });

    // Render Predictive Interception AI Card
    const predCard = document.getElementById('predictive-card');
    const predSpeed = document.getElementById('pred-speed');
    const predDir = document.getElementById('pred-direction');
    const predNodes = document.getElementById('pred-nodes');

    if (data.predictive_interception && data.predictive_interception.predicted_nodes && data.predictive_interception.predicted_nodes.length > 0) {
      const pred = data.predictive_interception;
      predCard.classList.remove('hidden');
      predSpeed.textContent = `${pred.estimated_speed_kmh} km/h`;
      predDir.innerHTML = `<i class="fa-solid fa-compass text-cyan-400 mr-1"></i> Heading: <b class="text-cyan-200">${pred.bearing_direction_text}</b>`;
      predNodes.innerHTML = '';

      pred.predicted_nodes.forEach((node, nIdx) => {
        const nodeEl = document.createElement('div');
        const badgeColor = node.tactical_priority === 'IMMEDIATE' ? 'bg-red-900/80 text-red-300 border-red-700' : 'bg-amber-900/80 text-amber-300 border-amber-700';
        nodeEl.className = 'p-1.5 bg-gray-900/90 rounded border border-gray-750 flex items-center justify-between text-[11px]';
        nodeEl.innerHTML = `
          <div>
            <div class="font-bold text-gray-200 truncate max-w-[150px]">${node.location_name}</div>
            <div class="text-[10px] text-gray-400">${node.distance_km} km away • ETA: <b class="text-amber-400">${node.eta_minutes} min</b></div>
          </div>
          <span class="text-[9px] px-1.5 py-0.5 rounded border font-mono ${badgeColor}">${node.tactical_priority}</span>
        `;
        nodeEl.addEventListener('click', () => map.flyTo([node.latitude, node.longitude], 15));
        predNodes.appendChild(nodeEl);

        // Add Pulsing Radar Marker on GIS Map for Interception Node
        const radarIcon = L.divIcon({
          className: 'radar-pin',
          html: `<div style="background:#f59e0b; color:#111; width:22px; height:22px; border-radius:50%; border:2px solid white; display:flex; align-items:center; justify-content:center; font-weight:bold; font-size:10px; box-shadow:0 0 14px #f59e0b; animation:pulse 1.2s infinite;">P${nIdx + 1}</div>`,
          iconSize: [22, 22],
          iconAnchor: [11, 11]
        });
        const radarMarker = L.marker([node.latitude, node.longitude], { icon: radarIcon }).addTo(routeTrajectoryLayer);
        radarMarker.bindPopup(`
          <div class="text-gray-900 text-xs p-1">
            <div class="font-bold text-sm text-amber-700">🎯 Interception Node #${nIdx + 1}: ${node.location_name}</div>
            <div class="text-gray-700">Distance: <b>${node.distance_km} km</b></div>
            <div class="text-gray-700">Estimated Arrival (ETA): <b class="text-red-600">${node.eta_minutes} Minutes</b></div>
            <div class="text-gray-600 text-[10px]">Recommend forward interceptor patrol dispatch.</div>
          </div>
        `);
      });
    } else {
      predCard.classList.add('hidden');
    }

    // Draw Glowing Polyline & Predictive Rays on GIS Map
    const geojson = data.route_geojson;
    const lineFeatures = geojson.features.filter(f => f.geometry.type === 'LineString');
    
    // Past Trajectory (Cyan)
    const pastRoute = lineFeatures.find(f => !f.properties || f.properties.type !== 'predictive_ray');
    if (pastRoute) {
      const coords = pastRoute.geometry.coordinates.map(c => [c[1], c[0]]);
      
      // Outer glow line
      L.polyline(coords, {
        color: '#06b6d4',
        weight: 8,
        opacity: 0.4
      }).addTo(routeTrajectoryLayer);

      // Inner sharp route line
      currentRoutePolyline = L.polyline(coords, {
        color: '#22d3ee',
        weight: 4,
        opacity: 0.9,
        dashArray: '8, 6'
      }).addTo(routeTrajectoryLayer);

      // Add numbered milestone markers
      data.milestones.forEach(m => {
        const numIcon = L.divIcon({
          className: 'milestone-pin',
          html: `<div style="background:#0891b2; color:white; width:22px; height:22px; border-radius:50%; border:2px solid white; display:flex; align-items:center; justify-content:center; font-weight:bold; font-size:11px; box-shadow:0 0 10px #22d3ee;">${m.sequence}</div>`,
          iconSize: [22, 22],
          iconAnchor: [11, 11]
        });
        const marker = L.marker([m.coordinates[1], m.coordinates[0]], { icon: numIcon }).addTo(routeTrajectoryLayer);
        marker.bindPopup(`
          <div class="text-gray-900 text-xs p-1">
            <div class="font-bold text-sm text-cyan-800">Stop #${m.sequence}: ${m.location_name}</div>
            <div class="text-gray-600 font-mono">Time: ${m.timestamp}</div>
            <div class="text-gray-600">Speed: <b>${m.estimated_speed_kmh} km/h</b></div>
            <div class="text-gray-600">Camera: <b>${m.camera_id}</b></div>
          </div>
        `);
      });

      map.fitBounds(currentRoutePolyline.getBounds(), { padding: [50, 50] });
    }

    // Predictive Interception Projection Ray (Dashed Amber)
    const predRay = lineFeatures.find(f => f.properties && f.properties.type === 'predictive_ray');
    if (predRay) {
      const rayCoords = predRay.geometry.coordinates.map(c => [c[1], c[0]]);
      L.polyline(rayCoords, {
        color: '#f59e0b',
        weight: 4,
        opacity: 0.85,
        dashArray: '4, 8'
      }).addTo(routeTrajectoryLayer);
    }

  } catch (err) {
    console.error("Route reconstruction error:", err);
  } finally {
    traceBtn.innerHTML = `<i class="fa-solid fa-route"></i><span>Trace</span>`;
  }
}

function focusRoutePoint(lat, lon) {
  map.flyTo([lat, lon], 16);
}

document.getElementById('trace-route-btn').addEventListener('click', () => {
  const plate = document.getElementById('route-plate-input').value.trim();
  traceVehicleRoute(plate);
});

document.getElementById('clear-route-btn').addEventListener('click', () => {
  routeTrajectoryLayer.clearLayers();
  document.getElementById('route-summary').classList.add('hidden');
});

// Seed Demo Pursuit button for instant 1-click evaluation
document.getElementById('seed-demo-btn').addEventListener('click', async () => {
  try {
    const res = await fetch(`${API_BASE}/tracking/seed-evaluation-scenario?plate=GJ01AB1234`, { method: 'POST' });
    const data = await res.json();
    document.getElementById('route-plate-input').value = "GJ01AB1234";
    traceVehicleRoute("GJ01AB1234");
  } catch (err) {
    console.error("Failed to seed demo pursuit:", err);
  }
});

// 5. Real-Time WebSocket Alerts Hub
function connectAlertWebSocket() {
  try {
    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsHost = window.location.host || "localhost:8000";
    const ws = new WebSocket(`${wsProtocol}//${wsHost}/ws/alerts`);

    ws.onopen = () => console.log("✅ WebSocket connected to Project SENTINEL Alert Gateway.");

    ws.onmessage = (event) => {
      try {
        const alertData = JSON.parse(event.data);
        renderAlertCard(alertData);
        playAlertAudio();
        triggerPulsingMarker(alertData);
      } catch (e) {
        console.warn("WebSocket parse error:", e);
      }
    };

    ws.onerror = (e) => {
      // In serverless / Vercel cloud, WebSockets may be unsupported; silence spam
      console.log("WebSocket alert gateway idle/unavailable in serverless mode.");
    };

    ws.onclose = () => {
      // Reconnect with a backoff so serverless doesn't spam reconnection loops
      setTimeout(connectAlertWebSocket, 15000);
    };
  } catch (err) {
    console.warn("WebSocket connection bypassed:", err);
  }
}

function renderAlertCard(data) {
  const container = document.getElementById('alert-feed');
  const card = document.createElement('div');
  card.className = 'alert-card-enter p-3 bg-red-950/80 border-l-4 border-l-red-500 border-y border-r border-red-800/50 rounded-xl text-xs space-y-1.5 shadow-lg hover:bg-red-900/80 transition-colors duration-150 cursor-pointer';
  card.innerHTML = `
    <div class="flex items-center justify-between">
      <span class="bg-red-600 text-white font-bold text-[10px] px-1.5 py-0.5 rounded font-mono">${data.category}</span>
      <span class="text-[10px] text-gray-400 font-mono">${new Date(data.detected_at).toLocaleTimeString()}</span>
    </div>
    <div class="font-bold text-sm text-red-200 font-mono tracking-wider">${data.license_plate}</div>
    <div class="text-gray-300"><i class="fa-solid fa-location-dot text-red-400 mr-1"></i> ${data.location_name}</div>
    <div class="text-[11px] text-gray-400 font-mono">FIR: ${data.fir_number} • ${data.camera_id}</div>
  `;

  card.addEventListener('click', () => {
    if (data.coordinates) {
      map.flyTo([data.coordinates[1], data.coordinates[0]], 16);
    }
  });

  container.insertBefore(card, container.firstChild);

  // Update header alert counter badge
  unreadAlertCount++;
  if (headerAlertBadge) {
    headerAlertBadge.textContent = unreadAlertCount > 99 ? '99+' : unreadAlertCount;
    headerAlertBadge.classList.remove('hidden');
  }
}

function playAlertAudio() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(880, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.3);
    gain.gain.setValueAtTime(0.3, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.3);
  } catch (e) {
    // Audio context may require user interaction
  }
}

function triggerPulsingMarker(data) {
  if (!data.coordinates) return;
  const alertIcon = L.divIcon({
    className: 'pulsing-alert-marker',
    iconSize: [26, 26],
    iconAnchor: [13, 13]
  });
  const pulseMarker = L.marker([data.coordinates[1], data.coordinates[0]], { icon: alertIcon }).addTo(map);
  setTimeout(() => map.removeLayer(pulseMarker), 12000);
}

// 6. Simulate Alert Button (for Evaluation Demo)
document.getElementById('simulate-alert-btn').addEventListener('click', async () => {
  try {
    await fetch(`${API_BASE}/watchlist/simulate-detection`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        camera_id: "CAM-AHM-SG-PAKWAN-04",
        license_plate: "GJ-01-AB-1234",
        vehicle_type: "SUV"
      })
    });
  } catch (err) {
    console.error("Simulation failed:", err);
  }
});

// 7. Live Stream Modal Player (Real Video + HLS + RTSP Relay)
let hlsInstance = null;

window.openLiveStreamModal = function(camId, camName, codec, resolution, hlsUrl) {
  document.getElementById('modal-cam-name').textContent = camName;
  document.getElementById('modal-cam-meta').textContent = `${camId} • RTSP over TCP • ${resolution} • ${codec}`;
  document.getElementById('stream-modal').classList.remove('hidden');

  const videoElement = document.getElementById('live-video-player');
  const canvasElement = document.getElementById('stream-canvas');

  videoElement.muted = true; // Required for modern browsers to allow autoplay
  videoElement.autoplay = true;
  videoElement.loop = true;

  // Stream endpoints
  const hlsStreamUrl = "http://localhost:8888/stream/1/index.m3u8";
  const mp4FallbackUrl = `/static/test_feed.mp4?t=${Date.now()}`;

  function playMp4Fallback() {
    videoElement.src = mp4FallbackUrl;
    videoElement.play().then(() => {
      videoElement.classList.remove('hidden');
      canvasElement.classList.add('hidden');
    }).catch((err) => {
      console.warn("HTML5 video autoplay blocked, starting canvas fallback:", err);
      videoElement.classList.add('hidden');
      canvasElement.classList.remove('hidden');
      startCanvasSimulation();
    });
  }

  if (window.Hls && Hls.isSupported()) {
    if (hlsInstance) hlsInstance.destroy();
    hlsInstance = new Hls({ lowLatencyMode: true, maxBufferLength: 3 });
    hlsInstance.loadSource(hlsStreamUrl);
    hlsInstance.attachMedia(videoElement);
    
    hlsInstance.on(Hls.Events.MANIFEST_PARSED, () => {
      videoElement.play().then(() => {
        videoElement.classList.remove('hidden');
        canvasElement.classList.add('hidden');
      }).catch(playMp4Fallback);
    });

    hlsInstance.on(Hls.Events.ERROR, (event, data) => {
      if (data.fatal) {
        hlsInstance.destroy();
        hlsInstance = null;
        playMp4Fallback();
      }
    });
  } else {
    playMp4Fallback();
  }

  function startCanvasSimulation() {
    const ctx = canvasElement.getContext('2d');
    let frameCount = 0;
    function renderFrame() {
      frameCount++;
      ctx.fillStyle = '#1e293b';
      ctx.fillRect(0, 0, canvasElement.width, canvasElement.height);
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(100, 0, 440, canvasElement.height);
      ctx.fillStyle = '#ffffff';
      for (let y = 0; y < canvasElement.height; y += 40) {
        ctx.fillRect(315, (y + frameCount * 4) % canvasElement.height, 10, 20);
      }
      const carY = (frameCount * 3) % (canvasElement.height + 100) - 80;
      ctx.fillStyle = '#3b82f6';
      ctx.fillRect(260, carY, 120, 180);
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(280, carY + 140, 80, 25);
      ctx.fillStyle = '#000000';
      ctx.font = 'bold 11px monospace';
      ctx.fillText('GJ01AB1234', 285, carY + 157);
      document.getElementById('stream-pts-overlay').textContent = `PTS: ${Date.now()} ms | Frame #${frameCount}`;
      activeStreamAnimId = requestAnimationFrame(renderFrame);
    }
    renderFrame();
  }
};

document.getElementById('close-modal-btn').addEventListener('click', () => {
  document.getElementById('stream-modal').classList.add('hidden');
  const videoElement = document.getElementById('live-video-player');
  videoElement.pause();
  videoElement.src = "";
  if (hlsInstance) {
    hlsInstance.destroy();
    hlsInstance = null;
  }
  if (activeStreamAnimId) cancelAnimationFrame(activeStreamAnimId);
});

// ==============================================================================
// CAMERA ASSET SEARCH & DEPARTMENT FILTERING (SYNCHRONIZED WITH MAP & SIDEBAR)
// ==============================================================================
function filterCameras() {
  if (!allCamerasGeoJSON || !allCamerasGeoJSON.features) return;

  const searchInput = document.getElementById('cam-search-input');
  const query = (searchInput ? searchInput.value : '').trim().toLowerCase();
  const clearBtn = document.getElementById('cam-search-clear');
  if (clearBtn) {
    clearBtn.classList.toggle('hidden', query.length === 0);
  }

  const activeDepts = Array.from(document.querySelectorAll('.dept-checkbox:checked')).map(cb => cb.value);

  // Filter features matching active department AND search query
  const matchingFeatures = allCamerasGeoJSON.features.filter(feat => {
    const p = feat.properties;
    // 1. Department filter
    if (!activeDepts.includes(p.department_code)) return false;

    // 2. Search query filter
    if (!query) return true;

    // Multi-attribute search string: camera_id, name, location_name, city, department_code, status, etc.
    const searchString = [
      p.camera_id,
      p.name,
      p.location_name,
      p.city,
      p.department_code,
      p.department_name,
      p.status,
      p.codec,
      p.resolution
    ].filter(Boolean).join(' ').toLowerCase();

    // Support multiple space-separated words (AND logic, e.g. "ahmedabad police")
    const words = query.split(/\s+/).filter(Boolean);
    return words.every(w => searchString.includes(w));
  });

  // Render matching markers on map
  renderCameraMarkers(matchingFeatures);

  // Render list in sidebar
  updateCameraListSidebar(matchingFeatures, query);
}

const camSearchInput = document.getElementById('cam-search-input');
const camSearchClear = document.getElementById('cam-search-clear');

if (camSearchInput) {
  camSearchInput.addEventListener('input', () => {
    filterCameras();
  });

  camSearchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      const firstItem = document.querySelector('#camera-list > div[data-cam-id]');
      if (firstItem) {
        firstItem.click();
      }
    } else if (e.key === 'Escape') {
      camSearchInput.value = '';
      filterCameras();
      camSearchInput.blur();
    }
  });
}

if (camSearchClear) {
  camSearchClear.addEventListener('click', () => {
    if (camSearchInput) {
      camSearchInput.value = '';
      filterCameras();
      camSearchInput.focus();
    }
  });
}

// Department Checkbox listeners
document.querySelectorAll('.dept-checkbox').forEach(cb => {
  cb.addEventListener('change', filterCameras);
});

// ==============================================================================
// SECTION 65B EVIDENCE CERTIFICATE MODAL
// ==============================================================================
const certModal = document.getElementById('cert-modal');
const closeCertBtn = document.getElementById('close-cert-btn');
const exportCertBtn = document.getElementById('export-cert-btn');

exportCertBtn.addEventListener('click', async () => {
  const plate = document.getElementById('route-plate-input').value.trim() || "GJ01AB1234";
  exportCertBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin mr-1"></i> Generating Dossier...`;

  try {
    const res = await fetch(`${API_BASE}/forensics/certificate/${plate}`);
    if (!res.ok) throw new Error("Failed to fetch certificate");
    const cert = await res.json();

    document.getElementById('cert-id-badge').textContent = cert.certificate_id;
    document.getElementById('cert-master-hash').textContent = cert.overall_dossier_sha256;
    document.getElementById('cert-statutory-text').textContent = cert.statutory_declaration;
    document.getElementById('cert-sighting-count').textContent = `${cert.total_detections_certified} Certified Sightings`;
    document.getElementById('cert-print-link').href = `${API_BASE}/forensics/certificate/${plate}/print`;

    const tbody = document.getElementById('cert-table-body');
    tbody.innerHTML = '';
    cert.evidence_chain.forEach((item, idx) => {
      const tr = document.createElement('tr');
      tr.className = 'hover:bg-gray-850';
      tr.innerHTML = `
        <td class="p-2 text-center text-gray-500">${idx + 1}</td>
        <td class="p-2">
          <div class="font-bold text-gray-200">${item.camera_id}</div>
          <div class="text-[10px] text-gray-400">${item.location_name}, ${item.city}</div>
        </td>
        <td class="p-2 font-mono text-[10px] text-gray-300">
          ${new Date(item.detected_at).toLocaleString()}<br>
          <span class="text-cyan-400">PTS: ${item.pts_ms}ms</span>
        </td>
        <td class="p-2 font-mono text-[10px] text-cyan-300 truncate max-w-[200px]" title="${item.snapshot_sha256}">
          ${item.snapshot_sha256.substring(0, 24)}...
        </td>
        <td class="p-2 text-center font-mono text-emerald-400">
          ${(item.confidence * 100).toFixed(1)}%
        </td>
      `;
      tbody.appendChild(tr);
    });

    certModal.classList.remove('hidden');
  } catch (err) {
    alert("Error generating Section 65B Certificate: " + err.message);
  } finally {
    exportCertBtn.innerHTML = `<i class="fa-solid fa-stamp text-amber-400"></i><span>Generate Section 65B Evidence Dossier</span>`;
  }
});

closeCertBtn.addEventListener('click', () => certModal.classList.add('hidden'));

// ==============================================================================
// CAMERA HEALTH DIAGNOSTICS MODAL (Computer Vision Quality Control)
// ==============================================================================
const healthModal = document.getElementById('health-modal');
const closeHealthBtn = document.getElementById('close-health-btn');
const toggleHealthBtn = document.getElementById('toggle-health-btn');

if (toggleHealthBtn) {
  toggleHealthBtn.addEventListener('click', async () => {
    toggleHealthBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin mr-1"></i> Running Diagnostics...`;
    try {
      const res = await fetch(`${API_BASE}/cameras/health-diagnostics`);
      if (!res.ok) throw new Error("Diagnostics API unreachable");
      const diagnostics = await res.json();

      let onlineCount = 0;
      let degradedCount = 0;
      let offlineCount = 0;

      const tbody = document.getElementById('health-table-body');
      if (tbody) tbody.innerHTML = '';

      diagnostics.forEach(diag => {
        if (diag.status === 'ONLINE') onlineCount++;
        else if (diag.status === 'OFFLINE') offlineCount++;
        else degradedCount++;

        let statusBadge = '';
        if (diag.status === 'ONLINE') statusBadge = '<span class="bg-emerald-900/60 text-emerald-300 border border-emerald-700 px-1.5 py-0.5 rounded text-[10px] font-mono">ONLINE</span>';
        else if (diag.status === 'OFFLINE') statusBadge = '<span class="bg-red-900/80 text-red-300 border border-red-700 px-1.5 py-0.5 rounded text-[10px] font-mono">OFFLINE</span>';
        else statusBadge = '<span class="bg-amber-900/80 text-amber-300 border border-amber-700 px-1.5 py-0.5 rounded text-[10px] font-mono">DEGRADED</span>';

        if (tbody) {
          const tr = document.createElement('tr');
          tr.className = 'hover:bg-gray-850';
          tr.innerHTML = `
            <td class="p-2 font-bold text-gray-200">${diag.camera_id}</td>
            <td class="p-2 text-gray-300">${diag.location_name}</td>
            <td class="p-2">${statusBadge}</td>
            <td class="p-2 font-mono text-[11px] ${diag.laplacian_variance < 95 ? 'text-amber-400 font-bold' : 'text-gray-400'}">${diag.laplacian_variance}</td>
            <td class="p-2 font-mono text-[11px] ${diag.mean_luminance < 18 ? 'text-red-400 font-bold' : 'text-gray-400'}">${diag.mean_luminance}</td>
            <td class="p-2 text-[10px] text-gray-400">${diag.recommendation}</td>
          `;
          tbody.appendChild(tr);
        }
      });

      const elTotal = document.getElementById('health-stat-total');
      if (elTotal) elTotal.textContent = diagnostics.length;
      const elOnline = document.getElementById('health-stat-online');
      if (elOnline) elOnline.textContent = onlineCount;
      const elDegraded = document.getElementById('health-stat-degraded');
      if (elDegraded) elDegraded.textContent = degradedCount;
      const elOffline = document.getElementById('health-stat-offline');
      if (elOffline) elOffline.textContent = offlineCount;

      if (healthModal) healthModal.classList.remove('hidden');
    } catch (err) {
      alert("Failed to load camera health diagnostics: " + err.message);
    } finally {
      toggleHealthBtn.innerHTML = `<i class="fa-solid fa-heart-pulse"></i><span>Camera Health Diagnostics (CV)</span>`;
    }
  });
}

if (closeHealthBtn && healthModal) {
  closeHealthBtn.addEventListener('click', () => healthModal.classList.add('hidden'));
}

// ==============================================================================
// RESPONSIVE WORKSPACE & DRAWER CONTROLS
// ==============================================================================
const leftSidebar = document.getElementById('left-sidebar');
const rightSidebar = document.getElementById('right-sidebar');
const sidebarBackdrop = document.getElementById('sidebar-backdrop');
const routeHudCard = document.getElementById('route-hud-card');
const routeHudBody = document.getElementById('route-hud-body');
const minimizeHudBtn = document.getElementById('minimize-hud-btn');
const minimizeHudIcon = document.getElementById('minimize-hud-icon');
const headerAlertBadge = document.getElementById('header-alert-badge');

let unreadAlertCount = 0;

function invalidateMapSmoothly() {
  setTimeout(() => {
    map.invalidateSize({ animate: true });
  }, 320);
}

// Left Sidebar Toggle
function toggleLeftSidebar(open) {
  const isMobile = window.innerWidth < 1024;
  if (isMobile) {
    if (open === undefined) {
      leftSidebar.classList.toggle('-translate-x-full');
    } else if (open) {
      leftSidebar.classList.remove('-translate-x-full');
    } else {
      leftSidebar.classList.add('-translate-x-full');
    }
    const isOpen = !leftSidebar.classList.contains('-translate-x-full');
    sidebarBackdrop.classList.toggle('hidden', !isOpen && rightSidebar.classList.contains('translate-x-full'));
  } else {
    leftSidebar.classList.toggle('sidebar-desktop-collapsed-left');
  }
  invalidateMapSmoothly();
}

// Right Sidebar Toggle
function toggleRightSidebar(open) {
  const isMobile = window.innerWidth < 1024;
  if (isMobile) {
    if (open === undefined) {
      rightSidebar.classList.toggle('translate-x-full');
    } else if (open) {
      rightSidebar.classList.remove('translate-x-full');
    } else {
      rightSidebar.classList.add('translate-x-full');
    }
    const isOpen = !rightSidebar.classList.contains('translate-x-full');
    sidebarBackdrop.classList.toggle('hidden', !isOpen && leftSidebar.classList.contains('-translate-x-full'));
  } else {
    rightSidebar.classList.toggle('sidebar-desktop-collapsed-right');
  }
  
  // Clear alert badge on open
  unreadAlertCount = 0;
  if (headerAlertBadge) {
    headerAlertBadge.classList.add('hidden');
    headerAlertBadge.textContent = '0';
  }

  invalidateMapSmoothly();
}

function closeAllDrawers() {
  if (leftSidebar) leftSidebar.classList.add('-translate-x-full');
  if (rightSidebar) rightSidebar.classList.add('translate-x-full');
  if (sidebarBackdrop) sidebarBackdrop.classList.add('hidden');
  invalidateMapSmoothly();
}

document.getElementById('btn-toggle-left')?.addEventListener('click', () => toggleLeftSidebar());
document.getElementById('close-left-sidebar')?.addEventListener('click', () => toggleLeftSidebar(false));

document.getElementById('btn-toggle-right')?.addEventListener('click', () => toggleRightSidebar());
document.getElementById('close-right-sidebar')?.addEventListener('click', () => toggleRightSidebar(false));

sidebarBackdrop?.addEventListener('click', closeAllDrawers);

// Route HUD Toggle & Minimize
document.getElementById('btn-toggle-hud')?.addEventListener('click', () => {
  if (routeHudCard) {
    routeHudCard.classList.toggle('hidden');
    if (!routeHudCard.classList.contains('hidden')) {
      routeHudCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }
});

minimizeHudBtn?.addEventListener('click', () => {
  if (routeHudBody) {
    const isHidden = routeHudBody.classList.toggle('hidden');
    if (minimizeHudIcon) {
      minimizeHudIcon.className = isHidden ? 'fa-solid fa-chevron-down' : 'fa-solid fa-chevron-up';
    }
  }
});

// Full Map Mode (Hide/Restore sidebars)
document.getElementById('btn-full-map')?.addEventListener('click', () => {
  const isMobile = window.innerWidth < 1024;
  if (isMobile) {
    closeAllDrawers();
    if (routeHudCard) routeHudCard.classList.add('hidden');
  } else {
    const leftCollapsed = leftSidebar.classList.contains('sidebar-desktop-collapsed-left');
    const rightCollapsed = rightSidebar.classList.contains('sidebar-desktop-collapsed-right');
    if (!leftCollapsed || !rightCollapsed) {
      leftSidebar.classList.add('sidebar-desktop-collapsed-left');
      rightSidebar.classList.add('sidebar-desktop-collapsed-right');
    } else {
      leftSidebar.classList.remove('sidebar-desktop-collapsed-left');
      rightSidebar.classList.remove('sidebar-desktop-collapsed-right');
    }
  }
  invalidateMapSmoothly();
});

// Keyboard Accessibility Shortcuts
window.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closeAllDrawers();
    document.getElementById('stream-modal')?.classList.add('hidden');
    document.getElementById('cert-modal')?.classList.add('hidden');
    document.getElementById('health-modal')?.classList.add('hidden');
  } else if (e.key === 'f' || e.key === 'F') {
    if (!['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) {
      document.getElementById('btn-full-map')?.click();
    }
  }
});

// Window resize handler
window.addEventListener('resize', () => {
  invalidateMapSmoothly();
});

// Initial boot
loadCameras();
connectAlertWebSocket();
