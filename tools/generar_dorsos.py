#!/usr/bin/env python3
"""Generador de dorsos de qubits de Mirá Vos con dos flechas ocultas.

Cada dorso es un laberinto de dos colores del juego (violeta y naranja). Las
flechas no cambian el color promedio de ninguna zona: se esconden en la
textura. Sea c = +1 en lo naranja y −1 en lo violeta (la "portadora", que la
app ve como G − B):

  * flecha vertical (↑/↓), filtro rojo: R += amp_r/2 · c · s_v
  * flecha horizontal (→/←), filtro cian: G y B += amp_gb/2 · c · s_h

con s = +1 adentro de la flecha y −1 afuera. Adentro, el naranja queda un poco
más rojo y el violeta un poco menos; afuera, al revés. El promedio es el mismo
en todos lados, así que a simple vista no hay región distinta. La app mide la
pendiente local de R (o de (G+B)/2) contra G − B y ahí aparece la flecha.
G − B no cambia con ninguna de las dos modulaciones, por eso los canales no se
cruzan. `--amp-*` es la diferencia, en niveles sobre 255, entre la misma
mancha adentro y afuera de la flecha.

Salidas (en --salida):
  png/dorso_NN.png     48 dorsos de 520 × 520 px a 300 dpi, en el marco de la
                       carta (marca de orientación arriba a la izquierda).
  dorsos.csv           manifiesto: flechas, rotación y semilla de cada carta.
  pliegos_dorsos.pdf   2 pliegos A4 de 24, espejados para doble faz.
  hoja_prueba.pdf/png  barrido de amplitudes 8/16/24/32 con las respuestas.

Uso:
  python tools/generar_dorsos.py                    # todo, valores por defecto
  python tools/generar_dorsos.py --solo-prueba      # solo la hoja de prueba
  python tools/generar_dorsos.py --amp-r 16 --amp-gb 24 --orientacion B
"""

import argparse
import csv
import zlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

DPI = 300
PX_MM = DPI / 25.4

CARTA_MM = 40.0          # carta cortada
SANGRADO_MM = 2.0
CELDA_MM = CARTA_MM + 2 * SANGRADO_MM
CELDA_PX = 520           # 44 mm a 300 dpi (44.03 mm)

# Pliego A4, igual que el PDF de frentes existente
A4_PX = (2479, 3508)     # 594.96 × 841.92 pt
GRILLA_X_MM = 17.0
GRILLA_Y_MM = 16.5
COLUMNAS, FILAS = 4, 6
POR_PLIEGO = COLUMNAS * FILAS
N_CARTAS = 48

# Paleta del laberinto (colores del juego). Tienen que diferir mucho en G − B,
# que es la portadora que lee la app: −84 contra +103.
VIOLETA = (109, 79, 163)   # #6d4fa3
NARANJA = (233, 162, 59)   # #e9a23b

# Flechas (mm, en el marco de la carta cortada)
FLECHA_LARGO = 28.0      # 70 % del lado
FLECHA_TRONCO = 6.0
FLECHA_CABEZA_ANCHO = 16.0
FLECHA_CABEZA_LARGO = 11.0
FLECHA_BORDE_MM = 1.0      # desenfoque del borde: sin contorno que el ojo enganche

# Camuflaje: el contraste del laberinto varía al azar (±CAMUFLAJE) a escala de
# varios mm. La flecha cambia un poco el contraste de la textura; así ese cambio
# queda perdido entre otros parecidos. No afecta la lectura: escala por igual
# las diferencias de todos los canales, y la app mide su cociente.
CAMUFLAJE = 0.10
CAMUFLAJE_ESCALA_MM = 3.0

# Señuelos: flechas falsas hechas con ese mismo cambio de contraste, en ángulos y
# tamaños al azar, con contraste de más o de menos. A simple vista se ven varias
# flechas parecidas y no hay forma de saber cuál cuenta; la app no las lee.
# Su fuerza se iguala a lo que se nota la flecha real (ver generar_dorso).
SENUELOS_MIN, SENUELOS_MAX = 6, 10

# Marca de orientación: el ojo del logo, en la esquina superior izquierda
MARCA_CENTRO_MM = 5.6    # desde el borde de corte
MARCA_ANCHO_MM = 9.5
MARCA_ALTO_MM = 5.6

NAVY = (20, 29, 58)
CREAM = (243, 238, 226)
SKY = (127, 176, 227)

VERTICALES = ('arriba', 'abajo')
HORIZONTALES = ('derecha', 'izquierda')
FLECHA_GLIFO = {'arriba': '↑', 'abajo': '↓', 'derecha': '→', 'izquierda': '←'}


def mm(v):
    return v * PX_MM


# ---------- Utilidades de imagen ----------

def gauss(img, sigma_px):
    """Desenfoque gaussiano por FFT (bordes periódicos, suficiente para ruido)."""
    h, w = img.shape
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.rfftfreq(w)[None, :]
    k = np.exp(-2 * (np.pi * sigma_px) ** 2 * (fx ** 2 + fy ** 2))
    return np.fft.irfft2(np.fft.rfft2(img) * k, s=img.shape)


def fuente(tam, negrita=False):
    nombres = (('C:/Windows/Fonts/segoeuib.ttf', 'DejaVuSans-Bold.ttf') if negrita
               else ('C:/Windows/Fonts/segoeui.ttf', 'DejaVuSans.ttf'))
    for n in nombres:
        try:
            return ImageFont.truetype(n, tam)
        except OSError:
            pass
    return ImageFont.load_default(size=tam)


# ---------- Dorso ----------

ANGULO = {'arriba': 0, 'derecha': 90, 'abajo': 180, 'izquierda': 270}


def mascara_flecha(direccion, n=CELDA_PX):
    """Máscara 0..1 de la flecha real: centrada, del tamaño completo."""
    return mascara_flecha_libre(ANGULO[direccion], 1.0, n / 2, n / 2, n)


def mascara_flecha_libre(angulo, escala, cx, cy, n=CELDA_PX, ss=4):
    """Máscara 0..1 de una flecha girada `angulo` grados (horario, 0 = arriba),
    escalada y centrada en (cx, cy) px. Antialias por sobremuestreo."""
    big = Image.new('L', (n * ss, n * ss), 0)
    L, t = mm(FLECHA_LARGO) * escala, mm(FLECHA_TRONCO) * escala
    hw, hl = mm(FLECHA_CABEZA_ANCHO) * escala, mm(FLECHA_CABEZA_LARGO) * escala
    # Flecha hacia arriba centrada en el origen
    pts = [(0, -L / 2), (hw / 2, -L / 2 + hl), (t / 2, -L / 2 + hl), (t / 2, L / 2),
           (-t / 2, L / 2), (-t / 2, -L / 2 + hl), (-hw / 2, -L / 2 + hl)]
    a = np.radians(angulo)
    ca, sa = np.cos(a), np.sin(a)
    pts = [((cx + x * ca - y * sa) * ss, (cy + x * sa + y * ca) * ss) for x, y in pts]
    ImageDraw.Draw(big).polygon(pts, fill=255)
    return np.asarray(big.resize((n, n), Image.LANCZOS), dtype=np.float64) / 255


def senuelos(rng, fuerza, n=CELDA_PX):
    """Suma de flechas falsas con signo: ±fuerza adentro de cada una."""
    total = np.zeros((n, n))
    centro_min, centro_max = mm(SANGRADO_MM + 8), mm(SANGRADO_MM + CARTA_MM - 8)
    for i in range(rng.integers(SENUELOS_MIN, SENUELOS_MAX + 1)):
        if i < 3:
            # Grandes y en el centro, como las reales, casi siempre en una
            # dirección cardinal: son los que más confunden
            ang = rng.choice((0, 90, 180, 270)) if rng.random() < 0.75 else rng.uniform(0, 360)
            esc = rng.uniform(0.85, 1.0)
            cx, cy = n / 2 + rng.normal(0, mm(1.5), 2)
        else:
            ang, esc = rng.uniform(0, 360), rng.uniform(0.45, 0.9)
            cx, cy = rng.uniform(centro_min, centro_max, 2)
        m = mascara_flecha_libre(ang, esc, cx, cy, n)
        total += rng.choice((-1, 1)) * rng.uniform(0.7, 1.3) * fuerza * m
    return gauss(total, mm(FLECHA_BORDE_MM))


def laberinto(rng, n=CELDA_PX):
    """Campo t ∈ [0, 1]: 0 = violeta, 1 = naranja.

    Ruido pasabanda umbralado: trazos de ~1 mm, mitad y mitad, del mismo grosor
    en toda la carta. Que no haya zonas lisas importa: la flecha solo se puede
    leer donde hay textura.
    """
    w = rng.standard_normal((n, n))
    f = gauss(w, mm(0.35)) - gauss(w, mm(0.6))
    return 0.5 + 0.5 * np.tanh(4 * f / f.std())


def almendra(cx, cy, ancho, alto, pasos=60):
    """Contorno del ojo del logo: dos parábolas que se tocan en las puntas."""
    pts = []
    for i in range(pasos + 1):
        x = -ancho / 2 + ancho * i / pasos
        pts.append((cx + x, cy - alto / 2 * (1 - (2 * x / ancho) ** 2)))
    for i in range(pasos + 1):
        x = ancho / 2 - ancho * i / pasos
        pts.append((cx + x, cy + alto / 2 * (1 - (2 * x / ancho) ** 2)))
    return pts


def dibujar_marca(img):
    """Ojo del logo en la esquina superior izquierda: almendra crema con borde
    navy, iris celeste y una flechita en la pupila que marca el "arriba"."""
    ss = 4
    n = CELDA_PX
    capa = Image.new('RGBA', (n * ss, n * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    cx = cy = mm(SANGRADO_MM + MARCA_CENTRO_MM) * ss
    ojo = almendra(cx, cy, mm(MARCA_ANCHO_MM) * ss, mm(MARCA_ALTO_MM) * ss)
    d.polygon(ojo, fill=NAVY)
    d.line(ojo + ojo[:1], fill=NAVY, width=round(mm(0.9) * ss), joint='curve')
    d.polygon([(cx + (x - cx) * 0.82, cy + (y - cy) * 0.72) for x, y in ojo], fill=CREAM)
    ri = mm(1.75) * ss
    d.ellipse((cx - ri, cy - ri, cx + ri, cy + ri), fill=SKY)
    rp = ri * 0.58
    d.ellipse((cx - rp, cy - rp, cx + rp, cy + rp), fill=NAVY)
    a = rp * 0.8
    d.polygon([(cx, cy - a), (cx + a * 0.7, cy), (cx + a * 0.28, cy), (cx + a * 0.28, cy + a),
               (cx - a * 0.28, cy + a), (cx - a * 0.28, cy), (cx - a * 0.7, cy)], fill=CREAM)
    img.alpha_composite(capa.resize((n, n), Image.LANCZOS))


def generar_dorso(semilla, vertical, horizontal, amp_r, amp_gb, marca=True):
    """Devuelve un PIL.Image RGB de 520 × 520 en el marco de la carta."""
    rng = np.random.default_rng(semilla)
    t = laberinto(rng)
    c1, c2 = np.array(VIOLETA, float), np.array(NARANJA, float)

    # Contraste del laberinto: camuflaje + señuelos. La flecha real cambia el
    # contraste de luminancia de la textura en ~amp / ΔY (ΔY = diferencia de
    # luminancia violeta–naranja); los señuelos cambian el contraste en eso mismo.
    lum = np.array([0.2126, 0.7152, 0.0722])
    dy = abs(lum @ (c2 - c1))
    fuerza = max(amp_r * lum[0], amp_gb * (lum[1] + lum[2])) / dy
    camo = gauss(rng.standard_normal(t.shape), mm(CAMUFLAJE_ESCALA_MM))
    k = 1 + CAMUFLAJE * np.clip(camo / camo.std(), -1.5, 1.5) + senuelos(rng, fuerza)
    k = np.clip(k, 0.6, 1.4)
    rgb = (c1 + c2) / 2 + (c2 - c1) * ((t - 0.5) * k)[..., None]
    portadora = 2 * t - 1

    # ±1 adentro/afuera de cada flecha, con bordes suaves
    sv = 2 * gauss(mascara_flecha(vertical), mm(FLECHA_BORDE_MM)) - 1
    sh = 2 * gauss(mascara_flecha(horizontal), mm(FLECHA_BORDE_MM)) - 1
    rgb[..., 0] += amp_r / 2 * portadora * sv
    rgb[..., 1] += amp_gb / 2 * portadora * sh
    rgb[..., 2] += amp_gb / 2 * portadora * sh

    # Dither de ±1 nivel para que no haya bandas
    rgb += rng.normal(0, 0.8, rgb.shape)
    img = Image.fromarray(np.clip(np.rint(rgb), 0, 255).astype(np.uint8), 'RGB').convert('RGBA')
    if marca:
        dibujar_marca(img)
    return img.convert('RGB')


# ---------- Asignación balanceada ----------

def asignar(rng, orientacion):
    """48 cartas: 12 por combinación de flechas y, en B, 12 por rotación.

    En B cada par (combinación, rotación) aparece 3 veces, así las flechas no
    dicen nada de la rotación y la rotación no dice nada del frente.
    """
    combos = [(v, h) for v in VERTICALES for h in HORIZONTALES]
    rots = (0, 90, 180, 270) if orientacion == 'B' else (0,)
    pares = [(c, r) for c in combos for r in rots]
    pares = pares * (N_CARTAS // len(pares))
    orden = rng.permutation(len(pares))
    return [pares[i] for i in orden]


# ---------- Pliegos ----------

def celda_xy(fila, col, espejado):
    """Esquina superior izquierda de la celda en px del pliego."""
    c = COLUMNAS - 1 - col if espejado else col
    return round(mm(GRILLA_X_MM + c * CELDA_MM)), round(mm(GRILLA_Y_MM + fila * CELDA_MM))


def marcas_de_corte(d, filas=FILAS, y0_mm=GRILLA_Y_MM):
    """Marcas en los márgenes, alineadas con los bordes de corte de cada carta."""
    largo, sep = mm(5), mm(1)
    grosor = 3
    x_bordes = [GRILLA_X_MM + c * CELDA_MM + SANGRADO_MM + k * CARTA_MM
                for c in range(COLUMNAS) for k in (0, 1)]
    y_bordes = [y0_mm + f * CELDA_MM + SANGRADO_MM + k * CARTA_MM
                for f in range(filas) for k in (0, 1)]
    x_ini, x_fin = mm(GRILLA_X_MM), mm(GRILLA_X_MM + COLUMNAS * CELDA_MM)
    y_ini, y_fin = mm(y0_mm), mm(y0_mm + filas * CELDA_MM)
    for xm in x_bordes:
        x = mm(xm)
        d.line((x, y_ini - sep - largo, x, y_ini - sep), fill=0, width=grosor)
        d.line((x, y_fin + sep, x, y_fin + sep + largo), fill=0, width=grosor)
    for ym in y_bordes:
        y = mm(ym)
        d.line((x_ini - sep - largo, y, x_ini - sep, y), fill=0, width=grosor)
        d.line((x_fin + sep, y, x_fin + sep + largo, y), fill=0, width=grosor)


def guardar_pdf(paginas, ruta):
    """PDF mínimo con cada página como imagen RGB sin pérdida (Flate).

    PIL guarda los PDF RGB como JPEG, y la compresión con pérdida destruye
    señales de pocos niveles. Por eso se arma el PDF a mano.
    """
    ancho_pt, alto_pt = 594.96, 841.92
    objs = []

    def nuevo(contenido):
        objs.append(contenido)
        return len(objs)

    cat = nuevo(None)
    pags = nuevo(None)
    kids = []
    for im in paginas:
        im = im.convert('RGB')
        datos = zlib.compress(im.tobytes(), 9)
        xo = nuevo(b'<< /Type /XObject /Subtype /Image /Width %d /Height %d '
                   b'/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode '
                   b'/Length %d >>\nstream\n' % (im.width, im.height, len(datos))
                   + datos + b'\nendstream')
        cont = b'q %.2f 0 0 %.2f 0 0 cm /Im0 Do Q' % (ancho_pt, alto_pt)
        co = nuevo(b'<< /Length %d >>\nstream\n' % len(cont) + cont + b'\nendstream')
        kids.append(nuevo(b'<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %.2f %.2f] '
                          b'/Resources << /XObject << /Im0 %d 0 R >> >> /Contents %d 0 R >>'
                          % (pags, ancho_pt, alto_pt, xo, co)))
    objs[cat - 1] = b'<< /Type /Catalog /Pages %d 0 R >>' % pags
    objs[pags - 1] = (b'<< /Type /Pages /Count %d /Kids [%s] >>'
                      % (len(kids), b' '.join(b'%d 0 R' % k for k in kids)))

    out = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    offs = []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b'%d 0 obj\n' % i + o + b'\nendobj\n'
    xref = len(out)
    out += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objs) + 1)
    for o in offs:
        out += b'%010d 00000 n \n' % o
    out += b'trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objs) + 1, cat, xref)
    Path(ruta).write_bytes(out)


def armar_pliegos(cartas, imagenes):
    paginas = []
    total = N_CARTAS // POR_PLIEGO
    for p in range(total):
        hoja = Image.new('RGB', A4_PX, 'white')
        d = ImageDraw.Draw(hoja)
        for carta in cartas[p * POR_PLIEGO:(p + 1) * POR_PLIEGO]:
            img = imagenes[carta['id']]
            if carta['rotacion']:
                # Rotación antihoraria vista desde el dorso
                img = img.rotate(carta['rotacion'], expand=False)
            hoja.paste(img, celda_xy(carta['fila'], carta['columna'], espejado=True))
        marcas_de_corte(d)
        d.text((A4_PX[0] / 2, mm(6)), f'Mirá Vos · dorsos de qubits · pliego {p + 1} de {total} · '
               'imprimir doble faz, borde largo', fill=(90, 90, 90), font=fuente(30), anchor='mm')
        paginas.append(hoja)
    return paginas


# ---------- Hoja de prueba ----------

AMPS_PRUEBA = (8, 16, 24, 32)


def hoja_prueba(semilla, orientacion):
    rng = np.random.default_rng([semilla, 999])
    combos = [(v, h) for v in VERTICALES for h in HORIZONTALES]
    y0 = 40.0
    hoja = Image.new('RGB', A4_PX, 'white')
    d = ImageDraw.Draw(hoja)
    f_tit, f_txt, f_eti = fuente(46, True), fuente(29), fuente(34, True)

    d.text((mm(GRILLA_X_MM), mm(12)), 'Mirá Vos · hoja de prueba de amplitudes', fill=NAVY,
           font=f_tit, anchor='ls')
    instr = ('Cada fila prueba una amplitud (niveles sobre 255), igual para R y para G + B. '
             'Las 4 cartas de la fila tienen las 4 combinaciones, en orden al azar.\n'
             'Escaneá cada una con el filtro rojo (flecha vertical) y con el cian (flecha horizontal), '
             'con la marca del ojo arriba a la izquierda.\n'
             'Anotá lo que ves y compará con las respuestas de abajo (están dadas vuelta). '
             'Elegí la amplitud más baja que se lea siempre.')
    d.multiline_text((mm(GRILLA_X_MM), mm(16)), instr, fill=(60, 60, 60), font=f_txt, spacing=8)

    respuestas = []
    for f, amp in enumerate(AMPS_PRUEBA):
        orden = rng.permutation(4)
        y_c = mm(y0 + f * CELDA_MM + CELDA_MM / 2)
        d.text((mm(GRILLA_X_MM - 2), y_c - 20), f'{amp}', fill=NAVY, font=f_eti, anchor='rm')
        d.text((mm(GRILLA_X_MM - 2), y_c + 22), 'niveles', fill=(90, 90, 90), font=fuente(24), anchor='rm')
        fila_resp = []
        for c in range(COLUMNAS):
            v, h = combos[orden[c]]
            img = generar_dorso([semilla, 999, f, c], v, h, amp, amp, marca=orientacion == 'B')
            hoja.paste(img, (round(mm(GRILLA_X_MM + c * CELDA_MM)), round(mm(y0 + f * CELDA_MM))))
            fila_resp.append(f'{"ABCD"[c]} {FLECHA_GLIFO[v]}{FLECHA_GLIFO[h]}')
        respuestas.append(f'{amp:>2}: ' + '   '.join(fila_resp))
    for c in range(COLUMNAS):
        d.text((mm(GRILLA_X_MM + c * CELDA_MM + CELDA_MM / 2), mm(y0 - 1.5)), 'ABCD'[c],
               fill=NAVY, font=f_eti, anchor='ms')
    marcas_de_corte(d, filas=len(AMPS_PRUEBA), y0_mm=y0)

    # Respuestas en chico y dadas vuelta, al pie
    f_resp = fuente(30)
    lineas = ['Respuestas (vertical, horizontal):'] + respuestas
    caja = Image.new('RGB', (round(mm(150)), round(mm(30))), 'white')
    dc = ImageDraw.Draw(caja)
    dc.multiline_text((0, 0), '\n'.join(lineas), fill=(110, 110, 110), font=f_resp, spacing=10)
    caja = caja.rotate(180)
    hoja.paste(caja, (round(A4_PX[0] - mm(GRILLA_X_MM) - caja.width), round(mm(297 - 12) - caja.height)))
    return hoja


# ---------- Principal ----------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--amp-r', type=float, default=16, help='amplitud de la flecha vertical en R (niveles)')
    ap.add_argument('--amp-gb', type=float, default=16, help='amplitud de la flecha horizontal en (G+B)/2 (niveles)')
    ap.add_argument('--orientacion', choices=('A', 'B'), default='B',
                    help='A: sin marca ni rotación. B: marca del ojo y rotación k·90° al azar (por defecto)')
    ap.add_argument('--semilla', type=int, default=2026)
    ap.add_argument('--salida', type=Path, default=Path(__file__).resolve().parent / 'salida')
    ap.add_argument('--solo-prueba', action='store_true', help='generar solo la hoja de prueba')
    args = ap.parse_args()

    args.salida.mkdir(parents=True, exist_ok=True)

    prueba = hoja_prueba(args.semilla, args.orientacion)
    prueba.save(args.salida / 'hoja_prueba.png', dpi=(DPI, DPI))
    guardar_pdf([prueba], args.salida / 'hoja_prueba.pdf')
    print(f'Hoja de prueba → {args.salida / "hoja_prueba.pdf"}')
    if args.solo_prueba:
        return

    rng = np.random.default_rng(args.semilla)
    asignacion = asignar(rng, args.orientacion)
    cartas, imagenes = [], {}
    (args.salida / 'png').mkdir(exist_ok=True)
    for i, ((v, h), rot) in enumerate(asignacion):
        cid = i + 1
        semilla_carta = args.semilla * 1000 + cid
        img = generar_dorso(semilla_carta, v, h, args.amp_r, args.amp_gb, marca=args.orientacion == 'B')
        img.save(args.salida / 'png' / f'dorso_{cid:02d}.png', dpi=(DPI, DPI))
        imagenes[cid] = img
        pos = i % POR_PLIEGO
        cartas.append(dict(id=cid, pliego=i // POR_PLIEGO + 1, fila=pos // COLUMNAS, columna=pos % COLUMNAS,
                           vertical=v, horizontal=h, rotacion=rot, semilla=semilla_carta))

    with open(args.salida / 'dorsos.csv', 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['id', 'pliego', 'fila', 'columna_frente', 'flecha_vertical', 'flecha_horizontal',
                    'rotacion_grados', 'semilla', 'amp_r', 'amp_gb', 'orientacion'])
        for c in cartas:
            w.writerow([c['id'], c['pliego'], c['fila'] + 1, c['columna'] + 1, c['vertical'], c['horizontal'],
                        c['rotacion'], c['semilla'], args.amp_r, args.amp_gb, args.orientacion])

    guardar_pdf(armar_pliegos(cartas, imagenes), args.salida / 'pliegos_dorsos.pdf')

    # Chequeo de balance
    from collections import Counter
    combos = Counter((c['vertical'], c['horizontal']) for c in cartas)
    rots = Counter(c['rotacion'] for c in cartas)
    print('Combinaciones:', dict(combos))
    print('Rotaciones:', dict(rots))
    assert all(n == N_CARTAS // 4 for n in combos.values())
    if args.orientacion == 'B':
        assert all(n == N_CARTAS // 4 for n in rots.values())
    print(f'48 dorsos, manifiesto y pliegos → {args.salida}')


if __name__ == '__main__':
    main()
