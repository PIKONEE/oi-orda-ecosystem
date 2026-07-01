// Shared library for interactive 3D anatomical posters.
// Each poster HTML imports this and calls initPoster(config).
//
// Config: { modelFile, zones, classify | seeds, i18n, modelScale?, modelRotation? }
//
// Two ways to define which zone a click falls into:
//
//   classify(x, y, z) — function returning zone index (0-based) or -1.
//   seeds: { zoneId: [[x,y,z], ...] } — anchor points per zone.
//          Click is assigned to the zone with the nearest seed (Voronoi).
//          Multi-seed support: elongated parts (spine, intestines) get several anchors.
//
//   Coordinate frame after normalization: x right, y up, z front.
//   Model is auto-scaled so the largest dimension spans ~2.4 units (range approx [-1.2, +1.2]).
//
// ZONES schema: { id, subtitle, color }
//   color is used only for legend dot and info-panel dot.
//
// URL params:
//   ?lang=ru|kz|en  — language
//   ?debug=1        — show axes helper, bounding box, log hit coords to console

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

export function initPoster(config) {
    const { modelFile, zones: ZONES, classify: classifyFn, seeds, i18n: I18N, modelScale = 1.0, modelRotation = [0, 0.2, 0], exposure = 1.05 } = config;

    // If seeds provided, build a nearest-seed classify function.
    let classify = classifyFn;
    if (!classify && seeds) {
        const flat = []; // [x, y, z, zoneIdx, ...]
        for (const [zoneId, pts] of Object.entries(seeds)) {
            const zi = ZONES.findIndex(z => z.id === zoneId);
            if (zi < 0) { console.warn('seeds: unknown zone id', zoneId); continue; }
            for (const p of pts) flat.push(p[0], p[1], p[2], zi);
        }
        classify = (x, y, z) => {
            let best = -1, bestD = Infinity;
            for (let i = 0; i < flat.length; i += 4) {
                const dx = x - flat[i], dy = y - flat[i + 1], dz = z - flat[i + 2];
                const d = dx * dx + dy * dy + dz * dz;
                if (d < bestD) { bestD = d; best = flat[i + 3]; }
            }
            return best;
        };
    }
    if (!classify) {
        console.error('initPoster: provide either `classify` or `seeds`');
        classify = () => -1;
    }

    const LANG = (() => {
        const q = new URLSearchParams(location.search).get('lang');
        return (q && I18N[q]) ? q : 'ru';
    })();
    const t = (key) => (I18N[LANG] && I18N[LANG][key]) ?? I18N.ru[key];
    const zoneText = (zone, key) => I18N[LANG]?.zones?.[zone.id]?.[key] ?? I18N.ru.zones[zone.id][key];

    // --- Static i18n ---
    document.documentElement.lang = LANG;
    const titleVal = t('page_title'); if (titleVal) document.title = titleVal;
    document.querySelectorAll('[data-i18n]').forEach(el => { const v = t(el.getAttribute('data-i18n')); if (v) el.textContent = v; });
    document.querySelectorAll('[data-i18n-title]').forEach(el => { const v = t(el.getAttribute('data-i18n-title')); if (v) el.setAttribute('title', v); });
    document.querySelectorAll('[data-i18n-aria-label]').forEach(el => { const v = t(el.getAttribute('data-i18n-aria-label')); if (v) el.setAttribute('aria-label', v); });

    // --- Language switcher ---
    const sw = document.getElementById('lang-switcher');
    if (sw) {
        sw.querySelectorAll('.lang-pill').forEach(btn => {
            const lang = btn.dataset.lang;
            if (lang === LANG) btn.classList.add('active');
            btn.addEventListener('click', () => {
                if (lang === LANG) return;
                const url = new URL(location.href);
                url.searchParams.set('lang', lang);
                location.href = url.toString();
            });
        });
    }

    const DEBUG = new URLSearchParams(location.search).get('debug') === '1';

    // --- Three.js scene ---
    const container = document.getElementById('canvas-container');
    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0x111838, 12, 40);

    const camera = new THREE.PerspectiveCamera(38, window.innerWidth / window.innerHeight, 0.05, 200);
    const CAMERA_START = new THREE.Vector3(0, 0.5, 5.5);
    camera.position.copy(CAMERA_START);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = exposure;
    container.appendChild(renderer.domElement);

    scene.add(new THREE.AmbientLight(0xffffff, 0.65));
    const keyLight = new THREE.DirectionalLight(0xffe9c8, 1.1); keyLight.position.set(3, 4, 4); scene.add(keyLight);
    const fillLight = new THREE.DirectionalLight(0x8cb6ff, 0.55); fillLight.position.set(-4, 1, -3); scene.add(fillLight);
    const rimLight = new THREE.DirectionalLight(0xffffff, 0.4); rimLight.position.set(0, -3, -4); scene.add(rimLight);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true; controls.dampingFactor = 0.08;
    controls.minDistance = 2.2; controls.maxDistance = 12;
    controls.target.set(0, 0, 0);
    controls.autoRotate = false;   // было true — постоянное вращение грело панель и приводило к сбросу WebGL-контекста

    const modelGroup = new THREE.Group(); scene.add(modelGroup);
    let mainMesh = null;
    let selectedZone = -1;
    let hitWorldPoint = null; // THREE.Vector3 — the 3D point of the last click (world coords)

    // --- Callout UI (created dynamically) ---
    const callout = document.createElement('div');
    callout.id = 'callout';
    callout.innerHTML = `<button class="callout-close">&times;</button><h3 id="callout-title"></h3><span id="callout-subtitle"></span><p id="callout-desc"></p><div id="callout-facts"></div>`;
    document.body.appendChild(callout);

    const svgNS = 'http://www.w3.org/2000/svg';
    const connectorSvg = document.createElementNS(svgNS, 'svg');
    connectorSvg.id = 'callout-line';
    const connectorCircle = document.createElementNS(svgNS, 'circle');
    connectorCircle.setAttribute('r', '4');
    const connectorLine = document.createElementNS(svgNS, 'line');
    connectorSvg.appendChild(connectorLine);
    connectorSvg.appendChild(connectorCircle);
    document.body.appendChild(connectorSvg);

    const calloutTitle = document.getElementById('callout-title');
    const calloutSubtitle = document.getElementById('callout-subtitle');
    const calloutDesc = document.getElementById('callout-desc');
    const calloutFacts = document.getElementById('callout-facts');
    callout.querySelector('.callout-close').addEventListener('click', (e) => { e.stopPropagation(); closeCallout(); });

    // --- Load model ---
    const loader = new GLTFLoader();
    loader.load(modelFile,
        (gltf) => { setupModel(gltf); },
        (xhr) => { if (xhr.lengthComputable) { const pct = Math.round(xhr.loaded / xhr.total * 100); document.getElementById('loading-text').textContent = `${t('loading')} ${pct}%`; } },
        (err) => { console.error('Error loading model', err); document.getElementById('loading-text').textContent = t('error_load'); }
    );

    function setupModel(gltf) {
        let origMesh = null;
        gltf.scene.traverse(obj => { if (!origMesh && obj.isMesh) origMesh = obj; });
        if (!origMesh) { document.getElementById('loading-text').textContent = t('error_no_mesh'); return; }

        const geom = origMesh.geometry;
        if (!geom.boundingBox) geom.computeBoundingBox();
        const bb = geom.boundingBox;
        const size = new THREE.Vector3(); bb.getSize(size);
        const center = new THREE.Vector3(); bb.getCenter(center);
        const maxDim = Math.max(size.x, size.y, size.z);
        const fitScale = (2.4 / maxDim) * modelScale;

        mainMesh = new THREE.Mesh(geom, origMesh.material);
        mainMesh.name = 'AnatomyMesh';
        
        // Scale and position the mesh directly instead of modifying geometry vertices (safer for interleaved/quantized buffers)
        mainMesh.scale.setScalar(fitScale);
        mainMesh.position.set(-center.x * fitScale, -center.y * fitScale, -center.z * fitScale);
        
        modelGroup.add(mainMesh);

        modelGroup.rotation.set(modelRotation[0], modelRotation[1], modelRotation[2]);

        if (DEBUG) {
            const axes = new THREE.AxesHelper(1.6);
            axes.renderOrder = 1000;
            scene.add(axes);
            const helper = new THREE.Box3Helper(bb.clone(), 0x7aa7ff);
            modelGroup.add(helper);
        }

        const loading = document.getElementById('loading');
        loading.classList.add('hidden'); setTimeout(() => loading.remove(), 800);
        const hint = document.getElementById('hint'); hint.classList.add('show');
        setTimeout(() => hint.classList.remove('show'), 5000);
        buildLegend();
        requestRender();   // показать модель после загрузки
    }

    function buildLegend() {
        const legend = document.getElementById('legend'); legend.innerHTML = '';
        ZONES.forEach((z, i) => {
            const chip = document.createElement('div'); chip.className = 'legend-chip'; chip.dataset.zone = i;
            chip.textContent = zoneText(z, 'title');
            chip.addEventListener('click', () => focusZone(i));
            legend.appendChild(chip);
        });
    }

    function syncChipActive() {
        document.querySelectorAll('.legend-chip').forEach(c => {
            const idx = parseInt(c.dataset.zone, 10);
            c.classList.toggle('active', idx === selectedZone);
        });
    }

    const resetBtn = document.getElementById('reset-btn');

    function showCallout(zoneIdx) {
        const z = ZONES[zoneIdx]; if (!z) return;
        calloutTitle.textContent = zoneText(z, 'title');
        calloutSubtitle.textContent = z.subtitle || '';
        calloutDesc.textContent = zoneText(z, 'desc');
        const factsText = zoneText(z, 'facts');
        if (factsText) { calloutFacts.innerHTML = `<strong>${t('facts_label')}</strong> ${factsText}`; calloutFacts.style.display = 'block'; }
        else calloutFacts.style.display = 'none';
        callout.classList.add('show');
        if (hitWorldPoint) connectorSvg.classList.add('show');
        else {
            connectorSvg.classList.remove('show');
            // Center callout when no world hit (e.g. legend click)
            callout.style.left = (window.innerWidth / 2 - 150) + 'px';
            callout.style.top = (window.innerHeight / 2 - 90) + 'px';
        }
        resetBtn.classList.add('show');
    }

    function closeCallout() {
        callout.classList.remove('show');
        connectorSvg.classList.remove('show');
        selectedZone = -1;
        hitWorldPoint = null;
        syncChipActive();
        resetBtn.classList.remove('show');
    }

    function focusZone(zoneIdx, worldPt) {
        selectedZone = zoneIdx;
        hitWorldPoint = worldPt || null;
        syncChipActive();
        showCallout(zoneIdx);
        controls.autoRotate = false;
        updateCalloutPosition(); // immediate positioning
    }

    // Project 3D world point to 2D screen and position callout + connector
    function updateCalloutPosition() {
        if (!hitWorldPoint || selectedZone < 0) return;
        const projected = hitWorldPoint.clone().project(camera);
        const hw = window.innerWidth / 2;
        const hh = window.innerHeight / 2;
        const sx = (projected.x * hw) + hw;
        const sy = -(projected.y * hh) + hh;

        // Place callout to the right of the click point, not too far
        const calloutW = 300;
        const calloutH = callout.offsetHeight || 180;
        let cx = sx + 60;
        // If it would go off-screen right, put it to the left of the point
        if (cx + calloutW > window.innerWidth - 10) cx = sx - calloutW - 60;
        // Ensure minimum distance from left edge
        if (cx < 10) cx = 10;
        let cy = sy - calloutH / 2;
        // Keep within viewport vertically
        if (cy < 10) cy = 10;
        if (cy + calloutH > window.innerHeight - 10) cy = window.innerHeight - calloutH - 10;

        callout.style.left = cx + 'px';
        callout.style.top = cy + 'px';

        // Connector line from hit point to nearest callout edge
        const cardEdgeX = cx < sx ? cx + calloutW : cx;
        const cardEdgeY = cy + calloutH / 2;
        connectorCircle.setAttribute('cx', sx);
        connectorCircle.setAttribute('cy', sy);
        connectorLine.setAttribute('x1', sx);
        connectorLine.setAttribute('y1', sy);
        connectorLine.setAttribute('x2', cardEdgeX);
        connectorLine.setAttribute('y2', cardEdgeY);
    }

    if (resetBtn) resetBtn.addEventListener('click', () => { closeCallout(); camera.position.copy(CAMERA_START); controls.target.set(0, 0, 0); requestRender(); });

    // --- Raycasting on mesh ---
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();
    const hoverLabel = document.getElementById('hover-label');

    function hitMesh(event) {
        if (!mainMesh) return null;
        const rect = renderer.domElement.getBoundingClientRect();
        mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
        raycaster.setFromCamera(mouse, camera);
        const hits = raycaster.intersectObject(mainMesh, false);
        if (hits.length === 0) return null;
        const hit = hits[0];
        const localPoint = modelGroup.worldToLocal(hit.point.clone());
        const zi = classify(localPoint.x, localPoint.y, localPoint.z);
        if (DEBUG) console.log('[hit]', localPoint.x.toFixed(2), localPoint.y.toFixed(2), localPoint.z.toFixed(2), '→ zone', zi, zi >= 0 ? ZONES[zi].id : 'none');
        return { zoneIndex: zi, worldPoint: hit.point.clone() };
    }

    renderer.domElement.addEventListener('pointermove', (e) => {
        const result = hitMesh(e);
        if (result && result.zoneIndex >= 0) {
            renderer.domElement.style.cursor = 'pointer';
            hoverLabel.textContent = zoneText(ZONES[result.zoneIndex], 'title');
            hoverLabel.classList.add('show');
        } else {
            renderer.domElement.style.cursor = 'grab';
            hoverLabel.classList.remove('show');
        }
        hoverLabel.style.left = e.clientX + 'px';
        hoverLabel.style.top = e.clientY + 'px';
    });
    renderer.domElement.addEventListener('pointerleave', () => {
        hoverLabel.classList.remove('show');
        renderer.domElement.style.cursor = 'grab';
    });
    renderer.domElement.addEventListener('pointerdown', () => { renderer.domElement.style.cursor = 'grabbing'; });
    renderer.domElement.addEventListener('pointerup', () => { renderer.domElement.style.cursor = 'grab'; });

    let downPos = null;
    renderer.domElement.addEventListener('mousedown', (e) => { downPos = { x: e.clientX, y: e.clientY }; });
    renderer.domElement.addEventListener('mouseup', (e) => {
        if (!downPos) return;
        const dx = e.clientX - downPos.x, dy = e.clientY - downPos.y;
        downPos = null;
        if (Math.hypot(dx, dy) > 4) return;
        const result = hitMesh(e);
        if (result && result.zoneIndex >= 0) {
            focusZone(result.zoneIndex, result.worldPoint);
        } else {
            closeCallout();
        }
    });
    renderer.domElement.addEventListener('touchend', (e) => {
        if (e.changedTouches && e.changedTouches.length > 0) {
            const touch = e.changedTouches[0];
            const result = hitMesh(touch);
            if (result && result.zoneIndex >= 0) focusZone(result.zoneIndex, result.worldPoint);
        }
    });
    // Рендер ПО ТРЕБОВАНИЮ: рисуем только когда камера движется (вращение/затухание)
    // или явно запрошено. В покое GPU простаивает → нет нагрева и «выгорания» контекста.
    let needsRender = true;
    function requestRender() { needsRender = true; }
    controls.addEventListener('change', requestRender);   // перерисовка при любом движении камеры (вращение/зум/инерция)

    function animate() {
        requestAnimationFrame(animate);
        const moving = controls.update();   // true пока идёт вращение/инерция
        if (moving || needsRender) {
            if (hitWorldPoint) updateCalloutPosition();
            renderer.render(scene, camera);
            needsRender = false;
        }
    }
    animate();
    window.addEventListener('resize', () => { camera.aspect = window.innerWidth / window.innerHeight; camera.updateProjectionMatrix(); renderer.setSize(window.innerWidth, window.innerHeight); requestRender(); });
    window.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeCallout(); });
}
