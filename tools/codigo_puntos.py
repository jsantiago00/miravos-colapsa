#!/usr/bin/env python3
"""ID de cada carta en el anillo de puntitos del dorso de Mirá Vos.

El dorso (tools/dorso_base.png) tiene 24 puntitos naranjas en un anillo de
17,6 mm de radio, uno cada 15°. Los 8 que están en las puntas de los pétalos
(cada 45°) quedan siempre. De los otros 16, cada carta tiene HUECOS puntitos
borrados en un patrón propio: eso es su ID (1 a 48).

A la vista es un anillo con algunos huecos; sin la tabla no se sabe qué carta
es. Para el escáner es fácil: naranja sobre azul marino.

Los patrones se eligen para que entre dos cartas, en cualquier giro, haya al
menos DISTANCIA puntitos distintos. Un puntito mal leído cambia dos (uno que
sobra y uno que falta, porque siempre faltan HUECOS), así que con 4 no se
confunde con otra carta: queda a distancia 2 de todas y la app pide escanear de
nuevo.

La lectura (misma lógica en `leer_carta()` acá y `read()` en lector.js):
  1. Mapa de naranja: R − B.
  2. Busca el centro y el radio del anillo (la carta puede estar corrida,
     girada y más chica o más grande que el recuadro): el círculo donde el
     naranja es más alto que justo adentro y justo afuera.
  3. Encuentra el giro con el armónico 24 del perfil del anillo (los puntitos
     están cada 15°) y mide el naranja en cada una de las 24 posiciones.
  4. Los 24 − HUECOS más naranjas son puntitos; el resto, huecos.
  5. Compara con la tabla en los 24 giros posibles.

Uso:
  python tools/codigo_puntos.py foto.jpg      # lee una foto (carta en el recuadro central)
  python tools/codigo_puntos.py --simular     # lee cartas simuladas con cámara, giro, JPEG…
  python tools/codigo_puntos.py --elegir      # vuelve a elegir los patrones (cambia todo)
"""

import io
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

AQUI = Path(__file__).resolve().parent
BASE = AQUI / 'dorso_base.png'

PX_MM = 300 / 25.4
CARTA_MM = 40.0
GUIA = 0.72                   # el recuadro guía de la app: 72% del lado menor
AMPLIA = 1.3                  # se lee un recorte 30% más grande que el recuadro guía,
                              # por si la carta quedó corrida o más grande
P = 320                       # lado al que se lleva ese recorte para leer
CAMPO_MM = CARTA_MM * AMPLIA  # mm que cubre el recorte si la carta llena el recuadro
N_PUNTOS = 24
R_ANILLO = 17.6               # mm, radio del anillo de puntitos
R_PUNTO = 0.7                 # mm, radio de cada puntito
HUECOS = 7                    # puntitos borrados por carta
DISTANCIA = 4                 # distancia mínima entre patrones, en cualquier giro
N_IDS = 48
FIJOS = [k for k in range(N_PUNTOS) if k % 3 == 0]    # puntas de los pétalos

# Patrón de cada carta: bit k = 1 si está el puntito k (en el ángulo k·15°,
# medido desde la derecha hacia abajo, en coordenadas de imagen). PATRONES[0]
# es la carta 1. Elegidos con `--elegir`. La app (lector.js) tiene la misma tabla.
PATRONES = [
    0x77d6f9, 0xedb76b, 0xb69bfb, 0xeebb6b, 0xfef26b, 0x7df26f,
    0xbfbe59, 0xbdda6f, 0xbcb6fd, 0x7cfe5d, 0xedff49, 0x7793fd,
    0xe5bfcb, 0xe49fef, 0x7f9f59, 0xf6b36f, 0x6fb2df, 0x27ff5d,
    0xaebf6d, 0xbedecb, 0xbfd34f, 0xedde6d, 0x7d9f4f, 0xb7d2fb,
    0xaedfd9, 0xafd6eb, 0xf6d76b, 0x35bfcf, 0x7e976f, 0xe6db7b,
    0xaff379, 0x67f76b, 0x75fa7b, 0xeff34b, 0xb4bf7d, 0x3db7dd,
    0xbe9b6f, 0xbfde69, 0xe7b2fd, 0x7cdef9, 0x3ff2cf, 0xeff25d,
    0xedd3dd, 0xadbbf9, 0xa7d3fd, 0xaebef9, 0x65bf7b, 0xb7f2dd,
]

# Confianza de la lectura
MARGEN_SEGURO = 0.35   # (último puntito − primer hueco) / (media puntitos − media huecos)
CONTRASTE_MIN = 0.35   # (media puntitos − media huecos) / media puntitos


# ---------- Patrones ----------

def girar(m, s):
    """Gira un patrón de 24 bits s posiciones."""
    s %= N_PUNTOS
    return ((m << s) | (m >> (N_PUNTOS - s))) & ((1 << N_PUNTOS) - 1)


def distancia(a, b):
    """Menor cantidad de puntitos distintos entre a y b en cualquier giro."""
    return min(bin(girar(a, s) ^ b).count('1') for s in range(N_PUNTOS))


def elegir(semilla=2026):
    """Elige N_IDS patrones con HUECOS huecos entre los 16 puntitos libres, a
    distancia DISTANCIA o más entre sí en cualquier giro."""
    rng = np.random.default_rng(semilla)
    libres = [k for k in range(N_PUNTOS) if k not in FIJOS]
    lleno = (1 << N_PUNTOS) - 1
    elegidos = []
    for _ in range(200000):
        huecos = rng.choice(libres, HUECOS, replace=False)
        m = lleno
        for k in huecos:
            m &= ~(1 << int(k))
        if all(distancia(m, e) >= DISTANCIA for e in elegidos):
            elegidos.append(m)
            if len(elegidos) == N_IDS:
                return elegidos
    raise RuntimeError(f'solo se encontraron {len(elegidos)} patrones')


def respuestas(cid):
    """Respuestas del juego base de la carta: (eje Z, eje X), cada una 'si' | 'no'.
    29 es coprimo con 48, así que salen 12 cartas de cada combinación."""
    c = (cid * 29 % N_IDS) % 4
    return ('si' if c < 2 else 'no', 'si' if c % 2 == 0 else 'no')


# ---------- Escritura ----------

def marcar(rgb, cid):
    """Borra del dorso (array H × W × 3, 300 dpi, centrado en la carta) los
    puntitos que no van en la carta cid, pintándolos del color del fondo."""
    out = rgb.copy()
    n = rgb.shape[0]
    c = n / 2 - 0.5
    yy, xx = np.mgrid[0:n, 0:n]
    m = PATRONES[cid - 1]
    for k in range(N_PUNTOS):
        if m >> k & 1:
            continue
        a = np.radians(k * 360 / N_PUNTOS)
        px, py = c + R_ANILLO * PX_MM * np.cos(a), c + R_ANILLO * PX_MM * np.sin(a)
        d = np.hypot(xx - px, yy - py)
        alrededor = (d > (R_PUNTO + 0.3) * PX_MM) & (d < (R_PUNTO + 0.8) * PX_MM)
        fondo = np.median(rgb[alrededor], 0)
        out[d < (R_PUNTO + 0.25) * PX_MM] = fondo
    return out


# ---------- Lectura ----------

def caja(a, r):
    """Promedio móvil (2r+1) × (2r+1)."""
    k = 2 * r + 1
    p = np.pad(a, r, mode='edge')
    s = np.cumsum(np.cumsum(p, 0), 1)
    s = np.pad(s, ((1, 0), (1, 0)))
    return (s[k:, k:] - s[:-k, k:] - s[k:, :-k] + s[:-k, :-k]) / (k * k)


def muestrear(a, x, y):
    """Interpolación bilineal de a en (x, y) (arrays de la misma forma)."""
    h, w = a.shape
    x = np.clip(x, 0, w - 1.001)
    y = np.clip(y, 0, h - 1.001)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = x - x0, y - y0
    return (a[y0, x0] * (1 - fx) * (1 - fy) + a[y0, x0 + 1] * fx * (1 - fy)
            + a[y0 + 1, x0] * (1 - fx) * fy + a[y0 + 1, x0 + 1] * fx * fy)


def anillo(o, cx, cy, r, ang):
    """Naranja medio sobre el círculo (cx, cy, r), menos el de los círculos
    justo adentro y justo afuera: alto solo en un anillo fino de puntitos."""
    ca, sa = np.cos(ang), np.sin(ang)
    d = 1.4 * P / CAMPO_MM
    m = lambda rr: muestrear(o, cx[..., None] + rr[..., None] * ca, cy[..., None] + rr[..., None] * sa).mean(-1)
    return m(r) - 0.5 * (m(r - d) + m(r + d))


def leer_carta(carta):
    """carta: array P × P × 3 (el recorte, AMPLIA veces el recuadro guía). Devuelve
    {'id', 'nivel' ('segura' | 'dudosa' | 'no se lee'), 'dist', 'margen',
     'contraste', 'centro', 'radio', 'giro', 'bits'}."""
    mm = P / CAMPO_MM
    o = carta[..., 0] - carta[..., 2]
    ob = caja(o, 2)
    # 1. Centro y radio, primero grueso y después fino
    c0, r0 = P / 2, R_ANILLO * mm
    ang = np.linspace(0, 2 * np.pi, 96, endpoint=False)
    dx = np.arange(-5 * mm, 5 * mm + 0.1, 2.0)
    rs = np.arange(r0 * 0.85, r0 * 1.15, 1.5)
    CX, CY, RR = np.meshgrid(c0 + dx, c0 + dx, rs, indexing='ij')
    s = anillo(ob, CX, CY, RR, ang)
    i = np.unravel_index(s.argmax(), s.shape)
    cx, cy, r = CX[i], CY[i], RR[i]
    fino = np.arange(-2, 2.01, 0.5)
    CX, CY, RR = np.meshgrid(cx + fino, cy + fino, r + fino, indexing='ij')
    ang = np.linspace(0, 2 * np.pi, 360, endpoint=False)
    s = anillo(caja(o, 1), CX, CY, RR, ang)
    i = np.unravel_index(s.argmax(), s.shape)
    cx, cy, r = float(CX[i]), float(CY[i]), float(RR[i])
    # 2. Giro: armónico 24 del perfil del anillo
    ang = np.linspace(0, 2 * np.pi, 720, endpoint=False)
    perfil = muestrear(caja(o, 1), cx + r * np.cos(ang), cy + r * np.sin(ang))
    giro = (-np.angle((perfil * np.exp(-1j * N_PUNTOS * ang)).sum()) / N_PUNTOS) % (2 * np.pi / N_PUNTOS)
    # 3. Naranja en cada posición (centro y cuatro alrededor, a 0,3 mm)
    tk = giro + np.arange(N_PUNTOS) * 2 * np.pi / N_PUNTOS
    off = np.array([[0, 0], [1, 0], [-1, 0], [0, 1], [0, -1]]) * 0.3 * mm
    px = cx + r * np.cos(tk)[:, None] + off[:, 0]
    py = cy + r * np.sin(tk)[:, None] + off[:, 1]
    v = muestrear(o, px, py).mean(1)
    # 4. Los más naranjas son puntitos
    lleno = N_PUNTOS - HUECOS
    orden = np.sort(v)[::-1]
    sep = orden[:lleno].mean() - orden[lleno:].mean()
    margen = (orden[lleno - 1] - orden[lleno]) / max(sep, 1e-6)
    contraste = sep / max(orden[:lleno].mean(), 1e-6)
    umbral = (orden[lleno - 1] + orden[lleno]) / 2
    bits = sum(1 << k for k in range(N_PUNTOS) if v[k] > umbral)
    # 5. La carta más parecida, en cualquier giro
    dists = [distancia(bits, m) for m in PATRONES]
    mejor = int(np.argmin(dists))
    d = dists[mejor]
    if d == 0 and margen >= MARGEN_SEGURO and contraste >= CONTRASTE_MIN:
        nivel = 'segura'
    elif d == 0 and contraste >= CONTRASTE_MIN / 2:
        nivel = 'dudosa'
    else:
        nivel = 'no se lee'
    return {'id': mejor + 1, 'nivel': nivel, 'dist': d, 'margen': float(margen),
            'contraste': float(contraste), 'centro': (cx, cy), 'radio': r, 'giro': float(giro), 'bits': bits}


def recortar_guia(im):
    """Recorta el recuadro guía (agrandado AMPLIA veces) de una imagen PIL, como en la app."""
    s = round(min(im.size) * GUIA * AMPLIA)
    x, y = (im.width - s) // 2, (im.height - s) // 2
    return np.asarray(im.crop((x, y, x + s, y + s)).resize((P, P), Image.BILINEAR)).astype(float)


def leer_foto(ruta):
    """Lee una foto con la carta en el recuadro central, como en la app."""
    return leer_carta(recortar_guia(Image.open(ruta).convert('RGB')))


# ---------- Simulación de cámara ----------

def foto_simulada(dorso, rng, jpeg=85, corrida_mm=3.0):
    """La carta (dorso de 44 mm con sangrado) sobre la mesa, girada, corrida,
    más grande o más chica que el recuadro, desenfocada, con luz despareja
    (y un poco amarillenta), ruido y JPEG 4:2:0, a la resolución con la que la
    app la lee (~292 px el recuadro guía)."""
    lado_guia = 292
    esc = rng.uniform(0.88, 1.12)
    px_mm = lado_guia * esc / CARTA_MM
    n = round(dorso.width * px_mm / PX_MM)
    carta = dorso.resize((n, n), Image.LANCZOS)
    W, H = 720, 405
    mesa = Image.new('RGB', (W, H), tuple(int(v) for v in rng.integers(40, 160, 3)))
    giro = carta.convert('RGBA').rotate(rng.uniform(0, 360), Image.BICUBIC, expand=True)
    corr = corrida_mm * px_mm
    mesa.paste(giro, (int((W - giro.width) / 2 + rng.uniform(-corr, corr)),
                      int((H - giro.height) / 2 + rng.uniform(-corr, corr))), giro)
    mesa = mesa.filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 1.2)))
    a = np.asarray(mesa).astype(float)
    luz = 0.6 + 0.5 * np.linspace(0, 1, W)[None, :, None] * rng.uniform(0.3, 1)
    tinte = np.array([1.0, 0.97, rng.uniform(0.8, 1.0)])     # luz cálida
    a = a * luz * tinte + rng.normal(0, 3, a.shape)
    mesa = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    buf = io.BytesIO()
    mesa.save(buf, 'JPEG', quality=jpeg, subsampling=2)
    return Image.open(io.BytesIO(buf.getvalue())).convert('RGB')


def simular(n=100, semilla=7):
    """Lee n cartas simuladas. Devuelve (seguras bien, dudosas bien, no leídas,
    errores aceptados, lecturas de mesa vacía aceptadas)."""
    rng = np.random.default_rng(semilla)
    base = np.asarray(Image.open(BASE).convert('RGB'))
    cuenta = {'segura': 0, 'dudosa': 0, 'no se lee': 0}
    errores = []
    for i in range(n):
        cid = int(rng.integers(1, N_IDS + 1))
        r = leer_carta(recortar_guia(foto_simulada(Image.fromarray(marcar(base, cid)), rng)))
        if r['nivel'] != 'no se lee' and r['id'] != cid:
            errores.append((cid, r['id'], r['nivel']))
        else:
            cuenta[r['nivel']] += 1
    vacias = 0
    for i in range(max(5, n // 5)):
        mesa = Image.new('RGB', (720, 405), tuple(int(v) for v in rng.integers(30, 200, 3)))
        a = np.asarray(mesa).astype(float) + rng.normal(0, 4, (405, 720, 3))
        r = leer_carta(recortar_guia(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))))
        vacias += r['nivel'] != 'no se lee'
    return cuenta, errores, vacias


def imprimir_patrones(pats):
    print('PATRONES = [')
    for i in range(0, len(pats), 6):
        print('    ' + ', '.join(f'0x{m:06x}' for m in pats[i:i + 6]) + ',')
    print(']')


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--elegir':
        imprimir_patrones(elegir())
    elif len(sys.argv) > 1 and sys.argv[1] == '--simular':
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 100
        cuenta, errores, vacias = simular(n)
        print(f'{n} cartas: {cuenta["segura"]} seguras, {cuenta["dudosa"]} dudosas, '
              f'{cuenta["no se lee"]} sin leer, {len(errores)} con la carta equivocada · '
              f'mesa vacía leída como carta: {vacias}')
        for e in errores:
            print('  error: era', e[0], 'leyó', e[1], f'({e[2]})')
    elif len(sys.argv) > 1:
        for ruta in sys.argv[1:]:
            r = leer_foto(ruta)
            z, x = respuestas(r['id'])
            print(f"{ruta}: carta {r['id']} ({r['nivel']}, distancia {r['dist']}, margen {r['margen']:.2f}) · "
                  f"eje Z {z.upper()}, eje X {x.upper()}")
    else:
        print(__doc__)
