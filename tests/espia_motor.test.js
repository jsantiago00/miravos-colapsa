// Tests del motor de El Espía: node --test tests/
const test = require('node:test');
const assert = require('node:assert/strict');
const M = require('../espia_motor.js');

const NOMBRES = ['Ada', 'Bruno', 'Caro', 'Dani', 'Eli', 'Fede', 'Gabi', 'Hugo'];

// rng que devuelve los valores dados en orden y después `resto`
const guion = (vals, resto = 0.99) => { let i = 0; return () => (i < vals.length ? vals[i++] : resto); };
// rng sembrado (mulberry32)
function sembrado(s) {
  return () => {
    s |= 0; s = (s + 0x6D2B79F5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Partida armada a mano: ejes por asiento ('z' | 'x' | 'obs'), mayoría en Z,
// arranca el asiento 0. Probabilidades de acción fijas en cada ronda.
function partida(ejes, { pc = 0, ps = 0, pAgujero = 0.5, inicio = 0 } = {}) {
  const n = ejes.length;
  const config = { ...M.CONFIG_BASE, pColapso: [pc, pc], pSinColapso: [ps, ps], pAgujero };
  const G = M.crearPartida(NOMBRES.slice(0, n), config, sembrado(1));
  G.ejeMayoria = 'z';
  G.inicio = inicio;
  G.roles = ejes.map(e => (e === 'obs'
    ? { tipo: 'obs', eje: null, distinto: false, calibrado: false }
    : { tipo: 'lab', eje: e, distinto: e !== 'z', calibrado: false }));
  return G;
}

const CARTA = 17;   // ID del dorso en juego

// ---------- Reparto ----------
test('reparto según la tabla, para cada cantidad de jugadores', () => {
  for (const [n, fila] of Object.entries(M.CONFIG_BASE.tabla)) {
    for (let s = 1; s <= 30; s++) {
      const G = M.crearPartida(NOMBRES.slice(0, +n), M.CONFIG_BASE, sembrado(s));
      const obs = G.roles.filter(r => r.tipo === 'obs');
      const labs = G.roles.filter(r => r.tipo === 'lab');
      assert.equal(obs.length, 1);
      assert.equal(labs.length, fila.labs);
      assert.equal(labs.filter(r => r.distinto).length, fila.distintos);
      assert.equal(G.roles.filter(r => r.calibrado).length, 1);
      assert.equal(G.roles.find(r => r.calibrado).tipo, 'lab');
      for (const r of labs) assert.equal(r.eje, r.distinto ? M.OTRO[G.ejeMayoria] : G.ejeMayoria);
      assert.equal(G.rondasTotal, fila.rondas);
    }
  }
});

test('la tabla es configurable y se valida', () => {
  const config = { ...M.CONFIG_BASE, tabla: { 4: { labs: 3, distintos: 1, rondas: 3 } } };
  assert.equal(M.crearPartida(NOMBRES.slice(0, 4), config).rondasTotal, 3);
  assert.throws(() => M.crearPartida(NOMBRES.slice(0, 5), config));
  const mal = { ...M.CONFIG_BASE, tabla: { 4: { labs: 3, distintos: 2, rondas: 2 } } };
  assert.throws(() => M.crearPartida(NOMBRES.slice(0, 4), mal));
});

test('orden: pasa por todos, vuelve al que arrancó, alterna dirección y cambia de inicio', () => {
  const G = partida(['z', 'z', 'x', 'obs', 'z'], { inicio: 2 });
  const o0 = M.orden(G, 0), o1 = M.orden(G, 1);
  assert.deepEqual(o0, [2, 3, 4, 0, 1, 2]);
  assert.deepEqual(o1, [3, 2, 1, 0, 4, 3]);
  for (const o of [o0, o1]) {
    assert.equal(o.length, G.n + 1);
    assert.equal(new Set(o).size, G.n);
    assert.equal(o[0], o[o.length - 1]);
  }
});

// ---------- Estado del qubit ----------
test('primera medición: sale al azar 50/50, sin importar el dorso', () => {
  const rng = sembrado(11);
  for (const eje of ['z', 'x']) {
    const vistos = { si: 0, no: 0 };
    for (let i = 0; i < 2000; i++) {
      const G = partida([eje, 'z', 'z', 'obs']);
      M.empezarRonda(G, rng);
      const { turno } = M.medir(G, CARTA, rng);
      assert.equal(turno.colapso, false);
      assert.equal(turno.accion, null);
      assert.deepEqual(M.rondaActual(G).qubit, { eje, res: turno.res });
      vistos[turno.res]++;
    }
    assert.ok(Math.abs(vistos.si - 1000) < 120, JSON.stringify(vistos));
  }
  // el dorso solo identifica la carta: queda guardado para el chequeo
  const G = partida(['z', 'z', 'z', 'obs']);
  M.empezarRonda(G);
  M.medir(G, CARTA);
  assert.equal(M.rondaActual(G).carta, CARTA);
});

test('mismo eje que la última medición: mismo resultado', () => {
  const G = partida(['x', 'x', 'z', 'obs']);
  M.empezarRonda(G);
  const t0 = M.medir(G, CARTA).turno;
  for (let i = 0; i < 20; i++) {
    const G2 = JSON.parse(JSON.stringify(G));
    const { turno } = M.medir(G2, CARTA, sembrado(i + 1));
    assert.equal(turno.res, t0.res);
    assert.equal(turno.colapso, false);
  }
});

test('otro eje: colapsa al azar 50/50 y actualiza el estado', () => {
  const G = partida(['z', 'x', 'z', 'obs']);
  M.empezarRonda(G);
  M.medir(G, CARTA);
  const vistos = { si: 0, no: 0 };
  const rng = sembrado(7);
  for (let i = 0; i < 2000; i++) {
    const G2 = JSON.parse(JSON.stringify(G));
    const { turno } = M.medir(G2, CARTA, rng);
    assert.equal(turno.colapso, true);
    assert.deepEqual(M.rondaActual(G2).qubit, { eje: 'x', res: turno.res });
    vistos[turno.res]++;
  }
  assert.ok(Math.abs(vistos.si - 1000) < 120, JSON.stringify(vistos));
});

test('dorso distinto: avisa y no toca nada; forzando sigue con la carta en juego', () => {
  const G = partida(['z', 'x', 'z', 'obs']);
  M.empezarRonda(G);
  M.medir(G, CARTA);
  const antes = JSON.stringify(G);
  assert.deepEqual(M.medir(G, 23), { error: 'otraCarta' });
  assert.equal(JSON.stringify(G), antes);
  const { turno } = M.medir(G, 23, Math.random, true);
  assert.equal(turno.k, 1);
  assert.equal(M.rondaActual(G).carta, CARTA);
});

// ---------- Acciones ----------
test('acciones: nunca en la primera medición, aunque la probabilidad sea 1', () => {
  const G = partida(['z', 'x', 'z', 'obs'], { pc: 1, ps: 1 });
  M.empezarRonda(G);
  assert.equal(M.medir(G, CARTA).turno.accion, null);
  assert.notEqual(M.medir(G, CARTA).turno.accion, null);
});

test('acciones: con pColapso si colapsó y con pSinColapso si no', () => {
  // colapso: pc = 1, ps = 0 → siempre acción
  let G = partida(['z', 'x', 'z', 'obs'], { pc: 1, ps: 0 });
  M.empezarRonda(G); M.medir(G, CARTA);
  assert.notEqual(M.medir(G, CARTA).turno.accion, null);
  // sin colapso: pc = 1, ps = 0 → nunca
  G = partida(['z', 'z', 'z', 'obs'], { pc: 1, ps: 0 });
  M.empezarRonda(G); M.medir(G, CARTA);
  assert.equal(M.medir(G, CARTA).turno.accion, null);
  // sin colapso: pc = 0, ps = 1 → siempre
  G = partida(['z', 'z', 'z', 'obs'], { pc: 0, ps: 1 });
  M.empezarRonda(G); M.medir(G, CARTA);
  assert.notEqual(M.medir(G, CARTA).turno.accion, null);
});

test('las probabilidades por ronda se sortean dentro de los rangos', () => {
  const G = M.crearPartida(NOMBRES.slice(0, 4), M.CONFIG_BASE, sembrado(3));
  const rng = sembrado(9);
  for (let i = 0; i < 200; i++) {
    G.rondas = [];
    const R = M.empezarRonda(G, rng);
    assert.ok(R.pc >= 0.10 && R.pc <= 0.25);
    assert.ok(R.ps >= 0.10 && R.ps <= 0.20);
  }
});

test('Par EPR: muestra lo que midió de verdad el que pasó la carta', () => {
  const G = partida(['z', 'x', 'z', 'obs'], { ps: 1, pc: 1, pAgujero: 0 });
  M.empezarRonda(G);
  const t0 = M.medir(G, CARTA).turno;
  const { turno } = M.medir(G, CARTA);
  assert.equal(turno.accion.tipo, 'epr');
  assert.equal(turno.accion.objetivo, 0);
  assert.equal(turno.accion.res, t0.res);
});

test('Agujero de gusano: la app elige al azar a alguien que ya midió en la ronda, y muestra la verdad', () => {
  for (let rep = 0; rep < 30; rep++) {
    const G = partida(['z', 'x', 'z', 'obs'], { ps: 1, pc: 1, pAgujero: 1 });
    M.empezarRonda(G);
    const t0 = M.medir(G, CARTA).turno;  // Ada (z)
    const t1 = M.medir(G, CARTA).turno;  // Bruno (x)
    assert.equal(t1.accion.tipo, 'agujero');
    assert.equal(t1.accion.objetivo, 0);
    assert.equal(t1.accion.res, t0.res);
    const t2 = M.medir(G, CARTA).turno;  // Caro (z)
    assert.ok([0, 1].includes(t2.accion.objetivo));
    assert.equal(t2.accion.res, [t0, t1][t2.accion.objetivo].res);
  }
});

test('Agujero de gusano: con el tiempo elige a todos los posibles', () => {
  const vistos = new Set();
  for (let rep = 0; rep < 60; rep++) {
    const G = partida(['z', 'x', 'z', 'obs'], { ps: 1, pc: 1, pAgujero: 1 });
    M.empezarRonda(G);
    M.medir(G, CARTA); M.medir(G, CARTA);
    vistos.add(M.medir(G, CARTA).turno.accion.objetivo);
  }
  assert.deepEqual([...vistos].sort(), [0, 1]);
});

test('Agujero de gusano en la vuelta final: el que arrancó no se elige a sí mismo', () => {
  for (let rep = 0; rep < 30; rep++) {
    const G = partida(['z', 'x', 'z', 'obs'], { ps: 1, pc: 1, pAgujero: 1 });
    M.empezarRonda(G);
    for (let i = 0; i < 4; i++) M.medir(G, CARTA);
    const { turno } = M.medir(G, CARTA);   // Ada otra vez
    assert.equal(turno.p, 0);
    assert.ok([1, 2, 3].includes(turno.accion.objetivo));
  }
});

// ---------- Observador ----------
test('el Observador no cambia el estado del qubit', () => {
  const G = partida(['z', 'x', 'obs', 'z'], { pc: 1, ps: 1 });
  M.empezarRonda(G);
  M.medir(G, CARTA);
  M.medir(G, CARTA);
  const R = M.rondaActual(G), antes = { ...R.qubit };
  const { turno } = M.medir(G, CARTA);   // Observador
  assert.equal(turno.obs, true);
  assert.deepEqual(R.qubit, antes);
  assert.equal(turno.accion, null);
  // lo que "habría medido" es el estado en ese momento
  assert.equal(turno.eje, antes.eje);
  assert.equal(turno.res, antes.res);
});

test('Observador elegido por un Agujero de gusano o un Par EPR: muestra el estado de ese momento', () => {
  let G = partida(['z', 'x', 'obs', 'z'], { pc: 1, ps: 1, pAgujero: 1 });
  M.empezarRonda(G);
  M.medir(G, CARTA);
  const t1 = M.medir(G, CARTA).turno;
  M.medir(G, CARTA);   // Observador
  const vistos = new Set();
  for (let rep = 0; rep < 60; rep++) {
    const H = JSON.parse(JSON.stringify(G));
    const t3 = M.medir(H, CARTA).turno;   // Dani
    vistos.add(t3.accion.objetivo);
    if (t3.accion.objetivo === 2) assert.equal(t3.accion.res, t1.res);
  }
  assert.ok(vistos.has(2));

  G = partida(['z', 'x', 'obs', 'z'], { pc: 1, ps: 1, pAgujero: 0 });
  M.empezarRonda(G);
  M.medir(G, CARTA);
  const u1 = M.medir(G, CARTA).turno;
  M.medir(G, CARTA);
  const u3 = M.medir(G, CARTA).turno;
  assert.equal(u3.accion.objetivo, 2);
  assert.equal(u3.accion.res, u1.res);
});

test('el Observador ve una medición verdadera de antes en la vuelta', () => {
  const G = partida(['z', 'x', 'obs', 'z']);
  M.empezarRonda(G);
  const t0 = M.medir(G, CARTA).turno, t1 = M.medir(G, CARTA).turno;
  for (let s = 1; s <= 20; s++) {
    const G2 = JSON.parse(JSON.stringify(G));
    const { ve } = M.medir(G2, CARTA, sembrado(s)).turno;
    const real = [t0, t1].find(t => t.p === ve.p);
    assert.ok(real);
    assert.equal(ve.ronda, 0);
    assert.equal(ve.res, real.res);
  }
});

test('Observador que arranca: cuenta como medición en el eje de la mayoría, y la ve', () => {
  const G = partida(['obs', 'z', 'x', 'z'], { pc: 1, ps: 1 });
  M.empezarRonda(G);
  const t0 = M.medir(G, CARTA).turno;
  assert.equal(t0.obs, true);
  assert.equal(t0.propio, t0.res);
  assert.deepEqual(M.rondaActual(G).qubit, { eje: 'z', res: t0.res });
  const t1 = M.medir(G, CARTA).turno;       // mayoría (z): mismo resultado, sin colapso
  assert.equal(t1.res, t0.res);
  assert.equal(t1.colapso, false);
  assert.notEqual(t1.accion, null);          // ya hubo una "medición" antes
});

test('Observador que arranca: en la ronda 1 no ve nada más; después, una medición de la ronda anterior', () => {
  const G = partida(['obs', 'z', 'x', 'z']);
  M.empezarRonda(G);
  const t0 = M.medir(G, CARTA).turno;
  assert.equal(t0.ve, null);
  for (let i = 1; i < 5; i++) M.medir(G, CARTA);
  // ronda 2 armada para que arranque de nuevo el Observador
  G.inicio = 0;
  G.rondas.push({ ...M.rondaActual(G), orden: [0, 3, 2, 1, 0], carta: null, qubit: null, turnos: [] });
  const r2 = M.medir(G, CARTA).turno;
  assert.notEqual(r2.propio, null);
  assert.equal(r2.ve.ronda, 0);
  assert.equal(G.roles[r2.ve.p].tipo, 'lab');
  assert.equal(r2.ve.res, G.rondas[0].turnos[r2.ve.k].res);
});

test('Observador que arranca: al cerrar la vuelta ve a un laboratorio de esta ronda', () => {
  const G = partida(['obs', 'z', 'x', 'z']);
  M.empezarRonda(G);
  for (let i = 0; i < 4; i++) M.medir(G, CARTA);
  const cierre = M.medir(G, CARTA).turno;
  assert.equal(cierre.p, 0);
  assert.equal(cierre.propio, null);
  assert.equal(cierre.ve.ronda, 0);
  assert.notEqual(G.roles[cierre.ve.p].tipo, 'obs');
  assert.equal(cierre.ve.res, M.rondaActual(G).turnos[cierre.ve.k].res);
});

// ---------- Votación ----------
test('votación: nadie se vota a sí mismo; gana la mayoría si el más votado es distinto', () => {
  const G = partida(['z', 'x', 'z', 'obs']);
  assert.throws(() => M.votar(G, 1, 1));
  [1, 0, 1, 1].forEach((v, i) => M.votar(G, i, v));
  assert.equal(M.resultado(G).gana, 'mayoria');
  [2, 0, 1, 2].forEach((v, i) => M.votar(G, i, v));
  assert.equal(M.resultado(G).gana, 'distintos');
});

test('votación: con empate ganan los distintos; con varios distintos alcanza con uno', () => {
  let G = partida(['z', 'x', 'z', 'obs']);
  [1, 0, 0, 1].forEach((v, i) => M.votar(G, i, v));
  const r = M.resultado(G);
  assert.equal(r.empate, true);
  assert.equal(r.gana, 'distintos');

  G = partida(['z', 'x', 'z', 'x', 'z', 'obs']);
  [3, 0, 3, 1, 3, 3].forEach((v, i) => M.votar(G, i, v));
  assert.equal(M.resultado(G).gana, 'mayoria');
});

// ---------- Persistencia ----------
test('la partida se puede guardar y retomar a mitad de ronda', () => {
  const rng = sembrado(42);
  const G = M.crearPartida(NOMBRES.slice(0, 6), M.CONFIG_BASE, rng);
  M.empezarRonda(G, rng);
  M.medir(G, CARTA, rng);
  M.medir(G, CARTA, rng);
  const G2 = JSON.parse(JSON.stringify(G));
  while (!M.rondaTerminada(M.rondaActual(G2))) {
    const { turno } = M.medir(G2, CARTA, rng);
  }
  assert.equal(M.rondaActual(G2).turnos.length, 7);
});
