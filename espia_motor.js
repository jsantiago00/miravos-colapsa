// Motor de El Espía: las reglas, sin pantalla ni cámara. Lo usan index.html
// y los tests (node --test tests/). Todo el estado de la partida es JSON, para
// poder guardarlo y retomarlo. Las funciones que sortean reciben rng (por
// defecto Math.random) para que los tests sean deterministas.
//
// Resultados: 'si' | 'no'. Ejes: 'z' | 'x'. Jugadores: índice de asiento
// (el orden de la ronda de la mesa).
(function (raiz) {
  'use strict';

  const CONFIG_BASE = {
    // jugadores → laboratorios, distintos y rondas (siempre hay 1 Observador)
    tabla: {
      4: { labs: 3, distintos: 1, rondas: 4 },
      5: { labs: 4, distintos: 1, rondas: 2 },
      6: { labs: 5, distintos: 2, rondas: 2 },
      7: { labs: 6, distintos: 2, rondas: 2 },
      8: { labs: 7, distintos: 3, rondas: 2 },
    },
    pColapso: [0.10, 0.25],     // prob. de acción si la medición colapsó (se sortea por ronda)
    pSinColapso: [0.10, 0.20],  // prob. de acción si no colapsó
    pAgujero: 0.5,              // Agujero de gusano frente a Par EPR
    debateSeg: 180,
    escaneoSeg: 20,             // tiempo para leer la carta en cada turno
    pausaSeg: 3,                // pausa mínima de las pantallas de turno
  };

  const OTRO = { z: 'x', x: 'z' };
  const azar = (rng, arr) => arr[Math.floor(rng() * arr.length)];
  const entre = (rng, [a, b]) => a + rng() * (b - a);
  const moneda = rng => (rng() < 0.5 ? 'si' : 'no');
  const copia = o => JSON.parse(JSON.stringify(o));

  function mezclar(arr, rng) {
    const a = arr.slice();
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(rng() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  // ---------- Partida y roles ----------
  function crearPartida(nombres, config = CONFIG_BASE, rng = Math.random) {
    const n = nombres.length, fila = config.tabla[n];
    if (!fila) throw new Error(`No hay configuración para ${n} jugadores`);
    if (fila.labs + 1 !== n) throw new Error(`Con ${n} jugadores tiene que haber ${n - 1} laboratorios`);
    if (fila.distintos < 1 || fila.distintos * 2 >= fila.labs) {
      throw new Error('Los distintos tienen que ser al menos 1 y menos de la mitad de los laboratorios');
    }
    const ejeMayoria = rng() < 0.5 ? 'z' : 'x';
    const asientos = mezclar([...Array(n).keys()], rng);
    const obs = asientos[0], labs = asientos.slice(1);
    const distintos = new Set(labs.slice(0, fila.distintos));
    const calibrado = azar(rng, labs);
    const roles = nombres.map((_, i) => (i === obs
      ? { tipo: 'obs', eje: null, distinto: false, calibrado: false }
      : { tipo: 'lab', eje: distintos.has(i) ? OTRO[ejeMayoria] : ejeMayoria,
          distinto: distintos.has(i), calibrado: i === calibrado }));
    return {
      v: 1, config: copia(config), nombres: nombres.slice(), n, rondasTotal: fila.rondas,
      roles, ejeMayoria, inicio: Math.floor(rng() * n), rondas: [], votos: Array(n).fill(null),
    };
  }

  // Orden de la ronda r: arranca un jugador distinto en cada ronda, la
  // dirección se alterna y la carta vuelve al que arrancó.
  function orden(G, r) {
    const n = G.n, s = (G.inicio + r) % n, d = r % 2 === 0 ? 1 : -1, o = [];
    for (let j = 0; j < n; j++) o.push(((s + j * d) % n + n) % n);
    o.push(s);
    return o;
  }

  // ---------- Rondas ----------
  const rondaActual = G => G.rondas[G.rondas.length - 1] || null;
  const rondaTerminada = R => R.turnos.length >= R.orden.length;
  const partidaTerminada = G => G.rondas.length >= G.rondasTotal && rondaTerminada(rondaActual(G));
  const jugadorDeTurno = G => { const R = rondaActual(G); return R.orden[R.turnos.length]; };

  function empezarRonda(G, rng = Math.random) {
    const R0 = rondaActual(G);
    if (R0 && !rondaTerminada(R0)) throw new Error('La ronda anterior no terminó');
    if (G.rondas.length >= G.rondasTotal) throw new Error('Ya se jugaron todas las rondas');
    const R = {
      orden: orden(G, G.rondas.length),
      pc: entre(rng, G.config.pColapso), ps: entre(rng, G.config.pSinColapso),
      carta: null,    // ID de la carta en juego (1 a 48), leído del dorso; solo para chequear que sea la misma
      qubit: null,    // último estado: { eje, res }
      turnos: [],
    };
    G.rondas.push(R);
    return R;
  }

  const mismaCarta = (a, b) => a === b;

  // Una medición verdadera al azar de un laboratorio de la ronda r, para el
  // Observador
  function medicionAlAzar(G, r, rng) {
    const labs = r >= 0 ? G.rondas[r].turnos.filter(t => !t.obs) : [];
    if (!labs.length) return null;
    const t = azar(rng, labs);
    return { ronda: r, k: t.k, p: t.p, res: t.res };
  }

  // Turno del jugador que sigue. lectura = ID del dorso escaneado; no decide
  // nada, solo se compara con la carta en juego. Si no
  // coincide devuelve { error: 'otraCarta' } sin tocar nada; con forzar se
  // sigue igual. La primera medición de la ronda sale al azar.
  function medir(G, lectura, rng = Math.random, forzar = false) {
    const R = rondaActual(G);
    if (!R || rondaTerminada(R)) throw new Error('No hay turno pendiente');
    if (R.carta === null) R.carta = lectura;
    else if (!mismaCarta(R.carta, lectura) && !forzar) return { error: 'otraCarta' };

    const k = R.turnos.length, p = R.orden[k], rol = G.roles[p], antes = R.qubit;
    const t = { k, p, obs: rol.tipo === 'obs', antes, eje: null, res: null,
                colapso: false, accion: null, propio: null, ve: null, dijo: null };

    if (t.obs) {
      // El Observador no mide: el qubit pasa por él sin cambiar, y lo que
      // "habría medido" es el estado en ese momento (lo mismo que el anterior). Ve una medición
      // verdadera de alguien que midió antes en la vuelta.
      // Si arranca la ronda, cuenta como si hubiera medido en el eje de la
      // mayoría y ve ese resultado (propio). Además ve una medición de la
      // ronda anterior; en la primera ronda, nada más.
      const ri = G.rondas.length - 1;
      if (antes) {
        t.eje = antes.eje; t.res = antes.res;
        t.ve = medicionAlAzar(G, ri, rng);
      } else {
        t.eje = G.ejeMayoria; t.res = moneda(rng);
        R.qubit = { eje: t.eje, res: t.res };
        t.propio = t.res;
        t.ve = medicionAlAzar(G, ri - 1, rng);
      }
    } else {
      t.eje = rol.eje;
      if (!antes) t.res = moneda(rng);
      else if (antes.eje === rol.eje) t.res = antes.res;
      else { t.res = moneda(rng); t.colapso = true; }
      R.qubit = { eje: t.eje, res: t.res };
      // Acciones: nunca en la primera medición de la ronda
      if (antes && rng() < (t.colapso ? R.pc : R.ps)) {
        if (rng() < G.config.pAgujero) {
          // Agujero de gusano: la app elige al azar a alguien que ya midió
          // este qubit en la ronda (el Observador incluido), menos uno mismo
          const opciones = [...new Set(R.turnos.map(x => x.p))].filter(q => q !== p);
          const objetivo = azar(rng, opciones);
          const visto = R.turnos.filter(x => x.p === objetivo).pop();
          t.accion = { tipo: 'agujero', objetivo, k: visto.k, res: visto.res };
        } else {
          const prev = R.turnos[k - 1];
          t.accion = { tipo: 'epr', objetivo: prev.p, k: prev.k, res: prev.res };
        }
      }
    }
    R.turnos.push(t);
    return { turno: t };
  }

  const ultimoTurno = G => { const R = rondaActual(G); return R.turnos[R.turnos.length - 1]; };

  // A quién puede mirar el Agujero de gusano del último turno: cualquiera que
  // ya haya medido este qubit en la ronda (el Observador incluido), menos uno
  // mismo. medir() ya elige al azar; esto queda para partidas guardadas con la
  // versión anterior, donde el objetivo lo elegía el jugador.
  function opcionesAgujero(G) {
    const R = rondaActual(G), t = ultimoTurno(G);
    return [...new Set(R.turnos.slice(0, t.k).map(x => x.p))].filter(p => p !== t.p);
  }

  function usarAgujero(G, objetivo) {
    const R = rondaActual(G), t = ultimoTurno(G);
    if (!t.accion || t.accion.tipo !== 'agujero') throw new Error('Este turno no tiene Agujero de gusano');
    if (t.accion.objetivo !== null) return t.accion;
    if (!opcionesAgujero(G).includes(objetivo)) throw new Error('Ese jugador no midió este qubit');
    const visto = R.turnos.slice(0, t.k).filter(x => x.p === objetivo).pop();
    Object.assign(t.accion, { objetivo, k: visto.k, res: visto.res });
    return t.accion;
  }

  // Lo que dijo cada uno en voz alta (opcional, se carga al final)
  function anotarDicho(G, r, k, valor) {
    G.rondas[r].turnos[k].dijo = valor;
  }

  // ---------- Votación ----------
  function votar(G, votante, elegido) {
    if (votante === elegido) throw new Error('No podés votarte a vos mismo');
    if (elegido < 0 || elegido >= G.n) throw new Error('Voto inválido');
    G.votos[votante] = elegido;
  }

  // Si el más votado (sin empate) es un distinto, ganan la mayoría y el
  // Observador. Si no, o si hay empate, ganan los distintos.
  function resultado(G) {
    const cuenta = Array(G.n).fill(0);
    G.votos.forEach(v => { if (v !== null) cuenta[v]++; });
    const max = Math.max(...cuenta);
    const top = cuenta.map((c, i) => (c === max ? i : -1)).filter(i => i >= 0);
    const ganaMayoria = top.length === 1 && G.roles[top[0]].distinto;
    return { cuenta, top, empate: top.length > 1, gana: ganaMayoria ? 'mayoria' : 'distintos' };
  }

  const Motor = {
    CONFIG_BASE, OTRO, crearPartida, orden, rondaActual, rondaTerminada, partidaTerminada,
    jugadorDeTurno, empezarRonda, medir, ultimoTurno, opcionesAgujero, usarAgujero,
    anotarDicho, votar, resultado, mismaCarta,
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = Motor;
  else raiz.Motor = Motor;
})(typeof window !== 'undefined' ? window : globalThis);
