# ruff: noqa: E501
"""Self-contained Three.js 3D Visualizer and Synthetic Data Studio template."""

THREEJS_VIEWER_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>PadelKit 3D Studio</title>
  <style>
    :root {
      --bg: #0b0f19;
      --panel: rgba(15, 23, 42, 0.88);
      --border: rgba(148, 163, 184, 0.22);
      --accent: #38bdf8;
      --accent-2: #22c55e;
      --text: #f8fafc;
      --muted: #94a3b8;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      overflow: hidden;
      width: 100vw;
      height: 100vh;
      user-select: none;
    }
    #canvas-container {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
    }
    .hud-top {
      position: absolute;
      top: 14px;
      left: 14px;
      right: 14px;
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      pointer-events: none;
      gap: 12px;
      z-index: 10;
    }
    .card {
      background: var(--panel);
      backdrop-filter: blur(14px);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 12px 16px;
      pointer-events: auto;
      box-shadow: 0 12px 32px rgba(0, 0, 0, 0.5);
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
      font-weight: 700;
      font-size: 15px;
      letter-spacing: -0.01em;
    }
    .badge {
      font-size: 11px;
      font-weight: 600;
      padding: 2px 8px;
      border-radius: 999px;
      background: rgba(56, 189, 248, 0.16);
      color: var(--accent);
      border: 1px solid rgba(56, 189, 248, 0.35);
    }
    .badge.live {
      background: rgba(34, 197, 94, 0.18);
      color: #4ade80;
      border-color: rgba(34, 197, 94, 0.4);
    }
    .scoreboard {
      margin-top: 8px;
      font-family: "JetBrains Mono", ui-monospace, monospace;
      font-size: 13px;
      color: #e2e8f0;
      display: flex;
      gap: 12px;
      align-items: center;
      flex-wrap: wrap;
    }
    .event-pill {
      font-size: 11px;
      padding: 2px 8px;
      border-radius: 6px;
      background: rgba(245, 158, 11, 0.2);
      color: #fbbf24;
      border: 1px solid rgba(245, 158, 11, 0.4);
      font-weight: 600;
    }
    .telemetry-bar {
      margin-top: 10px;
      padding-top: 9px;
      border-top: 1px solid var(--border);
      display: grid;
      grid-template-columns: repeat(3, minmax(88px, auto));
      gap: 12px;
      font-family: "JetBrains Mono", ui-monospace, monospace;
    }
    .stat-item {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .stat-label {
      font-size: 10px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .stat-value {
      font-size: 13px;
      font-weight: 700;
      color: #38bdf8;
    }
    .controls-grid {
      display: grid;
      grid-template-columns: repeat(2, auto);
      gap: 8px 12px;
      align-items: center;
      font-size: 12px;
    }
    label { color: var(--muted); font-weight: 500; }
    select, button, input[type="file"]::file-selector-button {
      background: rgba(30, 41, 59, 0.9);
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 7px;
      padding: 5px 10px;
      font-size: 12px;
      cursor: pointer;
      transition: border-color 0.15s, background 0.15s;
    }
    select:hover, button:hover {
      border-color: var(--accent);
      background: rgba(51, 65, 85, 0.9);
    }
    button.primary {
      background: rgba(56, 189, 248, 0.2);
      border-color: rgba(56, 189, 248, 0.5);
      color: #e0f2fe;
      font-weight: 600;
    }
    .hud-bottom {
      position: absolute;
      bottom: 14px;
      left: 14px;
      right: 14px;
      z-index: 10;
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .scrubber {
      flex: 1;
      accent-color: var(--accent);
      cursor: pointer;
    }
    .time-readout {
      font-family: ui-monospace, monospace;
      font-size: 12px;
      color: var(--muted);
      min-width: 115px;
      text-align: right;
    }
    #landmarks-overlay {
      position: absolute;
      inset: 0;
      pointer-events: none;
      z-index: 5;
    }
    .lm-tag {
      position: absolute;
      transform: translate(-50%, -50%);
      background: rgba(15, 23, 42, 0.85);
      border: 1px solid #38bdf8;
      color: #38bdf8;
      font-family: ui-monospace, monospace;
      font-size: 10px;
      padding: 1px 5px;
      border-radius: 999px;
      white-space: nowrap;
    }
    .seg-legend {
      display: none;
      margin-top: 8px;
      padding-top: 8px;
      border-top: 1px solid var(--border);
      font-size: 11px;
      gap: 8px;
      flex-wrap: wrap;
    }
    .seg-swatch {
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
    .seg-dot {
      width: 9px;
      height: 9px;
      border-radius: 2px;
      display: inline-block;
    }
  </style>
  <script type="importmap">
    {
      "imports": {
        "three": "https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js",
        "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/"
      }
    }
  </script>
</head>
<body>
  <div id="canvas-container"></div>
  <div id="landmarks-overlay"></div>

  <div class="hud-top">
    <div class="card">
      <div class="brand">
        <span>🎾 PadelKit 3D Studio</span>
        <span id="mode-badge" class="badge">9D PHYSICS / REPLAY</span>
      </div>
      <div class="scoreboard">
        <span id="score-display">SCORE: 0-0 | 0-0</span>
        <span id="event-display" class="event-pill">READY</span>
      </div>
      <div class="telemetry-bar">
        <div class="stat-item">
          <span class="stat-label">Ball Speed</span>
          <span id="speed-readout" class="stat-value">0.0 km/h</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Spin (9D)</span>
          <span id="spin-readout" class="stat-value">0 RPM</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Height (Z)</span>
          <span id="height-readout" class="stat-value">0.00 m</span>
        </div>
      </div>
      <div id="seg-legend" class="seg-legend">
        <span class="seg-swatch"><i class="seg-dot" style="background:#1d4ed8"></i>Turf</span>
        <span class="seg-swatch"><i class="seg-dot" style="background:#ffffff"></i>Lines</span>
        <span class="seg-swatch"><i class="seg-dot" style="background:#06b6d4"></i>Glass</span>
        <span class="seg-swatch"><i class="seg-dot" style="background:#64748b"></i>Mesh</span>
        <span class="seg-swatch"><i class="seg-dot" style="background:#a855f7"></i>Net</span>
        <span class="seg-swatch"><i class="seg-dot" style="background:#22c55e"></i>Team A</span>
        <span class="seg-swatch"><i class="seg-dot" style="background:#ef4444"></i>Team B</span>
        <span class="seg-swatch"><i class="seg-dot" style="background:#eab308"></i>Ball</span>
      </div>
    </div>

    <div class="card">
      <div class="controls-grid">
        <label for="camera-select">Camera View</label>
        <select id="camera-select">
          <option value="__orbit__">Free 3D Orbit Camera</option>
        </select>

        <label for="render-mode">Render Pass (CV)</label>
        <select id="render-mode">
          <option value="rgb">RGB Photorealistic</option>
          <option value="segmentation">Semantic Segmentation ID</option>
          <option value="depth">Normalized Depth Map</option>
        </select>

        <label for="landmarks-toggle">17 Court Landmarks</label>
        <select id="landmarks-toggle">
          <option value="on">Visible (2D/3D Keypoints)</option>
          <option value="off">Hidden</option>
        </select>

        <label for="csv-upload">Load Replay CSV</label>
        <input id="csv-upload" type="file" accept=".csv" style="font-size:11px; max-width:170px;" />

        <label for="snapshot-btn">Synthetic Frame</label>
        <button id="snapshot-btn" class="primary">Export PNG + GT</button>
      </div>
    </div>
  </div>

  <div class="hud-bottom card">
    <button id="play-btn" class="primary" style="min-width:74px;">Pause</button>
    <input id="timeline-slider" class="scrubber" type="range" min="0" max="100" value="0" step="1" />
    <select id="speed-select" title="Playback Speed">
      <option value="0.25">0.25x</option>
      <option value="0.5">0.5x</option>
      <option value="1.0" selected>1.0x</option>
      <option value="2.0">2.0x</option>
    </select>
    <span id="time-readout" class="time-readout">0.00s / 0.00s</span>
  </div>

  <script type="module">
    import * as THREE from "three";
    import { OrbitControls } from "three/addons/controls/OrbitControls.js";

    const CONFIG = __PADELKIT_CONFIG_JSON__;

    const container = document.getElementById("canvas-container");
    const lmOverlay = document.getElementById("landmarks-overlay");
    const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.15;
    container.appendChild(renderer.domElement);

    // PadelKit uses Z-up (X width, Y length, Z height)
    THREE.Object3D.DEFAULT_UP.set(0, 0, 1);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x090d16);
    scene.fog = new THREE.FogExp2(0x090d16, 0.011);

    // Orbit camera
    const orbitCam = new THREE.PerspectiveCamera(48, window.innerWidth / window.innerHeight, 0.1, 150);
    orbitCam.position.set(11.5, -16.8, 8.8);
    orbitCam.up.set(0, 0, 1);

    const controls = new OrbitControls(orbitCam, renderer.domElement);
    controls.target.set(0, 0, 0.85);
    controls.enableDamping = true;
    controls.maxPolarAngle = Math.PI * 0.495;
    controls.update();

    let activeCamera = orbitCam;
    let activePresetCameraCfg = null;
    const presetThreeCameras = {};

    // Material registry for Semantic Segmentation & Depth switching
    const trackedMeshes = [];
    const SEG_COLORS = {
      turf: 0x1d4ed8,
      line: 0xffffff,
      glass: 0x06b6d4,
      mesh: 0x64748b,
      structure: 0x334155,
      net: 0xa855f7,
      teamA: 0x22c55e,
      teamB: 0xef4444,
      racket: 0xf97316,
      ball: 0xeab308,
    };

    const depthMaterial = new THREE.MeshDepthMaterial({ depthPacking: THREE.BasicDepthPacking });

    function registerMesh(mesh, segCategory) {
      mesh.userData.rgbMaterial = mesh.material;
      mesh.userData.segMaterial = new THREE.MeshBasicMaterial({
        color: SEG_COLORS[segCategory] || 0x94a3b8,
        side: THREE.DoubleSide,
      });
      trackedMeshes.push(mesh);
      return mesh;
    }

    // ------------------------------------------------------------------ //
    // Lighting (Arena environment + 4 FIP LED Floodlights)
    // ------------------------------------------------------------------ //
    const hemiLight = new THREE.HemisphereLight(0xe0f2fe, 0x0f172a, 0.9);
    hemiLight.position.set(0, 0, 16);
    scene.add(hemiLight);

    const dims = CONFIG.court.dimensions;
    const W = dims.width;
    const L = dims.length;
    const hw = W / 2;
    const hl = L / 2;

    const floodlightPositions = [
      [-hw - 0.12, -5.0, 6.2],
      [ hw + 0.12, -5.0, 6.2],
      [-hw - 0.12,  5.0, 6.2],
      [ hw + 0.12,  5.0, 6.2],
    ];
    floodlightPositions.forEach(([lx, ly, lz], idx) => {
      const spot = new THREE.DirectionalLight(0xf8fafc, 0.78);
      spot.position.set(lx, ly, lz);
      if (idx < 2) {
        spot.castShadow = true;
        spot.shadow.mapSize.set(2048, 2048);
        spot.shadow.camera.near = 1;
        spot.shadow.camera.far = 30;
        const d = 12.5;
        spot.shadow.camera.left = -d;
        spot.shadow.camera.right = d;
        spot.shadow.camera.top = d;
        spot.shadow.camera.bottom = -d;
        spot.shadow.bias = -0.0005;
      }
      scene.add(spot);
    });

    // ------------------------------------------------------------------ //
    // High-Realism FIP Padel Court Builder
    // ------------------------------------------------------------------ //

    // 1. Surrounding arena floor + outer run-off carpet
    const arenaFloorGeo = new THREE.PlaneGeometry(52, 64);
    const arenaFloorMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.92 });
    const arenaFloor = new THREE.Mesh(arenaFloorGeo, arenaFloorMat);
    arenaFloor.position.z = -0.02;
    arenaFloor.receiveShadow = true;
    scene.add(arenaFloor);

    const plinthGeo = new THREE.BoxGeometry(W + 0.36, L + 0.36, 0.04);
    const plinthMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.6, metalness: 0.2 });
    const plinthMesh = registerMesh(new THREE.Mesh(plinthGeo, plinthMat), "structure");
    plinthMesh.position.z = -0.02;
    plinthMesh.receiveShadow = true;
    scene.add(plinthMesh);

    // 2. Procedural Silica-Sand Fibrillated Turf Texture with subtle weave stripes
    function createTurfTexture(colorName) {
      const canvas = document.createElement("canvas");
      canvas.width = 512;
      canvas.height = 512;
      const ctx = canvas.getContext("2d");
      const baseColors = {
        blue: "#0d4b82",
        green: "#1b5e20",
        black: "#182232",
        terracotta: "#9a3412",
      };
      ctx.fillStyle = baseColors[colorName] || baseColors.blue;
      ctx.fillRect(0, 0, 512, 512);

      // Subtle turf roll stripes
      ctx.fillStyle = "rgba(255,255,255,0.022)";
      ctx.fillRect(0, 0, 256, 512);

      // Silica sand and curled fiber grain
      for (let i = 0; i < 32000; i++) {
        const x = Math.random() * 512;
        const y = Math.random() * 512;
        ctx.fillStyle = Math.random() > 0.48 ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.065)";
        ctx.fillRect(x, y, 2, 2);
      }
      const tex = new THREE.CanvasTexture(canvas);
      tex.wrapS = THREE.RepeatWrapping;
      tex.wrapT = THREE.RepeatWrapping;
      tex.repeat.set(6, 12);
      return tex;
    }

    const turfGeo = new THREE.PlaneGeometry(W, L);
    const turfMat = new THREE.MeshStandardMaterial({
      map: createTurfTexture(CONFIG.court.turf_color || "blue"),
      roughness: 0.76,
      metalness: 0.04,
    });
    const turfMesh = registerMesh(new THREE.Mesh(turfGeo, turfMat), "turf");
    turfMesh.receiveShadow = true;
    scene.add(turfMesh);

    // 3. Regulation 5cm White Court Lines
    const lineMat = new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 0.42 });
    const lineW = 0.05;
    const svcY = hl - dims.service_line_distance_from_back;

    function addCourtLine(x, y, width, length) {
      const m = registerMesh(
        new THREE.Mesh(new THREE.PlaneGeometry(width, length), lineMat),
        "line"
      );
      m.position.set(x, y, 0.0025);
      m.receiveShadow = true;
      scene.add(m);
    }
    addCourtLine(0, -hl, W, lineW);
    addCourtLine(0,  hl, W, lineW);
    addCourtLine(-hw, 0, lineW, L);
    addCourtLine( hw, 0, lineW, L);
    addCourtLine(0, -svcY, W, lineW);
    addCourtLine(0,  svcY, W, lineW);
    addCourtLine(0, 0, lineW, svcY * 2 + 0.2);

    // 4. Tempered Glass Panels, Electro-Welded Metallic Fence & Structural Pillars
    const glassMat = new THREE.MeshPhysicalMaterial({
      color: 0xe0f2fe,
      transparent: true,
      opacity: 0.28,
      roughness: 0.05,
      metalness: 0.08,
      reflectivity: 0.95,
      clearcoat: 1.0,
      clearcoatRoughness: 0.05,
      side: THREE.DoubleSide,
    });
    const pillarMat = new THREE.MeshStandardMaterial({
      color: 0x1e293b,
      metalness: 0.78,
      roughness: 0.26,
    });
    const clampMat = new THREE.MeshStandardMaterial({
      color: 0xcbd5e1,
      metalness: 0.9,
      roughness: 0.2,
    });

    function createMetallicMeshMaterial() {
      const c = document.createElement("canvas");
      c.width = 128;
      c.height = 128;
      const ctx = c.getContext("2d");
      ctx.clearRect(0, 0, 128, 128);
      ctx.strokeStyle = "#94a3b8";
      ctx.lineWidth = 7;
      ctx.strokeRect(0, 0, 128, 128);
      ctx.strokeRect(64, 0, 64, 128);
      ctx.strokeRect(0, 64, 128, 64);
      const tex = new THREE.CanvasTexture(c);
      tex.wrapS = THREE.RepeatWrapping;
      tex.wrapT = THREE.RepeatWrapping;
      tex.repeat.set(14, 7);
      return new THREE.MeshStandardMaterial({
        map: tex,
        transparent: true,
        alphaTest: 0.15,
        side: THREE.DoubleSide,
        metalness: 0.82,
        roughness: 0.32,
      });
    }
    const wireMeshMat = createMetallicMeshMaterial();

    function addWallPanel(x, y, z, width, depth, height, isGlass) {
      const geo = new THREE.BoxGeometry(width, depth, height);
      const mat = isGlass ? glassMat : wireMeshMat;
      const mesh = registerMesh(new THREE.Mesh(geo, mat), isGlass ? "glass" : "mesh");
      mesh.position.set(x, y, z + height / 2);
      scene.add(mesh);

      // Top & bottom horizontal metallic rails for each panel
      const railH = 0.045;
      const topRail = registerMesh(
        new THREE.Mesh(new THREE.BoxGeometry(width + 0.02, depth + 0.03, railH), pillarMat),
        "structure"
      );
      topRail.position.set(x, y, z + height - railH / 2);
      scene.add(topRail);

      if (z === 0) {
        const botRail = registerMesh(
          new THREE.Mesh(new THREE.BoxGeometry(width + 0.02, depth + 0.04, railH), pillarMat),
          "structure"
        );
        botRail.position.set(x, y, railH / 2);
        scene.add(botRail);
      }

      // Brushed aluminum glass clamps on tempered glass panels
      if (isGlass) {
        [0.6, height - 0.6].forEach((cz) => {
          const clamp = registerMesh(
            new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.08, 0.05), clampMat),
            "structure"
          );
          clamp.position.set(x - width * 0.46, y, z + cz);
          scene.add(clamp);
        });
      }
    }

    function addStructuralPillar(x, y, height) {
      const post = registerMesh(
        new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.08, height), pillarMat),
        "structure"
      );
      post.position.set(x, y, height / 2);
      post.castShadow = true;
      scene.add(post);
    }

    const backH = dims.back_wall_height;
    const sideH = dims.side_wall_height;
    const glassThick = 0.016;

    // Back walls (5 panels of 2m width x 3m glass + 1m top mesh)
    for (let i = 0; i < 5; i++) {
      const px = -hw + 1.0 + i * 2.0;
      addWallPanel(px, -hl, 0, 1.98, glassThick, 3.0, true);
      addWallPanel(px, -hl, 3.0, 1.98, glassThick, backH - 3.0, false);
      addWallPanel(px,  hl, 0, 1.98, glassThick, 3.0, true);
      addWallPanel(px,  hl, 3.0, 1.98, glassThick, backH - 3.0, false);
    }
    for (let i = 0; i <= 5; i++) {
      const px = -hw + i * 2.0;
      addStructuralPillar(px, -hl, backH);
      addStructuralPillar(px,  hl, backH);
    }

    // Side walls with central entry doorway gap near the net
    const sideSegments = [
      { y: -hl + 1.0, len: 2.0, glassH: 3.0, meshH: 1.0, totalH: 4.0 },
      { y: -hl + 3.0, len: 2.0, glassH: 2.0, meshH: 1.0, totalH: 3.0 },
      { y: -hl + 5.0, len: 2.0, glassH: 0.0, meshH: sideH, totalH: sideH },
      { y: -hl + 7.0, len: 2.0, glassH: 0.0, meshH: sideH, totalH: sideH },
      { y: -hl + 8.5, len: 1.0, glassH: 0.0, meshH: sideH, totalH: sideH },
      // Central 2m doorway opening at y in [-1.0, 1.0]
      { y:  hl - 8.5, len: 1.0, glassH: 0.0, meshH: sideH, totalH: sideH },
      { y:  hl - 7.0, len: 2.0, glassH: 0.0, meshH: sideH, totalH: sideH },
      { y:  hl - 5.0, len: 2.0, glassH: 0.0, meshH: sideH, totalH: sideH },
      { y:  hl - 3.0, len: 2.0, glassH: 2.0, meshH: 1.0, totalH: 3.0 },
      { y:  hl - 1.0, len: 2.0, glassH: 3.0, meshH: 1.0, totalH: 4.0 },
    ];
    sideSegments.forEach((seg) => {
      [-hw, hw].forEach((sx) => {
        if (seg.glassH > 0) {
          addWallPanel(sx, seg.y, 0, glassThick, seg.len - 0.02, seg.glassH, true);
        }
        if (seg.meshH > 0) {
          addWallPanel(sx, seg.y, seg.glassH, glassThick, seg.len - 0.02, seg.meshH, false);
        }
        addStructuralPillar(sx, seg.y - seg.len / 2, seg.totalH);
        addStructuralPillar(sx, seg.y + seg.len / 2, seg.totalH);
      });
    });

    // 4b. Curved FIP LED Floodlight Masts & Luminaires
    const ledEmitMat = new THREE.MeshStandardMaterial({
      color: 0xffffff,
      emissive: 0xe0f2fe,
      emissiveIntensity: 2.5,
      roughness: 0.1,
    });
    floodlightPositions.forEach(([lx, ly, lz]) => {
      const signX = lx < 0 ? -1 : 1;
      const mast = registerMesh(
        new THREE.Mesh(new THREE.CylinderGeometry(0.055, 0.065, lz, 12), pillarMat),
        "structure"
      );
      mast.rotation.x = Math.PI / 2;
      mast.position.set(lx, ly, lz / 2);
      scene.add(mast);

      // Curved overhang arm + LED panel
      const arm = registerMesh(
        new THREE.Mesh(new THREE.BoxGeometry(0.85, 0.08, 0.08), pillarMat),
        "structure"
      );
      arm.position.set(lx - signX * 0.4, ly, lz);
      scene.add(arm);

      const lamp = registerMesh(
        new THREE.Mesh(new THREE.BoxGeometry(0.45, 0.75, 0.05), ledEmitMat),
        "structure"
      );
      lamp.position.set(lx - signX * 0.78, ly, lz - 0.04);
      lamp.rotation.y = signX * 0.35;
      scene.add(lamp);
    });

    // 5. Woven Net with Regulation Catenary Sag, Net Posts & Center Strap
    function createNetAlphaTexture() {
      const c = document.createElement("canvas");
      c.width = 64;
      c.height = 64;
      const ctx = c.getContext("2d");
      ctx.clearRect(0, 0, 64, 64);
      ctx.strokeStyle = "#1e293b";
      ctx.lineWidth = 8;
      ctx.strokeRect(0, 0, 64, 64);
      const tex = new THREE.CanvasTexture(c);
      tex.wrapS = THREE.RepeatWrapping;
      tex.wrapT = THREE.RepeatWrapping;
      tex.repeat.set(95, 9);
      return tex;
    }

    const netSegments = 36;
    const netGeo = new THREE.PlaneGeometry(W - 0.12, 0.92, netSegments, 6);
    const posAttr = netGeo.attributes.position;
    for (let i = 0; i < posAttr.count; i++) {
      const vx = posAttr.getX(i);
      const vy = posAttr.getY(i);
      const normX = vx / hw;
      const topZ = dims.net_height_center + (dims.net_height_posts - dims.net_height_center) * (normX * normX);
      const frac = (vy + 0.46) / 0.92;
      posAttr.setY(i, 0);
      posAttr.setZ(i, frac * topZ);
    }
    netGeo.computeVertexNormals();
    const netMat = new THREE.MeshStandardMaterial({
      map: createNetAlphaTexture(),
      transparent: true,
      alphaTest: 0.1,
      roughness: 0.85,
      side: THREE.DoubleSide,
    });
    const netMesh = registerMesh(new THREE.Mesh(netGeo, netMat), "net");
    netMesh.castShadow = true;
    scene.add(netMesh);

    // Net posts & center strap (faja central)
    [-hw + 0.05, hw - 0.05].forEach((nx) => {
      const netPost = registerMesh(
        new THREE.Mesh(new THREE.CylinderGeometry(0.045, 0.045, 0.96, 16), pillarMat),
        "net"
      );
      netPost.rotation.x = Math.PI / 2;
      netPost.position.set(nx, 0, 0.48);
      scene.add(netPost);
    });
    const centerStrap = registerMesh(
      new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.015, dims.net_height_center), lineMat),
      "net"
    );
    centerStrap.position.set(0, 0, dims.net_height_center / 2);
    scene.add(centerStrap);

    // White top net tape (faja superior)
    const tapeCurvePts = [];
    for (let i = 0; i <= netSegments; i++) {
      const u = (i / netSegments) * 2 - 1;
      const z = dims.net_height_center + (dims.net_height_posts - dims.net_height_center) * (u * u);
      tapeCurvePts.push(new THREE.Vector3(u * (hw - 0.05), 0, z));
    }
    const tapeCurve = new THREE.CatmullRomCurve3(tapeCurvePts);
    const tapeGeo = new THREE.TubeGeometry(tapeCurve, 36, 0.025, 10, false);
    const tapeMesh = registerMesh(new THREE.Mesh(tapeGeo, lineMat), "net");
    scene.add(tapeMesh);

    // ------------------------------------------------------------------ //
    // 3D Textured Padel Ball + Spin Seam + Hawk-Eye Bounce Ring Markers
    // ------------------------------------------------------------------ //
    function createPadelBallTexture() {
      const c = document.createElement("canvas");
      c.width = 256;
      c.height = 128;
      const ctx = c.getContext("2d");
      ctx.fillStyle = "#d9f99d";
      ctx.fillRect(0, 0, 256, 128);
      // Curved white rubber seam
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 8;
      ctx.beginPath();
      for (let x = 0; x <= 256; x += 4) {
        const y = 64 + Math.sin((x / 256) * Math.PI * 2) * 34;
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
      return new THREE.CanvasTexture(c);
    }

    const ballGeo = new THREE.SphereGeometry(0.0335, 28, 28);
    const ballMat = new THREE.MeshStandardMaterial({
      map: createPadelBallTexture(),
      emissive: 0x84cc16,
      emissiveIntensity: 0.28,
      roughness: 0.55,
    });
    const ballMesh = registerMesh(new THREE.Mesh(ballGeo, ballMat), "ball");
    ballMesh.castShadow = true;
    scene.add(ballMesh);

    // Subtle ground shadow / vertical drop indicator beneath ball
    const ballShadowGeo = new THREE.RingGeometry(0.02, 0.065, 24);
    const ballShadowMat = new THREE.MeshBasicMaterial({
      color: 0xbef264,
      transparent: true,
      opacity: 0.45,
      side: THREE.DoubleSide,
    });
    const ballGroundRing = new THREE.Mesh(ballShadowGeo, ballShadowMat);
    ballGroundRing.position.z = 0.004;
    scene.add(ballGroundRing);

    // Bounce impact ring markers pool
    const bounceRingGeo = new THREE.RingGeometry(0.06, 0.14, 28);
    const bounceRings = [];
    for (let i = 0; i < 6; i++) {
      const mat = new THREE.MeshBasicMaterial({
        color: 0x38bdf8,
        transparent: true,
        opacity: 0.0,
        side: THREE.DoubleSide,
      });
      const rMesh = new THREE.Mesh(bounceRingGeo, mat);
      scene.add(rMesh);
      bounceRings.push({ mesh: rMesh, opacity: 0.0 });
    }
    let nextRingIdx = 0;

    function spawnBounceMarker(bx, by, bz, eventStr) {
      const item = bounceRings[nextRingIdx];
      nextRingIdx = (nextRingIdx + 1) % bounceRings.length;
      const isGlass = eventStr.includes("glass") || eventStr.includes("wall");
      item.mesh.material.color.setHex(
        eventStr.includes("sliding") ? 0xf59e0b : 0x38bdf8
      );
      item.mesh.rotation.set(0, 0, 0);
      if (isGlass && Math.abs(by) > hl - 0.4) {
        item.mesh.rotation.x = Math.PI / 2;
        item.mesh.position.set(bx, by > 0 ? hl - 0.02 : -hl + 0.02, bz);
      } else {
        item.mesh.position.set(bx, by, 0.005);
      }
      item.opacity = 0.95;
      item.mesh.material.opacity = 0.95;
    }

    const trailMax = 50;
    const trailPositions = new Float32Array(trailMax * 3);
    const trailGeo = new THREE.BufferGeometry();
    trailGeo.setAttribute("position", new THREE.BufferAttribute(trailPositions, 3));
    const trailMat = new THREE.LineBasicMaterial({ color: 0xd9f99d, transparent: true, opacity: 0.82 });
    const trailLine = new THREE.Line(trailGeo, trailMat);
    scene.add(trailLine);

    // ------------------------------------------------------------------ //
    // Articulated Athletic 3D Padel Players & Perforated Carbon Racket
    // ------------------------------------------------------------------ //
    function createPerforatedRacketTexture(accentHex) {
      const c = document.createElement("canvas");
      c.width = 256;
      c.height = 256;
      const ctx = c.getContext("2d");
      // Carbon weave background
      ctx.fillStyle = "#111827";
      ctx.fillRect(0, 0, 256, 256);
      ctx.strokeStyle = "#1f2937";
      ctx.lineWidth = 3;
      for (let i = -256; i < 512; i += 10) {
        ctx.beginPath();
        ctx.moveTo(i, 0);
        ctx.lineTo(i + 256, 256);
        ctx.stroke();
      }
      // Accent frame stripe
      ctx.strokeStyle = accentHex;
      ctx.lineWidth = 18;
      ctx.beginPath();
      ctx.arc(128, 128, 112, 0, Math.PI * 2);
      ctx.stroke();

      // 28 Aerodynamic perforated holes (punched dark centers with rim highlight)
      const holeRows = [-52, -26, 0, 26, 52];
      holeRows.forEach((dx, rIdx) => {
        const count = rIdx === 0 || rIdx === 4 ? 4 : 6;
        for (let k = 0; k < count; k++) {
          const dy = (k - (count - 1) / 2) * 26 - 10;
          ctx.fillStyle = "#030712";
          ctx.beginPath();
          ctx.arc(128 + dx, 128 + dy, 7.5, 0, Math.PI * 2);
          ctx.fill();
          ctx.strokeStyle = "rgba(148,163,184,0.35)";
          ctx.lineWidth = 1.5;
          ctx.stroke();
        }
      });
      return new THREE.CanvasTexture(c);
    }

    function createPadelRacketMesh(team) {
      const racketGroup = new THREE.Group();
      const gripMat = new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 0.7 });
      const frameMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, metalness: 0.4, roughness: 0.3 });
      const faceTex = createPerforatedRacketTexture(team === "A" ? "#38bdf8" : "#f43f5e");
      const faceMat = new THREE.MeshStandardMaterial({
        map: faceTex,
        metalness: 0.35,
        roughness: 0.3,
      });

      // White overgrip handle + butt cap
      const handle = registerMesh(
        new THREE.Mesh(new THREE.CylinderGeometry(0.015, 0.016, 0.14, 14), gripMat),
        "racket"
      );
      handle.rotation.x = Math.PI / 2;
      handle.position.z = 0.07;
      racketGroup.add(handle);

      // Throat bridge (puente de la pala)
      [-0.032, 0.032].forEach((bx) => {
        const strut = registerMesh(
          new THREE.Mesh(new THREE.CylinderGeometry(0.011, 0.012, 0.09, 10), frameMat),
          "racket"
        );
        strut.rotation.x = Math.PI / 2;
        strut.rotation.y = bx < 0 ? -0.32 : 0.32;
        strut.position.set(bx * 0.6, 0, 0.16);
        racketGroup.add(strut);
      });

      // Teardrop 38mm EVA + Carbon head
      const head = registerMesh(
        new THREE.Mesh(new THREE.CylinderGeometry(0.13, 0.115, 0.038, 28), faceMat),
        "racket"
      );
      head.scale.set(1.0, 1.0, 1.24);
      head.position.z = 0.31;
      head.castShadow = true;
      racketGroup.add(head);

      return racketGroup;
    }

    function createArticulatedPlayer(playerId, team) {
      const root = new THREE.Group();
      const segKey = team === "A" ? "teamA" : "teamB";
      const jerseyColor = team === "A" ? 0x0284c7 : 0xe11d48;
      const trimColor = team === "A" ? 0x38bdf8 : 0xfda4af;
      const shortsColor = team === "A" ? 0x0f172a : 0x1e293b;

      const skinMat = new THREE.MeshStandardMaterial({ color: 0xe8b48a, roughness: 0.55 });
      const jerseyMat = new THREE.MeshStandardMaterial({ color: jerseyColor, roughness: 0.45 });
      const trimMat = new THREE.MeshStandardMaterial({ color: trimColor, roughness: 0.4 });
      const shortsMat = new THREE.MeshStandardMaterial({ color: shortsColor, roughness: 0.55 });
      const hairMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.8 });
      const shoeMat = new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 0.4 });

      // Upper body group (allows forward athletic lean & torso rotation during swings)
      const upperBody = new THREE.Group();
      upperBody.position.set(0, 0, 0.88);
      root.add(upperBody);

      // Tapered athletic torso
      const torso = registerMesh(
        new THREE.Mesh(new THREE.CylinderGeometry(0.19, 0.15, 0.48, 16), jerseyMat),
        segKey
      );
      torso.rotation.x = Math.PI / 2;
      torso.scale.set(1.12, 1.0, 0.72);
      torso.position.z = 0.28;
      torso.castShadow = true;
      upperBody.add(torso);

      // Rounded shoulders / chest cap
      const chest = registerMesh(
        new THREE.Mesh(new THREE.CapsuleGeometry(0.14, 0.22, 8, 14), jerseyMat),
        segKey
      );
      chest.rotation.z = Math.PI / 2;
      chest.position.z = 0.48;
      upperBody.add(chest);

      // Neck & Head with sports cap/hair
      const neck = registerMesh(
        new THREE.Mesh(new THREE.CylinderGeometry(0.055, 0.06, 0.1, 12), skinMat),
        segKey
      );
      neck.rotation.x = Math.PI / 2;
      neck.position.z = 0.6;
      upperBody.add(neck);

      const head = registerMesh(
        new THREE.Mesh(new THREE.SphereGeometry(0.125, 18, 18), skinMat),
        segKey
      );
      head.scale.set(0.92, 1.0, 1.08);
      head.position.z = 0.74;
      head.castShadow = true;
      upperBody.add(head);

      const capCrown = registerMesh(
        new THREE.Mesh(
          new THREE.SphereGeometry(0.128, 16, 12, 0, Math.PI * 2, 0, Math.PI * 0.55),
          hairMat
        ),
        segKey
      );
      capCrown.rotation.x = Math.PI / 2;
      capCrown.position.z = 0.75;
      upperBody.add(capCrown);

      const visor = registerMesh(
        new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.11, 0.015), trimMat),
        segKey
      );
      visor.position.set(0, 0.11, 0.78);
      upperBody.add(visor);

      // Shorts / Pelvis
      const pelvis = registerMesh(
        new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.165, 0.22, 16), shortsMat),
        segKey
      );
      pelvis.rotation.x = Math.PI / 2;
      pelvis.scale.set(1.08, 1.0, 0.76);
      pelvis.position.z = 0.82;
      root.add(pelvis);

      // Articulated Legs (Hip -> Thigh -> Knee -> Calf -> Court Shoe)
      function buildLeg(sideSign) {
        const hipPivot = new THREE.Group();
        hipPivot.position.set(sideSign * 0.105, 0, 0.76);

        const thigh = registerMesh(
          new THREE.Mesh(new THREE.CapsuleGeometry(0.068, 0.26, 6, 12), shortsMat),
          segKey
        );
        thigh.rotation.x = Math.PI / 2;
        thigh.position.z = -0.16;
        thigh.castShadow = true;
        hipPivot.add(thigh);

        const kneePivot = new THREE.Group();
        kneePivot.position.set(0, 0, -0.34);
        hipPivot.add(kneePivot);

        const calf = registerMesh(
          new THREE.Mesh(new THREE.CapsuleGeometry(0.052, 0.28, 6, 12), skinMat),
          segKey
        );
        calf.rotation.x = Math.PI / 2;
        calf.position.z = -0.18;
        calf.castShadow = true;
        kneePivot.add(calf);

        const sock = registerMesh(
          new THREE.Mesh(new THREE.CylinderGeometry(0.054, 0.05, 0.12, 12), shoeMat),
          segKey
        );
        sock.rotation.x = Math.PI / 2;
        sock.position.z = -0.31;
        kneePivot.add(sock);

        const shoe = registerMesh(
          new THREE.Mesh(new THREE.BoxGeometry(0.11, 0.24, 0.075), shoeMat),
          segKey
        );
        shoe.position.set(0, 0.045, -0.38);
        shoe.castShadow = true;
        kneePivot.add(shoe);

        root.add(hipPivot);
        return { hipPivot, kneePivot };
      }

      const leftLeg = buildLeg(-1);
      const rightLeg = buildLeg(1);

      // Left non-dominant balance arm (Shoulder -> UpperArm -> Forearm)
      const leftShoulder = new THREE.Group();
      leftShoulder.position.set(-0.23, 0, 0.46);
      const leftUpperArm = registerMesh(
        new THREE.Mesh(new THREE.CapsuleGeometry(0.046, 0.22, 6, 12), skinMat),
        segKey
      );
      leftUpperArm.rotation.x = Math.PI / 2;
      leftUpperArm.position.set(-0.02, 0.06, -0.12);
      leftShoulder.add(leftUpperArm);

      const leftForearm = registerMesh(
        new THREE.Mesh(new THREE.CapsuleGeometry(0.04, 0.20, 6, 12), skinMat),
        segKey
      );
      leftForearm.rotation.x = Math.PI / 4;
      leftForearm.position.set(0.02, 0.20, -0.22);
      leftShoulder.add(leftForearm);
      upperBody.add(leftShoulder);

      // Right dominant hitting arm + Perforated Padel Racket
      const rightShoulder = new THREE.Group();
      rightShoulder.position.set(0.23, 0, 0.46);

      const rightUpperArm = registerMesh(
        new THREE.Mesh(new THREE.CapsuleGeometry(0.048, 0.22, 6, 12), skinMat),
        segKey
      );
      rightUpperArm.rotation.x = Math.PI / 3;
      rightUpperArm.position.set(0, 0.10, -0.10);
      rightShoulder.add(rightUpperArm);

      const rightElbow = new THREE.Group();
      rightElbow.position.set(0, 0.20, -0.18);
      rightShoulder.add(rightElbow);

      const rightForearm = registerMesh(
        new THREE.Mesh(new THREE.CapsuleGeometry(0.042, 0.21, 6, 12), skinMat),
        segKey
      );
      rightForearm.position.set(0, 0.12, 0.04);
      rightElbow.add(rightForearm);

      const wristband = registerMesh(
        new THREE.Mesh(new THREE.CylinderGeometry(0.046, 0.046, 0.05, 12), trimMat),
        segKey
      );
      wristband.position.set(0, 0.21, 0.06);
      rightElbow.add(wristband);

      const racket = createPadelRacketMesh(team);
      racket.position.set(0, 0.24, 0.07);
      racket.rotation.x = -Math.PI / 5;
      rightElbow.add(racket);
      upperBody.add(rightShoulder);

      root.userData = {
        upperBody,
        leftLeg,
        rightLeg,
        leftShoulder,
        rightShoulder,
        rightElbow,
        team,
      };
      scene.add(root);
      return root;
    }

    const playerMeshes = {
      P1: createArticulatedPlayer("P1", "A"),
      P2: createArticulatedPlayer("P2", "A"),
      P3: createArticulatedPlayer("P3", "B"),
      P4: createArticulatedPlayer("P4", "B"),
    };

    // ------------------------------------------------------------------ //
    // Virtual Cameras Setup & Frustum Helpers (from padelkit.camera)
    // ------------------------------------------------------------------ //
    const camSelect = document.getElementById("camera-select");
    (CONFIG.cameras || []).forEach((camCfg) => {
      const vFov = camCfg.intrinsics.fov_vertical_deg;
      const aspect = camCfg.intrinsics.width_px / camCfg.intrinsics.height_px;
      const pCam = new THREE.PerspectiveCamera(vFov, aspect, 0.2, 120);
      const pos = camCfg.extrinsics.position;
      const fwd = camCfg.extrinsics.forward;
      const up = camCfg.extrinsics.up;
      pCam.position.set(pos[0], pos[1], pos[2]);
      pCam.up.set(up[0], up[1], up[2]);
      pCam.lookAt(pos[0] + fwd[0] * 10, pos[1] + fwd[1] * 10, pos[2] + fwd[2] * 10);
      pCam.updateMatrixWorld();
      presetThreeCameras[camCfg.name] = { camera: pCam, config: camCfg };

      const gizmo = new THREE.Mesh(
        new THREE.BoxGeometry(0.28, 0.28, 0.18),
        new THREE.MeshBasicMaterial({ color: 0x38bdf8, wireframe: true })
      );
      gizmo.position.copy(pCam.position);
      scene.add(gizmo);

      const opt = document.createElement("option");
      opt.value = camCfg.name;
      opt.textContent = `${camCfg.name} (${Math.round(camCfg.intrinsics.fov_horizontal_deg)}° FOV)`;
      camSelect.appendChild(opt);
    });

    camSelect.addEventListener("change", (e) => {
      const val = e.target.value;
      if (val === "__orbit__") {
        activeCamera = orbitCam;
        activePresetCameraCfg = null;
        controls.enabled = true;
      } else if (presetThreeCameras[val]) {
        activeCamera = presetThreeCameras[val].camera;
        activePresetCameraCfg = presetThreeCameras[val].config;
        controls.enabled = false;
      }
    });

    // ------------------------------------------------------------------ //
    // Render Mode Switcher (RGB / Semantic Segmentation / Depth)
    // ------------------------------------------------------------------ //
    const renderModeSelect = document.getElementById("render-mode");
    const segLegend = document.getElementById("seg-legend");
    renderModeSelect.addEventListener("change", (e) => {
      const mode = e.target.value;
      segLegend.style.display = mode === "segmentation" ? "flex" : "none";
      trackedMeshes.forEach((m) => {
        if (mode === "segmentation") m.material = m.userData.segMaterial;
        else if (mode === "depth") m.material = depthMaterial;
        else m.material = m.userData.rgbMaterial;
      });
    });

    // ------------------------------------------------------------------ //
    // 17 Court Landmarks Overlay Projection
    // ------------------------------------------------------------------ //
    let showLandmarks = true;
    document.getElementById("landmarks-toggle").addEventListener("change", (e) => {
      showLandmarks = e.target.value === "on";
      lmOverlay.style.display = showLandmarks ? "block" : "none";
    });

    const landmarkEntries = Object.entries(CONFIG.landmarks_3d || {});
    const lmDomNodes = landmarkEntries.map(([name, coords], idx) => {
      const el = document.createElement("div");
      el.className = "lm-tag";
      el.textContent = `${idx + 1}: ${name}`;
      lmOverlay.appendChild(el);
      return { name, vec: new THREE.Vector3(coords[0], coords[1], coords[2]), el };
    });

    function updateLandmarksOverlay() {
      if (!showLandmarks) return;
      const w = window.innerWidth;
      const h = window.innerHeight;
      lmDomNodes.forEach(({ vec, el }) => {
        const p = vec.clone().project(activeCamera);
        if (p.z > 1.0 || p.z < -1.0) {
          el.style.display = "none";
          return;
        }
        const sx = (p.x * 0.5 + 0.5) * w;
        const sy = (-p.y * 0.5 + 0.5) * h;
        if (sx < 0 || sx > w || sy < 0 || sy > h) {
          el.style.display = "none";
          return;
        }
        el.style.display = "block";
        el.style.left = `${sx}px`;
        el.style.top = `${sy}px`;
      });
    }

    // ------------------------------------------------------------------ //
    // Timeline Playback, 9D Telemetry & CSV Drag-and-Drop Loader
    // ------------------------------------------------------------------ //
    let timelineFrames = (CONFIG.timeline && CONFIG.timeline.frames) ? CONFIG.timeline.frames : [];
    let fps = (CONFIG.timeline && CONFIG.timeline.fps) ? CONFIG.timeline.fps : 60;
    let currentFrameIdx = 0;
    let isPlaying = true;
    let playbackSpeed = 1.0;

    const slider = document.getElementById("timeline-slider");
    const playBtn = document.getElementById("play-btn");
    const timeReadout = document.getElementById("time-readout");
    const scoreDisplay = document.getElementById("score-display");
    const eventDisplay = document.getElementById("event-display");
    const speedReadout = document.getElementById("speed-readout");
    const spinReadout = document.getElementById("spin-readout");
    const heightReadout = document.getElementById("height-readout");

    function refreshSliderRange() {
      slider.max = Math.max(timelineFrames.length - 1, 0);
    }
    refreshSliderRange();

    function applyFrameState(frame, frameIdx) {
      if (!frame) return;
      const [bx, by, bz] = frame.ball;
      ballMesh.position.set(bx, by, bz);
      ballGroundRing.position.set(bx, by, 0.004);
      const ringScale = Math.max(0.35, 1.2 - bz * 0.22);
      ballGroundRing.scale.set(ringScale, ringScale, 1);

      // Spin the 3D ball according to its 9D angular velocity vector [wx, wy, wz]
      const spinVec = frame.ball_spin || [0, 0, 0];
      const dtStep = 1.0 / Math.max(fps, 1);
      ballMesh.rotation.x += spinVec[0] * dtStep;
      ballMesh.rotation.y += spinVec[1] * dtStep;
      ballMesh.rotation.z += spinVec[2] * dtStep;

      // Update live 9D telemetry bar
      const velVec = frame.ball_vel || [0, 0, 0];
      const speedMs = Math.hypot(velVec[0], velVec[1], velVec[2]);
      const speedKmh = frame.ball_speed_kmh !== undefined ? frame.ball_speed_kmh : speedMs * 3.6;
      const spinMag = Math.hypot(spinVec[0], spinVec[1], spinVec[2]);
      const spinRpm = frame.ball_spin_rpm !== undefined ? frame.ball_spin_rpm : (spinMag * 60) / (Math.PI * 2);

      speedReadout.textContent = `${speedKmh.toFixed(1)} km/h`;
      spinReadout.textContent = `${Math.round(spinRpm)} RPM`;
      heightReadout.textContent = `${bz.toFixed(2)} m`;

      // Update ball trail ribbon
      if (timelineFrames.length > 0 && typeof frameIdx === "number") {
        for (let k = 0; k < trailMax; k++) {
          const sampleIdx = Math.max(0, frameIdx - k);
          const bf = timelineFrames[sampleIdx].ball;
          trailPositions[k * 3] = bf[0];
          trailPositions[k * 3 + 1] = bf[1];
          trailPositions[k * 3 + 2] = bf[2];
        }
        trailGeo.attributes.position.needsUpdate = true;
      }

      if (frame.score) scoreDisplay.textContent = `SCORE: ${frame.score}`;
      if (frame.event) {
        eventDisplay.textContent = frame.event.replace(/_/g, " ").toUpperCase();
        if (frame.event.startsWith("bounce_")) {
          spawnBounceMarker(bx, by, bz, frame.event);
        }
      }

      Object.entries(frame.players || {}).forEach(([pid, p]) => {
        const mesh = playerMeshes[pid];
        if (!mesh) return;
        mesh.position.set(p.x, p.y, p.z || 0);
        mesh.rotation.z = -THREE.MathUtils.degToRad(p.yaw_deg || 0);

        const isRunning = p.animation === "run";
        const phase = frame.t * 15.0;
        const hipSwing = isRunning ? Math.sin(phase) * 0.48 : 0.14;
        const kneeBendL = isRunning ? Math.max(0, -Math.sin(phase)) * 0.65 : 0.26;
        const kneeBendR = isRunning ? Math.max(0, Math.sin(phase)) * 0.65 : 0.26;

        mesh.userData.leftLeg.hipPivot.rotation.x = hipSwing;
        mesh.userData.rightLeg.hipPivot.rotation.x = -hipSwing;
        mesh.userData.leftLeg.kneePivot.rotation.x = -kneeBendL;
        mesh.userData.rightLeg.kneePivot.rotation.x = -kneeBendR;

        // Subtle athletic ready bounce and forward torso lean
        const sw = p.swing_phase || 0;
        mesh.userData.upperBody.rotation.x = isRunning ? 0.16 : 0.10;
        mesh.userData.upperBody.rotation.z = sw * 0.55;

        // Overhead vs groundstroke arm kinematics
        const animName = p.animation || "idle";
        if (animName.includes("smash") || animName.includes("bandeja")) {
          mesh.userData.rightShoulder.rotation.x = -Math.PI * 0.65 * sw + Math.sin(sw * Math.PI) * 1.1;
          mesh.userData.rightElbow.rotation.x = 0.4 * (1 - sw);
          mesh.userData.leftShoulder.rotation.x = -0.6 * sw;
        } else {
          mesh.userData.rightShoulder.rotation.x = sw * 1.45 - (isRunning ? Math.sin(phase) * 0.25 : 0);
          mesh.userData.rightElbow.rotation.x = 0.25 * sw;
          mesh.userData.leftShoulder.rotation.x = isRunning ? Math.sin(phase) * 0.3 : 0.1;
        }
      });

      const totalT = timelineFrames.length > 0 ? timelineFrames[timelineFrames.length - 1].t : frame.t;
      timeReadout.textContent = `${frame.t.toFixed(2)}s / ${totalT.toFixed(2)}s`;
    }

    playBtn.addEventListener("click", () => {
      isPlaying = !isPlaying;
      playBtn.textContent = isPlaying ? "Pause" : "Play";
    });
    slider.addEventListener("input", (e) => {
      isPlaying = false;
      playBtn.textContent = "Play";
      currentFrameIdx = parseInt(e.target.value, 10);
      applyFrameState(timelineFrames[currentFrameIdx], currentFrameIdx);
    });
    document.getElementById("speed-select").addEventListener("change", (e) => {
      playbackSpeed = parseFloat(e.target.value);
    });

    // Client-side CSV parser so users can load any PadelKit CSV directly in browser
    document.getElementById("csv-upload").addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (ev) => {
        const lines = ev.target.result.trim().split(/\\r?\\n/);
        if (lines.length < 2) return;
        const headers = lines[0].split(",").map((h) => h.trim());
        const parsed = [];
        for (let i = 1; i < lines.length; i++) {
          const vals = lines[i].split(",");
          const row = {};
          headers.forEach((h, idx) => (row[h] = vals[idx]));
          const players = {};
          ["p1", "p2", "p3", "p4"].forEach((k, idx) => {
            const pid = `P${idx + 1}`;
            if (row[`${k}_x`] !== undefined && row[`${k}_x`] !== "") {
              players[pid] = {
                x: parseFloat(row[`${k}_x`]),
                y: parseFloat(row[`${k}_y`]),
                z: parseFloat(row[`${k}_z`] || 0),
                yaw_deg: parseFloat(row[`${k}_yaw`] || 0),
                animation: row[`${k}_anim`] || "idle",
                swing_phase: parseFloat(row[`${k}_swing`] || 0),
              };
            }
          });
          parsed.push({
            t: parseFloat(row.timestamp || 0),
            ball: [parseFloat(row.ball_x), parseFloat(row.ball_y), parseFloat(row.ball_z)],
            ball_vel: [
              parseFloat(row.ball_vx || 0),
              parseFloat(row.ball_vy || 0),
              parseFloat(row.ball_vz || 0),
            ],
            ball_spin: [
              parseFloat(row.ball_wx || 0),
              parseFloat(row.ball_wy || 0),
              parseFloat(row.ball_wz || 0),
            ],
            score: row.score || "0-0",
            event: row.event || null,
            players,
          });
        }
        timelineFrames = parsed;
        currentFrameIdx = 0;
        refreshSliderRange();
        isPlaying = true;
        playBtn.textContent = "Pause";
      };
      reader.readAsText(file);
    });

    // Synthetic Frame + Ground Truth JSON Exporter
    document.getElementById("snapshot-btn").addEventListener("click", () => {
      renderer.render(scene, activeCamera);
      const dataUrl = renderer.domElement.toDataURL("image/png");
      const a = document.createElement("a");
      a.href = dataUrl;
      a.download = `padelkit_frame_${currentFrameIdx}.png`;
      a.click();
    });

    // Optional Live SSE Streaming Connection (when served via visualizer.serve())
    if (CONFIG.live_stream_url) {
      const badge = document.getElementById("mode-badge");
      badge.textContent = "LIVE STREAM CONNECTED";
      badge.classList.add("live");
      const evtSource = new EventSource(CONFIG.live_stream_url);
      evtSource.onmessage = (msg) => {
        try {
          const liveFrame = JSON.parse(msg.data);
          isPlaying = false;
          applyFrameState(liveFrame, 0);
        } catch (_) {}
      };
    }

    // Main Render Loop
    let lastTime = performance.now();
    let accumulator = 0;

    function animate(now) {
      requestAnimationFrame(animate);
      const dt = (now - lastTime) / 1000;
      lastTime = now;

      // Fade out Hawk-Eye bounce markers smoothly
      bounceRings.forEach((b) => {
        if (b.opacity > 0) {
          b.opacity = Math.max(0, b.opacity - dt * 0.55);
          b.mesh.material.opacity = b.opacity;
        }
      });

      if (isPlaying && timelineFrames.length > 0) {
        accumulator += dt * playbackSpeed;
        const frameDuration = 1.0 / fps;
        while (accumulator >= frameDuration) {
          accumulator -= frameDuration;
          currentFrameIdx = (currentFrameIdx + 1) % timelineFrames.length;
          slider.value = currentFrameIdx;
          applyFrameState(timelineFrames[currentFrameIdx], currentFrameIdx);
        }
      }

      if (controls.enabled) controls.update();
      renderer.render(scene, activeCamera);
      updateLandmarksOverlay();
    }

    if (timelineFrames.length > 0) {
      applyFrameState(timelineFrames[0], 0);
    }
    requestAnimationFrame(animate);

    window.addEventListener("resize", () => {
      orbitCam.aspect = window.innerWidth / window.innerHeight;
      orbitCam.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
    });
  </script>
</body>
</html>
"""
