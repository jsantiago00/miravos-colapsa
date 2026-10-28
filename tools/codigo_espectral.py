#!/usr/bin/env python3
"""Código espectral oculto en los dorsos de Mirá Vos.

Cada dorso lleva dos respuestas: una para medir en el eje Z y otra para el eje X,
cada una SÍ o NO (como en el frente: en Z, SÍ = ↑ y NO = ↓; en X, SÍ = → y NO = ←). Cada una de las 4 respuestas posibles es un "acorde" de K
ondas finas (ciclos/mm, en el marco de la carta) que se suman al dorso en el
eje azul−amarillo, donde el ojo casi no ve detalle fino.

La lectura mira la energía de la imagen en esas frecuencias, no su posición:
no importa dónde esté la carta en el recuadro, y se busca el giro y la escala
que mejor encajan, así que tampoco importa cómo esté girada. Por eso el
resultado es una propiedad de la carta (SÍ/NO), no una dirección sobre ella.

Uso:
  python tools/codigo_espectral.py foto.jpg      # lee una foto (carta en el recuadro central)
  python tools/codigo_espectral.py --elegir      # vuelve a elegir los códigos (cambia todo)
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image

AQUI = Path(__file__).resolve().parent
BASE = AQUI / 'dorso_base.png'

PX_MM = 300 / 25.4
CARTA_MM = 40.0
P = 256                       # lado al que se lleva la carta para leer
BIN = CARTA_MM                # bins de FFT por ciclo/mm
BANDA = (0.5, 0.8)            # ciclos/mm: rayitas de 1,25 a 2 mm
K = 3                         # ondas por respuesta
GUIA = 0.72                   # el recuadro guía de la app: 72% del lado menor
LUM_COMP = 0.0722 / (0.2126 + 0.7152)   # R y G compensan la luminancia del cambio en B

# Elegidos con `--elegir` sobre dorso_base.png. La app tiene la misma tabla.
CODIGOS = {
    'z_si': [(0.5613, 0.0990), (0.2847, 0.7047), (-0.7210, 0.1665)],
    'z_no': [(0.1030, 0.7328), (0.6390, 0.2326), (0.7238, 0.1539)],
    'x_si': [(-0.2134, 0.6981), (-0.5501, 0.3997), (-0.6954, 0.2531)],
    'x_no': [(-0.3009, 0.7088), (0.7034, 0.3132), (-0.5843, 0.0821)],
}

# Búsqueda de giro y escala al leer
GIROS = np.radians(np.arange(0, 180, 1.5))
ESCALAS = np.arange(0.88, 1.121, 0.03)

# z = diferencia SÍ−NO en unidades de ruido. En simulación (giro libre, desenfoque,
# luz despareja, video 4:2:0 o JPEG 90): con código z ≥ 11 aun a 3 niveles; sin
# código z ≤ 4. Revisar con la hoja de prueba impresa.
Z_SEGURO, Z_DUDOSO = 8.0, 5.0


# ---------- Utilidades ----------

def gauss(img, sigma_px):
    """Desenfoque gaussiano por FFT."""
    h, w = img.shape
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.rfftfreq(w)[None, :]
    return np.fft.irfft2(np.fft.rfft2(img) * np.exp(-2 * (np.pi * sigma_px) ** 2 * (fx ** 2 + fy ** 2)), s=img.shape)


def max3(E):
    """Máximo en la vecindad 3 × 3 (tolera medio bin de error en giro/escala)."""
    out = E.copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            out = np.maximum(out, np.roll(np.roll(E, dy, 0), dx, 1))
    return out


def radio_bins():
    f = np.fft.fftfreq(P) * P
    return np.hypot(*np.meshgrid(f, f)) / BIN


# ---------- Escritura ----------

def codificar(rgb, z, x, amp, semilla):
    """Suma al dorso (array H × W × 3, 300 dpi, centrado en la carta) los
    acordes de las dos respuestas, con fases al azar. amp = desvío del código
    en niveles del canal azul."""
    rng = np.random.default_rng(semilla)
    n = rgb.shape[0]
    mmc = (np.arange(n) - n / 2) / PX_MM
    X, Y = np.meshgrid(mmc, mmc)
    code = np.zeros((n, n))
    for nombre in (f'z_{z}', f'x_{x}'):
        for fx, fy in CODIGOS[nombre]:
            code += np.cos(2 * np.pi * (fx * X + fy * Y) + rng.uniform(0, 2 * np.pi))
    code *= amp / code.std()
    out = rgb.astype(float).copy()
    out[..., 2] += code
    out[..., 0] -= LUM_COMP * code
    out[..., 1] -= LUM_COMP * code
    return np.clip(np.rint(out), 0, 255).astype(np.uint8)


# ---------- Lectura ----------

def preparar(carta):
    """Carta P × P × 3 → canal azul−amarillo sin fondo, sin los trazos del
    dibujo y con ventana. Los trazos se detectan por luminancia: el código está
    compensado para no cambiarla, así que el umbral puede ser bajo. El fondo se
    estima solo con lo que queda (convolución normalizada), para que los trazos
    no dejen halo."""
    C = carta[..., 2] - (carta[..., 0] + carta[..., 1]) / 2
    Y = carta @ np.array([0.2126, 0.7152, 0.0722])
    mm_px = P / CARTA_MM
    trazo = np.abs(Y - gauss(Y, 0.5 * mm_px)) > 6
    libre = (gauss(trazo.astype(float), 0.3 * mm_px) < 0.05).astype(float)
    fondo = gauss(C * libre, mm_px) / np.maximum(gauss(libre, mm_px), 1e-3)
    C = (C - fondo) * libre
    w = np.hanning(P)
    return C * np.outer(w, w)


def espectro(carta):
    return np.abs(np.fft.fft2(preparar(carta))) ** 2


def leer_carta(carta):
    """carta: array P × P × 3 (la carta cortada llenando el cuadro).
    Devuelve {'z': ('si'|'no', z), 'x': (...)}."""
    E = espectro(carta)
    anillo = (radio_bins() > BANDA[0]) & (radio_bins() < BANDA[1])
    mu = E[anillo].mean()
    E = max3(E) / mu
    tabla = {k: np.array(v) for k, v in CODIGOS.items()}
    mejor = None
    for th in GIROS:
        c, s = np.cos(th), np.sin(th)
        for sc in ESCALAS:
            e = {}
            for k, fs in tabla.items():
                gx = sc * BIN * (c * fs[:, 0] - s * fs[:, 1])
                gy = sc * BIN * (s * fs[:, 0] + c * fs[:, 1])
                e[k] = E[np.rint(gy).astype(int) % P, np.rint(gx).astype(int) % P].sum()
            total = max(e['z_si'], e['z_no']) + max(e['x_si'], e['x_no'])
            if mejor is None or total > mejor[0]:
                mejor = (total, e)
    e = mejor[1]
    res = {}
    for eje in ('z', 'x'):
        z = (e[f'{eje}_si'] - e[f'{eje}_no']) / np.sqrt(2 * K)
        res[eje] = ('si' if z > 0 else 'no', abs(z))
    return res


def leer_foto(ruta):
    """Lee una foto con la carta en el recuadro central, como en la app."""
    im = Image.open(ruta).convert('RGB')
    s = round(min(im.size) * GUIA)
    x, y = (im.width - s) // 2, (im.height - s) // 2
    carta = np.asarray(im.crop((x, y, x + s, y + s)).resize((P, P), Image.BILINEAR)).astype(float)
    return leer_carta(carta)


def veredicto(z):
    return 'segura' if z >= Z_SEGURO else 'dudosa' if z >= Z_DUDOSO else 'no se lee'


# ---------- Elección de los códigos ----------

def elegir(semilla=42, intentos=2000):
    """Elige 4 acordes de K frecuencias donde el dibujo base casi no tiene
    energía, lejos de 0°/45°/90° (ejes de impresora y cámara), separados entre
    sí, y tales que ningún giro ni escala haga coincidir más de una onda de un
    acorde con las de otro (así ningún acorde se confunde con otro girado)."""
    base = np.asarray(Image.open(BASE).convert('RGB')).astype(float)
    corte = round(2 * PX_MM)
    carta = np.asarray(Image.fromarray(base[corte:-corte, corte:-corte].astype(np.uint8))
                       .resize((P, P), Image.LANCZOS)).astype(float)
    e_dis = max3(max3(espectro(carta)))

    cand = []
    for r in np.arange(BANDA[0] + 0.02, BANDA[1] - 0.02, 0.01):
        for a in np.radians(np.arange(0, 180, 1.0)):
            d = np.degrees(a) % 45
            if min(d, 45 - d) < 7:
                continue
            f = np.array([r * np.cos(a), r * np.sin(a)])
            cand.append((e_dis[int(round(f[1] * BIN)) % P, int(round(f[0] * BIN)) % P], f))
    cand.sort(key=lambda t: t[0])
    cand = [f for _, f in cand[:len(cand) * 3 // 10]]

    rng = np.random.default_rng(semilla)
    giros = np.radians(np.arange(0, 180, 1.0))
    escalas = np.arange(0.85, 1.151, 0.01)

    def coinciden(A, B):
        peor = 0
        for th in giros:
            c, s = np.cos(th), np.sin(th)
            for sc in escalas:
                ra = sc * np.stack([c * A[:, 0] - s * A[:, 1], s * A[:, 0] + c * A[:, 1]], 1)
                n = 0
                for p in ra:
                    if min(np.min(np.hypot(*(B - p).T)), np.min(np.hypot(*(B + p).T))) < 0.04:
                        n += 1
                peor = max(peor, n)
        return peor

    for _ in range(intentos):
        orden = rng.permutation(len(cand))
        usadas, sets = [], []
        for i in orden:
            f = cand[i]
            if all(min(np.hypot(*(f - g)), np.hypot(*(f + g))) > 0.08 for g in usadas):
                usadas.append(f)
                if len(usadas) == 4 * K:
                    break
        if len(usadas) < 4 * K:
            continue
        sets = [np.array(usadas[i * K:(i + 1) * K]) for i in range(4)]
        if all(coinciden(sets[i], sets[j]) <= 1 for i in range(4) for j in range(4) if i != j):
            return dict(zip(('z_si', 'z_no', 'x_si', 'x_no'), sets))
    raise RuntimeError('no se encontraron códigos que cumplan')


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--elegir':
        cods = elegir()
        print('CODIGOS = {')
        for k, v in cods.items():
            print(f"    '{k}': [" + ', '.join(f'({x:.4f}, {y:.4f})' for x, y in v) + '],')
        print('}')
    elif len(sys.argv) > 1:
        for ruta in sys.argv[1:]:
            r = leer_foto(ruta)
            txt = ', '.join(f'eje {e.upper()}: {r[e][0].upper()} (z {r[e][1]:.1f}, {veredicto(r[e][1])})' for e in r)
            print(f'{ruta}: {txt}')
    else:
        print(__doc__)
