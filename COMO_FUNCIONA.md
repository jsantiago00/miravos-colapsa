# Mirá Vos · ¡Colapsá! — cómo funciona

Documento de contexto para retomar el proyecto (pensado para pasárselo a Claude
al empezar una sesión nueva). Describe qué hace la app, cómo va el ID de cada
carta en el dorso y cómo se lee.

> Nota: no es encriptación. El ID está a la vista, en el patrón de puntitos del
> anillo; quien tenga la tabla `PATRONES` puede leerlo. La idea es que sea fácil
> para el escáner y difícil de descifrar para una persona.

---

## 1. Qué es

Un juego de cartas de "qubits". Cada carta tiene en el dorso el mismo dibujo
(la flor de órbitas, `tools/dorso_base.png`), pero en cada dorso faltan algunos
puntitos del anillo, en un patrón propio: eso es su **ID** (1 a 48).

La app es una sola: **El Espía** (`EL_ESPIA.md`). En cada turno el jugador
escanea el dorso; la app usa el ID solo para reconocer la carta en juego, y el
resultado (SÍ o NO) lo sortea. El escaneo es parte del juego: es lo que hace
sentir que se mide.

> Hasta la edición 02 había un visor aparte que sacaba del ID una respuesta fija
> en Z y otra en X. Se sacó: nadie lo usaba y los ejes ya no se muestran.

## 2. Archivos

| Archivo | Qué hace |
|---|---|
| `index.html` + `espia_motor.js` | La app: El Espía (ver `EL_ESPIA.md`). |
| `espia.html` | Redirige a `index.html`, para que no se rompan los links viejos. |
| `lector.js` | La lectura del ID (`PATRONES`, `read`). |
| `tests/` | Tests (`npm test` o `node --test "tests/*.test.js"`). |
| `docs/el_espia_bots.html` | Laboratorio de bots de El Espía (referencia, reglas viejas). |
| `tools/codigo_puntos.py` | Escritura y lectura del ID (fuente de verdad). Lee fotos desde la compu, simula fotos de celular (`--simular`) y elige los patrones (`--elegir`). |
| `tools/generar_dorsos.py` | Genera los 48 dorsos, el manifiesto `dorsos.csv`, los pliegos A4 para imprimir doble faz y la hoja de prueba. |
| `tools/dorso_base.png` | El dibujo base del dorso, con los 24 puntitos (520 × 520 px, 300 dpi, 44 mm con sangrado). |

Las salidas van a `tools/salida/` (no versionado).

## 3. Cómo va el ID en el dorso (escritura)

Código en `marcar()` de `tools/codigo_puntos.py`.

1. El dorso base tiene **24 puntitos naranjas** en un anillo de **17,6 mm** de
   radio, uno cada 15° (radio de cada puntito: 0,7 mm).
2. Los **8 de las puntas de los pétalos** (cada 45°) quedan siempre. De los
   otros 16, cada carta tiene **7 huecos**: se borran pintándolos del color del
   fondo. Quedan 17 puntitos.
3. `PATRONES` (48 números de 24 bits; bit k = está el puntito del ángulo k·15°,
   desde la derecha hacia abajo, en coordenadas de imagen) dice cuáles quedan
   en cada carta. `PATRONES[0]` es la carta 1.
4. **Cómo se eligieron** (`elegir()`, ya hecho; volver a correrlo cambia todas
   las cartas): al azar, con la condición de que entre dos cartas cualesquiera,
   en cualquier giro, haya al menos **4 puntitos distintos**. Un puntito mal
   leído cambia 2 (siempre faltan 7: si uno sobra, otro falta), así que nunca
   lleva a otra carta: queda "a mitad de camino" y la app pide reescanear.
5. `tools/codigo_puntos.py` todavía tiene `respuestas(id)` (las respuestas Z/X
   del visor viejo) y el manifiesto las imprime. La app ya no las usa.

## 4. Cómo se lee (lectura)

Misma lógica en `leer_carta()` (Python) y `read()` (JS en `lector.js`).

1. **Recorte**: el recuadro guía (72 % del lado menor del cuadro) agrandado
   **1,3 veces** (por si la carta quedó corrida o más grande que el recuadro),
   llevado a **320 × 320 px**.
2. **Mapa de naranja**: R − B. Los puntitos dan muy alto; el fondo azul marino
   y los pétalos celestes, bajo o negativo.
3. **Centro y radio del anillo**: búsqueda gruesa (±5 mm, escala 0,85–1,15) y
   después fina. Puntaje de un círculo = naranja medio sobre él menos el de los
   círculos 1,4 mm adentro y afuera: alto solo en un anillo fino, así que una
   mesa naranja no lo engaña.
4. **Giro**: el armónico 24 del perfil de naranja sobre el anillo da dónde
   caen las 24 posiciones.
5. **Puntitos**: naranja medio en cada posición (centro y 4 alrededor). Los 17
   más naranjas son puntitos; los 7 restantes, huecos (no hace falta umbral).
6. **ID**: el patrón más parecido de la tabla, probando los 24 giros.
   - **segura**: coincide exacto, y hay buena separación entre el puntito más
     flojo y el hueco más fuerte (`margen ≥ 0,35`) y buen contraste
     (`contraste ≥ 0,35`);
   - **dudosa**: coincide exacto pero con poca separación;
   - **no se lee**: no coincide con ninguna.

En simulación (`--simular`: carta girada, corrida hasta 3 mm, escala 0,88–1,12,
desenfoque, luz despareja y cálida, ruido, JPEG 4:2:0) se leen seguras 150 de
150, sin ninguna carta equivocada; la mesa vacía no se lee como carta. En
condiciones peores (más desenfoque, JPEG 60, corrida 4 mm) 87 % seguras y
ninguna equivocada. **Falta confirmarlo con la hoja de prueba impresa.**

## 5. La app (`index.html`)

Ver `EL_ESPIA.md`. La app nunca muestra el ID leído. Para revisar la lectura
de la hoja de prueba impresa, sacarle fotos y leerlas con
`python tools/codigo_puntos.py foto.jpg`, que muestra el ID, el nivel de
lectura y el margen.

## 6. Imprimir y probar

```
python tools/generar_dorsos.py --solo-prueba   # hoja de prueba: 16 dorsos con sus IDs al pie
python tools/generar_dorsos.py                 # 48 dorsos + manifiesto + pliegos
python tools/codigo_puntos.py foto.jpg         # leer una foto desde la compu
python tools/codigo_puntos.py --simular 150    # simular lecturas con cámara
```

- Los PDF se arman a mano sin compresión con pérdida.
- Pliegos A4 de 4 × 6, espejados para doble faz (borde largo), con marcas de
  corte. Carta 40 mm + 2 mm de sangrado.
- Hoja de prueba: recortar, escanear cada carta en cualquier orientación y con
  distinta luz, y comparar con los IDs al pie (dados vuelta).

## 7. Reglas para tocar el código

- **`PATRONES` está duplicado**: en `tools/codigo_puntos.py` y en `lector.js`.
  Si cambia uno, cambia el otro. Lo mismo para `GUIA`, `AMPLIA`, `P`,
  `R_ANILLO`, `HUECOS`, la búsqueda del anillo, los umbrales
  (`MARGEN_SEGURO`, `CONTRASTE_MIN`).
- Cambiar los patrones (`--elegir`) **invalida las cartas ya impresas**.
- Si cambia el dibujo base, revisar que los puntitos sigan en el mismo anillo
  (17,6 mm, cada 15°) y que no haya otras cosas naranjas cerca de ese radio.
- Convenciones: código y comentarios en español rioplatense, sin
  dependencias en la app (HTML y JS planos, sin compilar). `lector.js` y
  `espia_motor.js` funcionan en el navegador y en Node (para los tests).
