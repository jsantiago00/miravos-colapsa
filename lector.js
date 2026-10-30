// Lector del ID de los dorsos: igual que tools/codigo_puntos.py. Lo usan el
// visor (index.html) y El Espía (espia.html).
//
// El dorso tiene 24 puntitos naranjas en un anillo de 17,6 mm de radio, uno
// cada 15°. Los 8 de las puntas de los pétalos están siempre; de los otros 16,
// cada carta tiene 7 huecos en un patrón propio (PATRONES). La lectura busca
// el anillo (la carta puede estar corrida, girada y más chica o más grande que
// el recuadro), mide qué puntitos están y compara con la tabla en los 24 giros.
(function (raiz) {
  'use strict';

  const MAX_SIDE = 720;
  const GUIDE = 0.72;       // lado del recuadro guía, fracción del lado menor del cuadro
  const AMPLIA = 1.3;       // se lee un recorte 30% más grande que el recuadro guía
  const CARD_MM = 40;       // el recuadro guía es la carta cortada
  const P = 320;            // lado al que se lleva el recorte para leer
  const CAMPO_MM = CARD_MM * AMPLIA;
  const MM = P / CAMPO_MM;  // px por mm si la carta llena el recuadro
  const N_PUNTOS = 24;
  const R_ANILLO = 17.6;    // mm
  const HUECOS = 7;
  const N_IDS = 48;
  // bit k = 1 si está el puntito k (ángulo k·15°, desde la derecha hacia
  // abajo, en coordenadas de imagen). PATRONES[0] es la carta 1.
  const PATRONES = [
    0x77d6f9, 0xedb76b, 0xb69bfb, 0xeebb6b, 0xfef26b, 0x7df26f,
    0xbfbe59, 0xbdda6f, 0xbcb6fd, 0x7cfe5d, 0xedff49, 0x7793fd,
    0xe5bfcb, 0xe49fef, 0x7f9f59, 0xf6b36f, 0x6fb2df, 0x27ff5d,
    0xaebf6d, 0xbedecb, 0xbfd34f, 0xedde6d, 0x7d9f4f, 0xb7d2fb,
    0xaedfd9, 0xafd6eb, 0xf6d76b, 0x35bfcf, 0x7e976f, 0xe6db7b,
    0xaff379, 0x67f76b, 0x75fa7b, 0xeff34b, 0xb4bf7d, 0x3db7dd,
    0xbe9b6f, 0xbfde69, 0xe7b2fd, 0x7cdef9, 0x3ff2cf, 0xeff25d,
    0xedd3dd, 0xadbbf9, 0xa7d3fd, 0xaebef9, 0x65bf7b, 0xb7f2dd,
  ];
  const MARGEN_SEGURO = 0.35;  // (último puntito − primer hueco) / (media puntitos − media huecos)
  const CONTRASTE_MIN = 0.35;  // (media puntitos − media huecos) / media puntitos

  function guideRect(W, H) {
    const s = Math.round(Math.min(W, H) * GUIDE);
    return { x: (W - s) >> 1, y: (H - s) >> 1, s };
  }

  // El recorte que se lee: el recuadro guía agrandado AMPLIA veces
  function readRect(W, H) {
    const s = Math.min(Math.round(Math.min(W, H) * GUIDE * AMPLIA), Math.min(W, H));
    return { x: (W - s) >> 1, y: (H - s) >> 1, s };
  }

  // Tamaño del cuadro de trabajo: el lado mayor a lo sumo MAX_SIDE
  function workSize(w, h) {
    const k = Math.min(1, MAX_SIDE / Math.max(w, h));
    return { W: Math.max(1, Math.round(w * k)), H: Math.max(1, Math.round(h * k)) };
  }

  // ---------- Patrones ----------
  const MASK = (1 << N_PUNTOS) - 1;
  const girar = (m, s) => (((m << s) | (m >>> (N_PUNTOS - s))) & MASK);
  function popcount(x) {
    x -= (x >>> 1) & 0x55555555;
    x = (x & 0x33333333) + ((x >>> 2) & 0x33333333);
    return (((x + (x >>> 4)) & 0x0f0f0f0f) * 0x01010101) >>> 24;
  }
  // Menor cantidad de puntitos distintos entre a y b en cualquier giro
  function distancia(a, b) {
    let d = N_PUNTOS;
    for (let s = 0; s < N_PUNTOS; s++) d = Math.min(d, popcount(girar(a, s) ^ b));
    return d;
  }

  // Respuestas del juego base de la carta (eje Z, eje X): 12 de cada combinación
  function respuestas(id) {
    const c = (id * 29 % N_IDS) % 4;
    return { z: c < 2 ? 'si' : 'no', x: c % 2 === 0 ? 'si' : 'no' };
  }

  // ---------- Utilidades ----------
  const n2 = P * P;
  const O = new Float32Array(n2), O1 = new Float32Array(n2), O2 = new Float32Array(n2);
  const INT = new Float64Array((P + 1) * (P + 1));

  // Promedio móvil (2r+1) × (2r+1) con imagen integral, replicando el borde
  function caja(src, dst, r) {
    const W = P + 1;
    for (let y = 0; y < P; y++) {
      let fila = 0;
      for (let x = 0; x < P; x++) {
        fila += src[y * P + x];
        INT[(y + 1) * W + x + 1] = INT[y * W + x + 1] + fila;
      }
    }
    for (let y = 0; y < P; y++) {
      const y0 = Math.max(0, y - r), y1 = Math.min(P, y + r + 1);
      for (let x = 0; x < P; x++) {
        const x0 = Math.max(0, x - r), x1 = Math.min(P, x + r + 1);
        dst[y * P + x] = (INT[y1 * W + x1] - INT[y0 * W + x1] - INT[y1 * W + x0] + INT[y0 * W + x0])
          / ((y1 - y0) * (x1 - x0));
      }
    }
  }

  function muestra(a, x, y) {
    if (x < 0) x = 0; else if (x > P - 1.001) x = P - 1.001;
    if (y < 0) y = 0; else if (y > P - 1.001) y = P - 1.001;
    const x0 = x | 0, y0 = y | 0, fx = x - x0, fy = y - y0, i = y0 * P + x0;
    return a[i] * (1 - fx) * (1 - fy) + a[i + 1] * fx * (1 - fy) + a[i + P] * (1 - fx) * fy + a[i + P + 1] * fx * fy;
  }

  const angulos = n => {
    const c = new Float64Array(n), s = new Float64Array(n);
    for (let i = 0; i < n; i++) { c[i] = Math.cos(2 * Math.PI * i / n); s[i] = Math.sin(2 * Math.PI * i / n); }
    return { c, s, n };
  };
  const A96 = angulos(96), A360 = angulos(360), A720 = angulos(720);
  const D_ANILLO = 1.4 * MM;

  // Naranja medio sobre el círculo, menos el de los círculos justo adentro y
  // justo afuera: alto solo en un anillo fino de puntitos
  function anillo(a, cx, cy, r, A) {
    let m = 0, adentro = 0, afuera = 0;
    const ri = r - D_ANILLO, re = r + D_ANILLO;
    for (let i = 0; i < A.n; i++) {
      const c = A.c[i], s = A.s[i];
      m += muestra(a, cx + r * c, cy + r * s);
      adentro += muestra(a, cx + ri * c, cy + ri * s);
      afuera += muestra(a, cx + re * c, cy + re * s);
    }
    return (m - 0.5 * (adentro + afuera)) / A.n;
  }

  // ---------- Lectura ----------
  // px: recorte de P × P píxeles RGBA. Devuelve { id, level ('sure' | 'maybe'
  // | 'none'), dist, margen, contraste, cx, cy, r, giro, presentes }.
  function read(px) {
    for (let p = 0, i = 0; p < n2; p++, i += 4) O[p] = px[i] - px[i + 2];   // R − B
    caja(O, O2, 2);
    caja(O, O1, 1);

    // 1. Centro y radio: grueso y después fino
    const c0 = P / 2, r0 = R_ANILLO * MM;
    let best = -Infinity, cx = c0, cy = c0, r = r0;
    for (let dx = -5 * MM; dx <= 5 * MM + 0.1; dx += 2) {
      for (let dy = -5 * MM; dy <= 5 * MM + 0.1; dy += 2) {
        for (let rr = r0 * 0.85; rr < r0 * 1.15; rr += 1.5) {
          const s = anillo(O2, c0 + dx, c0 + dy, rr, A96);
          if (s > best) { best = s; cx = c0 + dx; cy = c0 + dy; r = rr; }
        }
      }
    }
    const gx = cx, gy = cy, gr = r;
    best = -Infinity;
    for (let dx = -2; dx <= 2.01; dx += 0.5) {
      for (let dy = -2; dy <= 2.01; dy += 0.5) {
        for (let dr = -2; dr <= 2.01; dr += 0.5) {
          const s = anillo(O1, gx + dx, gy + dy, gr + dr, A360);
          if (s > best) { best = s; cx = gx + dx; cy = gy + dy; r = gr + dr; }
        }
      }
    }

    // 2. Giro: armónico 24 del perfil del anillo
    let re = 0, im = 0;
    for (let i = 0; i < A720.n; i++) {
      const v = muestra(O1, cx + r * A720.c[i], cy + r * A720.s[i]);
      const t = 2 * Math.PI * i / A720.n * N_PUNTOS;
      re += v * Math.cos(t); im -= v * Math.sin(t);
    }
    const paso = 2 * Math.PI / N_PUNTOS;
    const giro = (((-Math.atan2(im, re) / N_PUNTOS) % paso) + paso) % paso;

    // 3. Naranja en cada posición (centro y cuatro alrededor, a 0,3 mm)
    const off = 0.3 * MM, v = new Float64Array(N_PUNTOS);
    for (let k = 0; k < N_PUNTOS; k++) {
      const t = giro + k * paso, x = cx + r * Math.cos(t), y = cy + r * Math.sin(t);
      v[k] = (muestra(O, x, y) + muestra(O, x + off, y) + muestra(O, x - off, y)
            + muestra(O, x, y + off) + muestra(O, x, y - off)) / 5;
    }

    // 4. Los más naranjas son puntitos
    const lleno = N_PUNTOS - HUECOS;
    const orden = Array.from(v).sort((a, b) => b - a);
    let mp = 0, mh = 0;
    for (let i = 0; i < N_PUNTOS; i++) { if (i < lleno) mp += orden[i]; else mh += orden[i]; }
    mp /= lleno; mh /= HUECOS;
    const sep = mp - mh;
    const margen = (orden[lleno - 1] - orden[lleno]) / Math.max(sep, 1e-6);
    const contraste = sep / Math.max(mp, 1e-6);
    const umbral = (orden[lleno - 1] + orden[lleno]) / 2;
    let bits = 0;
    for (let k = 0; k < N_PUNTOS; k++) if (v[k] > umbral) bits |= 1 << k;

    // 5. La carta más parecida, en cualquier giro
    let id = 1, dist = N_PUNTOS;
    PATRONES.forEach((m, i) => { const d = distancia(bits, m); if (d < dist) { dist = d; id = i + 1; } });
    const level = dist === 0 && margen >= MARGEN_SEGURO && contraste >= CONTRASTE_MIN ? 'sure'
      : dist === 0 && contraste >= CONTRASTE_MIN / 2 ? 'maybe' : 'none';
    const presentes = [];
    for (let k = 0; k < N_PUNTOS; k++) presentes.push((bits >> k) & 1);
    return { id, level, dist, margen, contraste, cx, cy, r, giro, presentes };
  }

  // Recorta de un canvas lo que se lee y lo lee. Devuelve además el recorte
  // (rect, en px del canvas) para dibujar encima.
  let proc = null, pctx = null;
  function readCanvas(cv) {
    if (!proc) {
      proc = document.createElement('canvas');
      proc.width = proc.height = P;
      pctx = proc.getContext('2d', { willReadFrequently: true });
    }
    const g = readRect(cv.width, cv.height);
    pctx.drawImage(cv, g.x, g.y, g.s, g.s, 0, 0, P, P);
    const res = read(pctx.getImageData(0, 0, P, P).data);
    res.rect = g;
    return res;
  }

  const Lector = { MAX_SIDE, GUIDE, AMPLIA, CARD_MM, P, N_PUNTOS, R_ANILLO, HUECOS, N_IDS, PATRONES,
                   guideRect, readRect, workSize, read, readCanvas, respuestas, distancia };
  if (typeof module !== 'undefined' && module.exports) module.exports = Lector;
  else raiz.Lector = Lector;
})(typeof window !== 'undefined' ? window : globalThis);
