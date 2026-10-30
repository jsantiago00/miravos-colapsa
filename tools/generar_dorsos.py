#!/usr/bin/env python3
"""Generador de dorsos de qubits de Mirá Vos con su ID.

Cada dorso es el dibujo de siempre (la flor de órbitas, tools/dorso_base.png)
con algunos puntitos del anillo borrados: el patrón de huecos es el ID de la
carta (ver tools/codigo_puntos.py). La app lo lee aunque la carta esté girada o
mal encuadrada. Del ID salen las respuestas del juego base (eje Z y eje X).

Como en el frente: en Z, SÍ = ↑ (+1) y NO = ↓ (−1); en X, SÍ = → y NO = ←.

Salidas (en --salida):
  png/dorso_NN.png     48 dorsos de 520 × 520 px a 300 dpi (44 mm con sangrado).
  dorsos.csv           manifiesto: ID de cada carta, su lugar en el pliego y sus respuestas.
  pliegos_dorsos.pdf   2 pliegos A4 de 24, espejados para doble faz.
  hoja_prueba.pdf/png  16 dorsos para probar la lectura, con los IDs al pie.

Uso:
  python tools/generar_dorsos.py                  # todo
  python tools/generar_dorsos.py --solo-prueba    # solo la hoja de prueba
"""

import argparse
import csv
import zlib
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from codigo_puntos import BASE, N_IDS, marcar, respuestas

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
N_CARTAS = N_IDS

NAVY = (20, 29, 58)
TXT = {'si': 'SÍ', 'no': 'NO'}


def mm(v):
    return v * PX_MM


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

_base = None


def generar_dorso(cid):
    """Dorso de 520 × 520 de la carta cid (1 a 48)."""
    global _base
    if _base is None:
        _base = np.asarray(Image.open(BASE).convert('RGB'))
    return Image.fromarray(marcar(_base, cid), 'RGB')


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
            hoja.paste(imagenes[carta['id']], celda_xy(carta['fila'], carta['columna'], espejado=True))
        marcas_de_corte(d)
        d.text((A4_PX[0] / 2, mm(6)), f'Mirá Vos · dorsos de qubits · pliego {p + 1} de {total} · '
               'imprimir doble faz, borde largo', fill=(90, 90, 90), font=fuente(30), anchor='mm')
        paginas.append(hoja)
    return paginas


# ---------- Hoja de prueba ----------

def hoja_prueba(semilla):
    """16 dorsos al azar en 4 filas, con sus IDs y respuestas al pie (dados
    vuelta). Sirve para probar la lectura con la cámara antes de imprimir todo."""
    rng = np.random.default_rng([semilla, 999])
    ids = [int(i) + 1 for i in rng.permutation(N_CARTAS)[:16]]
    filas, y0 = 4, 40.0
    hoja = Image.new('RGB', A4_PX, 'white')
    d = ImageDraw.Draw(hoja)
    f_tit, f_txt, f_eti = fuente(46, True), fuente(29), fuente(34, True)

    d.text((mm(GRILLA_X_MM), mm(12)), 'Mirá Vos · hoja de prueba de lectura', fill=NAVY,
           font=f_tit, anchor='ls')
    instr = ('Cada dorso tiene su ID en el patrón de puntitos del anillo. Recortá las cartas, escaneá cada\n'
             'una con la app (visor o El Espía), en cualquier orientación y con distinta luz, y anotá qué ID\n'
             'leyó y si fue segura. Compará con la lista de abajo (está dada vuelta).')
    d.multiline_text((mm(GRILLA_X_MM), mm(16)), instr, fill=(60, 60, 60), font=f_txt, spacing=8)

    lineas = []
    for f in range(filas):
        fila = []
        for c in range(COLUMNAS):
            cid = ids[f * COLUMNAS + c]
            hoja.paste(generar_dorso(cid), (round(mm(GRILLA_X_MM + c * CELDA_MM)), round(mm(y0 + f * CELDA_MM))))
            z, x = respuestas(cid)
            fila.append(f'{"ABCD"[c]}{f + 1} = {cid:2d} ({TXT[z]}/{TXT[x]})')
        lineas.append('   '.join(fila))
    for c in range(COLUMNAS):
        d.text((mm(GRILLA_X_MM + c * CELDA_MM + CELDA_MM / 2), mm(y0 - 1.5)), 'ABCD'[c],
               fill=NAVY, font=f_eti, anchor='ms')
    for f in range(filas):
        d.text((mm(GRILLA_X_MM - 2), mm(y0 + f * CELDA_MM + CELDA_MM / 2)), str(f + 1),
               fill=NAVY, font=f_eti, anchor='rm')
    marcas_de_corte(d, filas=filas, y0_mm=y0)

    # IDs en chico y dados vuelta, al pie
    caja = Image.new('RGB', (round(mm(176)), round(mm(26))), 'white')
    ImageDraw.Draw(caja).multiline_text((0, 0), '\n'.join(['ID (eje Z / eje X):'] + lineas),
                                        fill=(110, 110, 110), font=fuente(26), spacing=10)
    caja = caja.rotate(180)
    hoja.paste(caja, (round(A4_PX[0] - mm(GRILLA_X_MM) - caja.width), round(mm(297 - 12) - caja.height)))
    return hoja


# ---------- Principal ----------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--semilla', type=int, default=2026)
    ap.add_argument('--salida', type=Path, default=Path(__file__).resolve().parent / 'salida')
    ap.add_argument('--solo-prueba', action='store_true', help='generar solo la hoja de prueba')
    args = ap.parse_args()

    args.salida.mkdir(parents=True, exist_ok=True)

    prueba = hoja_prueba(args.semilla)
    prueba.save(args.salida / 'hoja_prueba.png', dpi=(DPI, DPI))
    guardar_pdf([prueba], args.salida / 'hoja_prueba.pdf')
    print(f'Hoja de prueba → {args.salida / "hoja_prueba.pdf"}')
    if args.solo_prueba:
        return

    rng = np.random.default_rng(args.semilla)
    orden = [int(i) + 1 for i in rng.permutation(N_CARTAS)]   # qué ID va en cada lugar del pliego
    cartas, imagenes = [], {}
    png = args.salida / 'png'
    png.mkdir(exist_ok=True)
    for viejo in png.glob('dorso_*.png'):
        viejo.unlink()
    for i, cid in enumerate(orden):
        img = generar_dorso(cid)
        img.save(png / f'dorso_{cid:02d}.png', dpi=(DPI, DPI))
        imagenes[cid] = img
        pos = i % POR_PLIEGO
        z, x = respuestas(cid)
        cartas.append(dict(id=cid, pliego=i // POR_PLIEGO + 1, fila=pos // COLUMNAS, columna=pos % COLUMNAS,
                           z=z, x=x))

    with open(args.salida / 'dorsos.csv', 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['id', 'pliego', 'fila', 'columna_frente', 'eje_z', 'eje_x'])
        for c in sorted(cartas, key=lambda c: c['id']):
            w.writerow([c['id'], c['pliego'], c['fila'] + 1, c['columna'] + 1, TXT[c['z']], TXT[c['x']]])

    guardar_pdf(armar_pliegos(cartas, imagenes), args.salida / 'pliegos_dorsos.pdf')

    combos = Counter((c['z'], c['x']) for c in cartas)
    print('Combinaciones:', dict(combos))
    assert len(combos) == 4 and all(n == N_CARTAS // 4 for n in combos.values())
    print(f'48 dorsos, manifiesto y pliegos → {args.salida}')


if __name__ == '__main__':
    main()
