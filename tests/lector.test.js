// Test del lector del ID del dorso con cartas sintéticas: node --test tests/
const test = require('node:test');
const assert = require('node:assert/strict');
const L = require('../lector.js');

function mulberry(s) {
  return () => {
    s = (s + 0x6D2B79F5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const NAVY = [19, 32, 60], NARANJA = [241, 179, 60], AZUL = [116, 172, 223], ARO = [72, 112, 154], MESA = [70, 75, 90];

// Color del dorso en (x, y) mm desde el centro de la carta. Dibujo
// simplificado: fondo, aro exterior, pétalos, anillo de puntitos y centro.
function colorDorso(x, y, patron) {
  if (Math.abs(x) > 20 || Math.abs(y) > 20) return MESA;
  const r = Math.hypot(x, y);
  for (let k = 0; k < L.N_PUNTOS; k++) {
    if (!((patron >> k) & 1)) continue;
    const a = k * 2 * Math.PI / L.N_PUNTOS;
    if (Math.hypot(x - L.R_ANILLO * Math.cos(a), y - L.R_ANILLO * Math.sin(a)) < 0.7) return NARANJA;
  }
  if (Math.abs(r - 18.8) < 0.18) return ARO;
  if (r < 2.75 || Math.abs(r - 5.2) < 0.25) return NARANJA;
  for (let k = 0; k < 8; k++) {   // pétalos: elipses de 6 × 3,9 mm centradas a 11 mm
    const a = k * Math.PI / 4, c = Math.cos(a), s = Math.sin(a);
    const u = (x * c + y * s - 11) / 6, v = (-x * s + y * c) / 3.9;
    if (Math.abs(Math.hypot(u, v) - 1) < 0.05) return AZUL;
  }
  return NAVY;
}

// Recorte de P × P como el que lee la app: la carta girada th, a escala esc
// (1 = llena el recuadro), corrida (dx, dy) mm, con luz despareja y ruido.
function recorte(patron, { th = 0, esc = 1, dx = 0, dy = 0, ruido = 6, seed = 1 } = {}) {
  const rnd = mulberry(seed);
  const pxmm = L.P / (L.CARD_MM * L.AMPLIA) * esc, px = new Uint8ClampedArray(L.P * L.P * 4);
  const c = Math.cos(th), s = Math.sin(th);
  for (let j = 0; j < L.P; j++) {
    for (let i = 0; i < L.P; i++) {
      const acc = [0, 0, 0];
      for (const [oi, oj] of [[0.25, 0.25], [0.75, 0.25], [0.25, 0.75], [0.75, 0.75]]) {
        const X = (i + oi - L.P / 2) / pxmm - dx, Y = (j + oj - L.P / 2) / pxmm - dy;
        const col = colorDorso(c * X + s * Y, -s * X + c * Y, patron);
        for (let ch = 0; ch < 3; ch++) acc[ch] += col[ch] / 4;
      }
      const luz = 0.7 + 0.4 * i / L.P, q = (j * L.P + i) * 4;
      for (let ch = 0; ch < 3; ch++) px[q + ch] = acc[ch] * luz + (rnd() - 0.5) * ruido;
      px[q + 3] = 255;
    }
  }
  return px;
}

test('los patrones están a distancia 4 o más entre sí, en cualquier giro', () => {
  assert.equal(L.PATRONES.length, L.N_IDS);
  for (let i = 0; i < L.N_IDS; i++) {
    let puntos = 0;
    for (let k = 0; k < L.N_PUNTOS; k++) puntos += (L.PATRONES[i] >> k) & 1;
    assert.equal(puntos, L.N_PUNTOS - L.HUECOS);
    for (let j = i + 1; j < L.N_IDS; j++) assert.ok(L.distancia(L.PATRONES[i], L.PATRONES[j]) >= 4, `${i + 1} y ${j + 1}`);
  }
});

test('lee el ID de cartas giradas, corridas y de distinto tamaño', () => {
  const rnd = mulberry(42);
  for (let id = 1; id <= L.N_IDS; id += 3) {
    const r = L.read(recorte(L.PATRONES[id - 1], {
      th: rnd() * 2 * Math.PI, esc: 0.88 + rnd() * 0.24, dx: (rnd() - 0.5) * 6, dy: (rnd() - 0.5) * 6, seed: id,
    }));
    assert.equal(r.id, id, `carta ${id}: leyó ${r.id} (${r.level})`);
    assert.equal(r.level, 'sure', `carta ${id}: ${r.level}, margen ${r.margen.toFixed(2)}`);
  }
});

test('un puntito tapado no da otra carta: no se lee', () => {
  // la carta 5 con un puntito libre de más borrado
  const libre = [...Array(L.N_PUNTOS).keys()].find(k => k % 3 && ((L.PATRONES[4] >> k) & 1));
  const r = L.read(recorte(L.PATRONES[4] & ~(1 << libre), { th: 1 }));
  assert.ok(r.level === 'none' || r.id === 5, `leyó la carta ${r.id} (${r.level})`);
});

test('sin carta no se lee', () => {
  const px = new Uint8ClampedArray(L.P * L.P * 4), rnd = mulberry(3);
  for (let q = 0; q < px.length; q += 4) {
    for (let ch = 0; ch < 3; ch++) px[q + ch] = MESA[ch] + (rnd() - 0.5) * 10;
    px[q + 3] = 255;
  }
  assert.equal(L.read(px).level, 'none');
});
