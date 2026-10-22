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
      --border: rgba(148, 163, 184, 0.2);
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
      backdrop-filter: blur(12px);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 12px 16px;
      pointer-events: auto;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45);
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
      gap: 14px;
      align-items: center;
    }
    .event-pill {
      font-size: 11px;
      padding: 2px 8px;
      border-radius: 6px;
      background: rgba(245, 158, 11, 0.2);
      color: #fbbf24;
      border: 1px solid rgba(245, 158, 11, 0.4);
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
        <span id="mode-badge" class="badge">REPLAY / INTERACTIVE</span>
      </div>
      <div class="scoreboard">
        <span id="score-display">SCORE: 0-0 | 0-0</span>
        <span id="event-display" class="event-pill">READY</span>
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
    renderer.toneMappingExposure = 1.1;
    container.appendChild(renderer.domElement);

    // PadelKit uses Z-up (X width, Y length, Z height)
    THREE.Object3D.DEFAULT_UP.set(0, 0, 1);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0b0f19);
    scene.fog = new THREE.FogExp2(0x0b0f19, 0.012);

    // Orbit camera
    const orbitCam = new THREE.PerspectiveCamera(50, window.innerWidth / window.innerHeight, 0.1, 150);
    orbitCam.position.set(11.5, -16.5, 9.0);
    orbitCam.up.set(0, 0, 1);

    const controls = new OrbitControls(orbitCam, renderer.domElement);
    controls.target.set(0, 0, 0.8);
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
    const hemiLight = new THREE.HemisphereLight(0xdbeafe, 0x1e293b, 0.85);
    hemiLight.position.set(0, 0, 15);
    scene.add(hemiLight);

    const floodlightPositions = [
      [-5.2, -5.0, 6.2],
      [ 5.2, -5.0, 6.2],
      [-5.2,  5.0, 6.2],
      [ 5.2,  5.0, 6.2],
    ];
    floodlightPositions.forEach(([lx, ly, lz], idx) => {
      const spot = new THREE.DirectionalLight(0xf8fafc, 0.72);
      spot.position.set(lx, ly, lz);
      if (idx < 2) {
        spot.castShadow = true;
        spot.shadow.mapSize.set(1024, 1024);
        spot.shadow.camera.near = 1;
        spot.shadow.camera.far = 28;
        const d = 12;
        spot.shadow.camera.left = -d;
        spot.shadow.camera.right = d;
        spot.shadow.camera.top = d;
        spot.shadow.camera.bottom = -d;
      }
      scene.add(spot);
    });

    // ------------------------------------------------------------------ //
    // Procedural High-Realism FIP Padel Court Builder
    // ------------------------------------------------------------------ //
    const dims = CONFIG.court.dimensions;
    const W = dims.width;
    const L = dims.length;
    const hw = W / 2;
    const hl = L / 2;

    // 1. Surrounding arena floor
    const arenaFloorGeo = new THREE.PlaneGeometry(46, 56);
    const arenaFloorMat = new THREE.MeshStandardMaterial({ color: 0x111827, roughness: 0.9 });
    const arenaFloor = new THREE.Mesh(arenaFloorGeo, arenaFloorMat);
    arenaFloor.position.z = -0.01;
    arenaFloor.receiveShadow = true;
    scene.add(arenaFloor);

    // 2. Procedural Silica-Sand Artificial Turf Texture
    function createTurfTexture(colorName) {
      const canvas = document.createElement("canvas");
      canvas.width = 512;
      canvas.height = 512;
      const ctx = canvas.getContext("2d");
      const baseColors = {
        blue: "#0f4c81",
        green: "#1b5e20",
        black: "#1e293b",
        terracotta: "#9a3412",
      };
      ctx.fillStyle = baseColors[colorName] || baseColors.blue;
      ctx.fillRect(0, 0, 512, 512);
      for (let i = 0; i < 24000; i++) {
        const x = Math.random() * 512;
        const y = Math.random() * 512;
        ctx.fillStyle = Math.random() > 0.5 ? "rgba(255,255,255,0.045)" : "rgba(0,0,0,0.06)";
        ctx.fillRect(x, y, 2, 2);
      }
      const tex = new THREE.CanvasTexture(canvas);
      tex.wrapS = THREE.RepeatWrapping;
      tex.wrapT = THREE.RepeatWrapping;
      tex.repeat.set(8, 16);
      return tex;
    }

    const turfGeo = new THREE.PlaneGeometry(W, L);
    const turfMat = new THREE.MeshStandardMaterial({
      map: createTurfTexture(CONFIG.court.turf_color || "blue"),
      roughness: 0.78,
      metalness: 0.05,
    });
    const turfMesh = registerMesh(new THREE.Mesh(turfGeo, turfMat), "turf");
    turfMesh.receiveShadow = true;
    scene.add(turfMesh);

    // 3. Regulation 5cm White Court Lines
    const lineMat = new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 0.5 });
    const lineW = 0.05;
    const svcY = hl - dims.service_line_distance_from_back;

    function addCourtLine(x, y, width, length) {
      const m = registerMesh(
        new THREE.Mesh(new THREE.PlaneGeometry(width, length), lineMat),
        "line"
      );
      m.position.set(x, y, 0.002);
      scene.add(m);
    }
    // Perimeter & service lines
    addCourtLine(0, -hl, W, lineW);
    addCourtLine(0,  hl, W, lineW);
    addCourtLine(-hw, 0, lineW, L);
    addCourtLine( hw, 0, lineW, L);
    addCourtLine(0, -svcY, W, lineW);
    addCourtLine(0,  svcY, W, lineW);
    addCourtLine(0, 0, lineW, svcY * 2 + 0.2);

    // 4. Tempered Glass Walls (Back walls 4m + Side stepped glass 4m & 3m)
    const glassMat = new THREE.MeshPhysicalMaterial({
      color: 0xdbeafe,
      transparent: true,
      opacity: 0.34,
      roughness: 0.08,
      metalness: 0.05,
      reflectivity: 0.9,
      side: THREE.DoubleSide,
    });
    const pillarMat = new THREE.MeshStandardMaterial({
      color: 0x1e293b,
      metalness: 0.7,
      roughness: 0.3,
    });

    function createMetallicMeshMaterial() {
      const c = document.createElement("canvas");
      c.width = 64;
      c.height = 64;
      const ctx = c.getContext("2d");
      ctx.clearRect(0, 0, 64, 64);
      ctx.strokeStyle = "#94a3b8";
      ctx.lineWidth = 5;
      ctx.strokeRect(0, 0, 64, 64);
      const tex = new THREE.CanvasTexture(c);
      tex.wrapS = THREE.RepeatWrapping;
      tex.wrapT = THREE.RepeatWrapping;
      tex.repeat.set(16, 16);
      return new THREE.MeshStandardMaterial({
        map: tex,
        transparent: true,
        alphaTest: 0.15,
        side: THREE.DoubleSide,
        metalness: 0.8,
        roughness: 0.35,
      });
    }
    const wireMeshMat = createMetallicMeshMaterial();

    function addWallPanel(x, y, z, width, depth, height, isGlass) {
      const geo = new THREE.BoxGeometry(width, depth, height);
      const mat = isGlass ? glassMat : wireMeshMat;
      const mesh = registerMesh(new THREE.Mesh(geo, mat), isGlass ? "glass" : "mesh");
      mesh.position.set(x, y, z + height / 2);
      scene.add(mesh);

      // Frame post
      const postGeo = new THREE.BoxGeometry(0.06, 0.06, height);
      const post = registerMesh(new THREE.Mesh(postGeo, pillarMat), "structure");
      post.position.set(x, y, z + height / 2);
      scene.add(post);
    }

    const backH = dims.back_wall_height;
    const sideH = dims.side_wall_height;
    const glassThick = 0.015;

    // Back walls (5 panels of 2m width x 3m glass + 1m top mesh in V1)
    for (let i = 0; i < 5; i++) {
      const px = -hw + 1.0 + i * 2.0;
      addWallPanel(px, -hl, 0, 1.98, glassThick, 3.0, true);
      addWallPanel(px, -hl, 3.0, 1.98, glassThick, backH - 3.0, false);
      addWallPanel(px,  hl, 0, 1.98, glassThick, 3.0, true);
      addWallPanel(px,  hl, 3.0, 1.98, glassThick, backH - 3.0, false);
    }

    // Side walls (First 2m from each back wall: 3m glass + 1m mesh; next 2m: 2m glass + 1m mesh; middle: 3m mesh)
    const sideSegments = [
      { y: -hl + 1.0, len: 2.0, glassH: 3.0, meshH: 1.0 },
      { y: -hl + 3.0, len: 2.0, glassH: 2.0, meshH: 1.0 },
      { y: -hl + 5.0, len: 2.0, glassH: 0.0, meshH: sideH },
      { y: -hl + 7.0, len: 2.0, glassH: 0.0, meshH: sideH },
      { y:  hl - 7.0, len: 2.0, glassH: 0.0, meshH: sideH },
      { y:  hl - 5.0, len: 2.0, glassH: 0.0, meshH: sideH },
      { y:  hl - 3.0, len: 2.0, glassH: 2.0, meshH: 1.0 },
      { y:  hl - 1.0, len: 2.0, glassH: 3.0, meshH: 1.0 },
    ];
    sideSegments.forEach((seg) => {
      [-hw, hw].forEach((sx) => {
        if (seg.glassH > 0) {
          addWallPanel(sx, seg.y, 0, glassThick, seg.len - 0.02, seg.glassH, true);
        }
        if (seg.meshH > 0) {
          addWallPanel(sx, seg.y, seg.glassH, glassThick, seg.len - 0.02, seg.meshH, false);
        }
      });
    });

    // 5. Net with Regulation Catenary Sag (0.88m center, 0.92m posts)
    const netSegments = 32;
    const netGeo = new THREE.PlaneGeometry(W, 0.92, netSegments, 4);
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
      color: 0x1e293b,
      wireframe: true,
      side: THREE.DoubleSide,
    });
    const netMesh = registerMesh(new THREE.Mesh(netGeo, netMat), "net");
    scene.add(netMesh);

    // White top net tape
    const tapeCurvePts = [];
    for (let i = 0; i <= netSegments; i++) {
      const u = (i / netSegments) * 2 - 1;
      const z = dims.net_height_center + (dims.net_height_posts - dims.net_height_center) * (u * u);
      tapeCurvePts.push(new THREE.Vector3(u * hw, 0, z));
    }
    const tapeCurve = new THREE.CatmullRomCurve3(tapeCurvePts);
    const tapeGeo = new THREE.TubeGeometry(tapeCurve, 32, 0.024, 8, false);
    const tapeMesh = registerMesh(new THREE.Mesh(tapeGeo, lineMat), "net");
    scene.add(tapeMesh);

    // ------------------------------------------------------------------ //
    // 3D Ball + Dynamic Trajectory Ribbon
    // ------------------------------------------------------------------ //
    const ballGeo = new THREE.SphereGeometry(0.0335, 24, 24);
    const ballMat = new THREE.MeshStandardMaterial({
      color: 0xd9f99d,
      emissive: 0x65a30d,
      emissiveIntensity: 0.4,
      roughness: 0.4,
    });
    const ballMesh = registerMesh(new THREE.Mesh(ballGeo, ballMat), "ball");
    ballMesh.castShadow = true;
    scene.add(ballMesh);

    const trailMax = 45;
    const trailPositions = new Float32Array(trailMax * 3);
    const trailGeo = new THREE.BufferGeometry();
    trailGeo.setAttribute("position", new THREE.BufferAttribute(trailPositions, 3));
    const trailMat = new THREE.LineBasicMaterial({ color: 0xbef264, transparent: true, opacity: 0.75 });
    const trailLine = new THREE.Line(trailGeo, trailMat);
    scene.add(trailLine);

    // ------------------------------------------------------------------ //
    // Articulated 3D Padel Players + Perforated Padel Racket in RightHand
    // ------------------------------------------------------------------ //
    function createPadelRacketMesh() {
      const racketGroup = new THREE.Group();
      const handle = registerMesh(
        new THREE.Mesh(
          new THREE.CylinderGeometry(0.015, 0.015, 0.14, 12),
          new THREE.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.6 })
        ),
        "racket"
      );
      handle.rotation.x = Math.PI / 2;
      handle.position.z = 0.07;
      racketGroup.add(handle);

      const head = registerMesh(
        new THREE.Mesh(
          new THREE.CylinderGeometry(0.13, 0.11, 0.038, 20),
          new THREE.MeshStandardMaterial({ color: 0xf97316, metalness: 0.3, roughness: 0.35 })
        ),
        "racket"
      );
      head.scale.set(1.0, 1.0, 1.22);
      head.position.z = 0.28;
      racketGroup.add(head);
      return racketGroup;
    }

    function createArticulatedPlayer(playerId, team) {
      const root = new THREE.Group();
      const segKey = team === "A" ? "teamA" : "teamB";
      const jerseyColor = team === "A" ? 0x0284c7 : 0xe11d48;
      const shortsColor = team === "A" ? 0x0f172a : 0xf8fafc;
      const skinMat = new THREE.MeshStandardMaterial({ color: 0xf1c27d, roughness: 0.6 });
      const jerseyMat = new THREE.MeshStandardMaterial({ color: jerseyColor, roughness: 0.5 });
      const shortsMat = new THREE.MeshStandardMaterial({ color: shortsColor, roughness: 0.6 });

      // Torso
      const torso = registerMesh(
        new THREE.Mesh(new THREE.CapsuleGeometry(0.18, 0.46, 8, 16), jerseyMat),
        segKey
      );
      torso.rotation.x = Math.PI / 2;
      torso.position.z = 1.15;
      torso.castShadow = true;
      root.add(torso);

      // Shorts / Pelvis
      const pelvis = registerMesh(
        new THREE.Mesh(new THREE.CylinderGeometry(0.17, 0.16, 0.24, 14), shortsMat),
        segKey
      );
      pelvis.rotation.x = Math.PI / 2;
      pelvis.position.z = 0.82;
      root.add(pelvis);

      // Head
      const head = registerMesh(
        new THREE.Mesh(new THREE.SphereGeometry(0.13, 16, 16), skinMat),
        segKey
      );
      head.position.z = 1.62;
      head.castShadow = true;
      root.add(head);

      // Legs
      const leftLeg = registerMesh(
        new THREE.Mesh(new THREE.CapsuleGeometry(0.065, 0.58, 6, 12), skinMat),
        segKey
      );
      leftLeg.rotation.x = Math.PI / 2;
      leftLeg.position.set(-0.1, 0, 0.38);
      root.add(leftLeg);

      const rightLeg = registerMesh(
        new THREE.Mesh(new THREE.CapsuleGeometry(0.065, 0.58, 6, 12), skinMat),
        segKey
      );
      rightLeg.rotation.x = Math.PI / 2;
      rightLeg.position.set(0.1, 0, 0.38);
      root.add(rightLeg);

      // Right Arm + Padel Racket Pivot
      const rightShoulder = new THREE.Group();
      rightShoulder.position.set(0.24, 0, 1.35);
      const rightArm = registerMesh(
        new THREE.Mesh(new THREE.CapsuleGeometry(0.05, 0.44, 6, 12), skinMat),
        segKey
      );
      rightArm.position.set(0, 0.22, -0.1);
      rightShoulder.add(rightArm);

      const racket = createPadelRacketMesh();
      racket.position.set(0, 0.42, -0.05);
      racket.rotation.x = -Math.PI / 4;
      rightShoulder.add(racket);
      root.add(rightShoulder);

      root.userData = { leftLeg, rightLeg, rightShoulder, team };
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

      // Small camera body gizmo in the 3D scene
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
    // Timeline Playback & CSV Drag-and-Drop Loader
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

    function refreshSliderRange() {
      slider.max = Math.max(timelineFrames.length - 1, 0);
    }
    refreshSliderRange();

    function applyFrameState(frame, frameIdx) {
      if (!frame) return;
      const [bx, by, bz] = frame.ball;
      ballMesh.position.set(bx, by, bz);

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
      if (frame.event) eventDisplay.textContent = frame.event.toUpperCase();

      Object.entries(frame.players || {}).forEach(([pid, p]) => {
        const mesh = playerMeshes[pid];
        if (!mesh) return;
        mesh.position.set(p.x, p.y, p.z || 0);
        // Convert yaw_deg (0 = +Y, 90 = +X) to Z rotation
        mesh.rotation.z = -THREE.MathUtils.degToRad(p.yaw_deg || 0);

        const stride = p.animation === "run" ? Math.sin(frame.t * 14) * 0.45 : 0;
        mesh.userData.leftLeg.rotation.x = Math.PI / 2 + stride;
        mesh.userData.rightLeg.rotation.x = Math.PI / 2 - stride;

        const swing = (p.swing_phase || 0) * 1.4;
        mesh.userData.rightShoulder.rotation.x = swing;
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
