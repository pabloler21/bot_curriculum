// Objeto 3D de cada página de features: lupa (evaluator), puzzle (adapter), globo (jobs).
// La escena la elige data-scene en .feature-visual; se arrastra para girarla.
// Si WebGL o el CDN fallan, queda el glifo de .feature-visual.
// +esm: el paquete de three no trae builds minificados; jsDelivr los arma, y el addon
// importa esta misma URL, así que hay una sola copia de three.
const THREE_URL = 'https://cdn.jsdelivr.net/npm/three@0.186.1/+esm';
const ROOM_ENV_URL = 'https://cdn.jsdelivr.net/npm/three@0.186.1/examples/jsm/environments/RoomEnvironment.js/+esm';
let THREE, RoomEnvironment;

const ACCENT = 0xFF7A5C;
const AQUA = 0x5EEAD4;
const ease = (t) => 1 - Math.pow(1 - t, 3);
const clampX = (x) => Math.max(-1.1, Math.min(1.1, x));
const animated = !matchMedia('(prefers-reduced-motion: reduce)').matches;
// ponytail: pantalla táctil como proxy de GPU modesta; medir en equipos reales si se queda corto.
const cheapGlass = matchMedia('(pointer: coarse)').matches;

// El vidrio con transmission dibuja la escena dos veces por cuadro: en táctil va translúcido.
function glass(params) {
  return new THREE.MeshPhysicalMaterial(cheapGlass
    ? { ...params, transmission: 0, transparent: true, opacity: 0.6 }
    : params);
}

// Evaluator: una lupa de vidrio recorre el CV.
function evaluator(group) {
  const cv = document.createElement('canvas');
  cv.width = 360; cv.height = 480;
  const x = cv.getContext('2d');
  x.fillStyle = '#1b1f3a'; x.fillRect(0, 0, 360, 480);
  x.fillStyle = 'rgba(255,255,255,.75)';
  x.beginPath(); x.arc(56, 64, 24, 0, 7); x.fill();
  x.fillRect(96, 48, 170, 16);
  x.fillStyle = 'rgba(255,255,255,.35)'; x.fillRect(96, 74, 110, 10);
  // [resaltada, ancho, marca: 0 nada · 1 acierto · 2 problema]
  [[0, 250, 0], [1, 200, 1], [0, 270, 0], [0, 180, 2], [1, 240, 1], [0, 220, 0], [0, 160, 2], [1, 230, 1]]
    .forEach(([hl, w, mark], i) => {
      x.fillStyle = hl ? '#FF7A5C' : 'rgba(255,255,255,.3)';
      x.fillRect(40, 130 + i * 40, w, 12);
      if (mark) {
        x.fillStyle = mark === 1 ? '#34D399' : '#FBBF24';
        x.beginPath(); x.arc(310, 136 + i * 40, 9, 0, 7); x.fill();
      }
    });
  const tex = new THREE.CanvasTexture(cv);
  tex.colorSpace = THREE.SRGBColorSpace;
  const side = new THREE.MeshStandardMaterial({ color: 0x2a2f55 });
  const front = new THREE.MeshStandardMaterial({ map: tex, roughness: 0.6 });
  group.add(new THREE.Mesh(new THREE.BoxGeometry(1.5, 2, 0.04), [side, side, side, side, front, side]));

  const lens = new THREE.Group();
  lens.add(new THREE.Mesh(new THREE.TorusGeometry(0.42, 0.05, 24, 64),
    new THREE.MeshStandardMaterial({ color: ACCENT, metalness: 0.9, roughness: 0.25 })));
  const disc = new THREE.Mesh(new THREE.CylinderGeometry(0.4, 0.4, 0.05, 48),
    glass({ transmission: 1, roughness: 0.04, thickness: 0.6, ior: 1.6, color: 0xffffff }));
  disc.rotation.x = Math.PI / 2;
  lens.add(disc);
  const handle = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.07, 0.7, 24),
    new THREE.MeshStandardMaterial({ color: 0x22264a, metalness: 0.6, roughness: 0.35 }));
  handle.position.set(0.55, -0.55, 0);
  handle.rotation.z = Math.PI / 4;
  lens.add(handle);
  lens.position.z = 0.45;
  group.add(lens);

  return (t) => {
    lens.position.x = Math.sin(t * 0.9) * 0.35;
    lens.position.y = Math.sin(t * 1.8) * 0.45 + 0.1;
    lens.rotation.z = Math.sin(t * 0.9) * 0.15;
  };
}

// Adapter: tu CV (vidrio) y el rol (coral) encajan como piezas de puzzle.
function adapter(group) {
  const A = Math.atan2(0.12, -0.16); // ángulo donde el arco de la pestaña toca el borde
  const cvShape = new THREE.Shape();
  cvShape.moveTo(-0.5, -0.5); cvShape.lineTo(0.5, -0.5); cvShape.lineTo(0.5, -0.12);
  cvShape.absarc(0.66, 0, 0.2, -A, A, false); // pestaña hacia afuera
  cvShape.lineTo(0.5, 0.5); cvShape.lineTo(-0.5, 0.5); cvShape.lineTo(-0.5, -0.5);
  const roleShape = new THREE.Shape();
  roleShape.moveTo(-0.5, -0.5); roleShape.lineTo(0.5, -0.5); roleShape.lineTo(0.5, 0.5);
  roleShape.lineTo(-0.5, 0.5); roleShape.lineTo(-0.5, 0.12);
  roleShape.absarc(-0.34, 0, 0.2, A, -A, true); // hueco hacia adentro
  roleShape.lineTo(-0.5, -0.5);

  const opts = { depth: 0.22, bevelEnabled: true, bevelSize: 0.03, bevelThickness: 0.03, bevelSegments: 4, curveSegments: 32 };
  const cvPiece = new THREE.Mesh(new THREE.ExtrudeGeometry(cvShape, opts),
    glass({ color: 0xdfe5ff, transmission: 0.85, roughness: 0.25, thickness: 0.6, clearcoat: 1 }));
  const roleMat = new THREE.MeshPhysicalMaterial({ color: ACCENT, roughness: 0.3, clearcoat: 1, emissive: ACCENT, emissiveIntensity: 0 });
  const rolePiece = new THREE.Mesh(new THREE.ExtrudeGeometry(roleShape, opts), roleMat);
  [-0.22, -0.02, 0.18].forEach((y, i) => {
    const line = new THREE.Mesh(new THREE.BoxGeometry(i ? 0.5 : 0.3, 0.06, 0.02),
      new THREE.MeshStandardMaterial({ color: i === 1 ? ACCENT : 0xffffff, roughness: 0.5 }));
    line.position.set(-0.1, y, 0.27);
    cvPiece.add(line);
  });
  cvPiece.position.z = -0.11;
  const pivot = new THREE.Group();
  pivot.position.x = -0.5; // centra las dos piezas encajadas
  pivot.add(cvPiece, rolePiece);
  group.add(pivot);

  return (t) => {
    const p = (t % 4) / 4;
    const k = p < 0.45 ? 1 - ease(p / 0.45) : p < 0.8 ? 0 : ease((p - 0.8) / 0.2); // entra, encaja, sale
    rolePiece.position.set(1 + k * 0.55, k * 0.3, -0.11 + k * 0.2);
    rolePiece.rotation.z = k * 0.5;
    roleMat.emissiveIntensity = p > 0.45 && p < 0.6 ? (1 - (p - 0.45) / 0.15) * 0.8 : 0;
  };
}

// Jobs: globo de ofertas remotas; los arcos salen de vos hacia tus mejores matches.
function jobs(group) {
  const N = 900;
  const dots = [];
  for (let i = 0; i < N; i++) { // esfera de Fibonacci: puntos parejos sin polos amontonados
    const y = 1 - 2 * (i + 0.5) / N, r = Math.sqrt(1 - y * y), th = i * 2.39996;
    dots.push(Math.cos(th) * r, y, Math.sin(th) * r);
  }
  const dotsGeo = new THREE.BufferGeometry();
  dotsGeo.setAttribute('position', new THREE.Float32BufferAttribute(dots, 3));
  group.add(new THREE.Points(dotsGeo, new THREE.PointsMaterial({ color: 0xaab4ff, size: 0.022, transparent: true, opacity: 0.7 })));
  group.add(new THREE.Mesh(new THREE.SphereGeometry(0.985, 48, 48), new THREE.MeshStandardMaterial({ color: 0x0b0e24, roughness: 0.8 })));

  const latLon = (lat, lon) => {
    const p = lat * Math.PI / 180, l = lon * Math.PI / 180;
    return new THREE.Vector3(Math.cos(p) * Math.cos(l), Math.sin(p), -Math.cos(p) * Math.sin(l));
  };
  const marker = (v, color, size) => {
    const m = new THREE.Mesh(new THREE.SphereGeometry(size, 16, 16), new THREE.MeshBasicMaterial({ color }));
    m.position.copy(v).multiplyScalar(1.01);
    group.add(m);
    return m;
  };
  const me = latLon(-34, -58);
  marker(me, AQUA, 0.04);
  const pulses = [], arcs = [];
  [[40, -74], [51, 0], [52, 13], [37, -122], [1, 103], [-33, 151]].forEach(([lat, lon]) => {
    const v = latLon(lat, lon);
    pulses.push(marker(v, ACCENT, 0.035));
    const mid = me.clone().add(v).normalize().multiplyScalar(1.45);
    const pts = new THREE.QuadraticBezierCurve3(me.clone().multiplyScalar(1.01), mid, v.clone().multiplyScalar(1.01)).getPoints(60);
    const geo = new THREE.BufferGeometry().setFromPoints(pts);
    geo.setDrawRange(0, 0);
    group.add(new THREE.Line(geo, new THREE.LineBasicMaterial({ color: ACCENT, transparent: true, opacity: 0.85 })));
    arcs.push(geo);
  });
  group.scale.setScalar(1.15);

  return (t) => {
    arcs.forEach((geo, i) => geo.setDrawRange(0, Math.floor(Math.min(1, ((t * 0.35 + i / arcs.length) % 1) * 1.6) * 61)));
    pulses.forEach((m, i) => m.scale.setScalar(1 + 0.5 * Math.max(0, Math.sin(t * 3 + i))));
  };
}

// [escena, pose fija en segundos para cuando el sistema pide reducir animaciones]
const SCENES = { evaluator: [evaluator, 0.6], adapter: [adapter, 2.4], jobs: [jobs, 1.86] };

function mount(host, build, pose) {
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  } catch {
    return; // sin WebGL: queda el glifo
  }
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  const canvas = renderer.domElement;
  host.prepend(canvas);

  const scene = new THREE.Scene();
  scene.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;
  const camera = new THREE.PerspectiveCamera(35, 4 / 3, 0.1, 50);
  camera.position.set(0, 0, 4.4);
  const light = new THREE.PointLight(0xffd2c4, 18, 20); // sigue al cursor
  light.position.set(1.5, 1.5, 3);
  scene.add(light, new THREE.AmbientLight(0x8090ff, 0.35));
  const group = new THREE.Group();
  scene.add(group);
  const update = build(group);

  // Arrastrar gira con inercia; si nadie lo toca, gira solo.
  let dragging = false, lastX = 0, lastY = 0, vx = 0, vy = 0, rx = 0.25, ry = -0.4;
  let lastTouch = -Infinity, visible = false;

  function frame(now) {
    if (!dragging) {
      vx *= 0.92; vy *= 0.92;
      ry += vy; rx = clampX(rx + vx);
      if (animated && now - lastTouch > 1500) { ry += 0.004; rx += (0.25 - rx) * 0.01; }
    }
    group.rotation.set(rx, ry, 0);
    update(animated ? now / 1000 : pose);
    renderer.render(scene, camera);
    host.classList.add('is-3d');
    // Con animaciones reducidas el loop corre solo mientras algo se mueve.
    if (!animated && !dragging && Math.abs(vx) + Math.abs(vy) < 1e-4) renderer.setAnimationLoop(null);
  }
  const wake = () => visible && renderer.setAnimationLoop(frame);

  canvas.addEventListener('pointerdown', (e) => {
    dragging = true; lastX = e.clientX; lastY = e.clientY;
    canvas.setPointerCapture(e.pointerId);
    wake();
  });
  const release = () => { dragging = false; lastTouch = performance.now(); };
  canvas.addEventListener('pointerup', release);
  canvas.addEventListener('pointercancel', release); // en táctil, el scroll vertical cancela el arrastre
  canvas.addEventListener('pointermove', (e) => {
    const r = canvas.getBoundingClientRect();
    light.position.x = ((e.clientX - r.left) / r.width - 0.5) * 6;
    light.position.y = -((e.clientY - r.top) / r.height - 0.5) * 4.5;
    if (dragging) {
      vy = (e.clientX - lastX) * 0.008; vx = (e.clientY - lastY) * 0.008;
      lastX = e.clientX; lastY = e.clientY;
      ry += vy; rx = clampX(rx + vx);
      lastTouch = performance.now();
    }
    wake();
  });

  new ResizeObserver(() => {
    renderer.setSize(host.clientWidth, host.clientHeight, false);
    camera.aspect = host.clientWidth / host.clientHeight;
    camera.updateProjectionMatrix();
    wake(); // setSize borra el canvas: redibujar aunque el loop esté quieto
  }).observe(host);
  // Fuera de pantalla no dibuja.
  new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting;
    if (visible) wake(); else renderer.setAnimationLoop(null);
  }).observe(host);
}

const host = document.querySelector('.feature-visual[data-scene]');
const entry = host && SCENES[host.dataset.scene];
if (entry) {
  // Evaluar three bloquea el hilo un rato: se baja con la página ya cargada y el navegador libre.
  const idle = window.requestIdleCallback || ((cb) => setTimeout(cb, 200));
  addEventListener('load', () => idle(async () => {
    [THREE, { RoomEnvironment }] = await Promise.all([import(THREE_URL), import(ROOM_ENV_URL)]);
    mount(host, ...entry);
  }), { once: true });
}
