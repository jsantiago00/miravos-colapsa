# El Espía · modo de juego de ¡Colapsá!

Modo para jugar en la mesa con las cartas reales y **un solo celular que se va
pasando**. La app reparte los roles en secreto, lleva el estado del qubit y
muestra a cada uno solo lo que le toca.

- App: `index.html` (es la única; `espia.html` redirige ahí). El visor aparte se sacó.
- Reglas: `espia_motor.js`, sin pantalla ni cámara. Tests: `npm test`.
- Lector del ID de los dorsos: `lector.js` (ver `COMO_FUNCIONA.md`).
- Referencia vieja con bots: `docs/el_espia_bots.html`. Las reglas de abajo mandan sobre ella.

---

## 1. Cómo se juega desde la app

1. **Preparar.** Abrí la app (`index.html`), elegí la cantidad de jugadores (4 a 8) y
   escribí los nombres **en el orden en que están sentados**. "Modo prueba"
   reemplaza la cámara por un botón "Simular escaneo". En "Reglas
   configurables" están la tabla de roles, las probabilidades de las acciones y
   los tiempos.
2. **Repartir roles.** El celu pasa por todos: "Pasale el celu a X" → *Soy X* →
   ve su rol → *Entendido · ocultar*.
   - Laboratorio: no sabe su eje ni si es distinto.
   - Calibrado: además sabe si es de la mayoría o distinto.
   - Observador: juega con la mayoría y tiene que hacer como que mide.
3. **Rondas.** Una carta nueva por ronda, con el dorso para arriba. La app
   muestra el orden (arriba, en fichas). En cada turno:
   - *Soy X* → escanear el dorso → animación "Midiendo" (dura lo mismo para
     todos) → **SÍ o NO** con una línea debajo → *Ocultar* (con la misma
     pausa para todos).
   - La línea debajo está siempre, en el mismo lugar: "Nada más en tu
     detector", la acción si te tocó una ("Par EPR: Juan midió de verdad SÍ"),
     o, para el Observador, "Sos el Observador…".
   - La siguiente pantalla le dice al que midió que diga su resultado en voz
     alta y pase la carta y el celu al que sigue.
   - La carta pasa por todos y **vuelve al que arrancó**, que la mide de nuevo.
4. **Debate** con temporizador (3 min por defecto, con pausa y "+30 s").
5. **Votación secreta** pasando el celu: cada uno elige a quién cree distinto y
   confirma. Nadie se puede votar a sí mismo.
6. **Revelación.**
   - Quién gana y los roles (Mayoría, Distinto, Observador). Los ejes no se
     nombran.
   - Los votos.
   - Una tabla por ronda con la carta, el lado de cada uno, lo que midió de
     verdad, dónde el qubit se volvió a sortear, las acciones y lo que vio el
     Observador.
   - Opcional: la columna "Dijo" se carga tocando (¿? → SÍ → NO) y marca con ≠
     dónde alguien dijo otra cosa que lo que midió.

Si se cierra la app o se apaga la pantalla, al volver ofrece **Retomar
partida**. Si la pantalla se apaga en medio de algo privado, vuelve a "Pasale el
celu a X".

---

## 2. Qué quedó implementado

| Regla | Cómo quedó |
|---|---|
| Tabla de roles configurable | Sí, en "Reglas configurables" (se guarda para la próxima). El motor valida que haya entre 1 distinto y menos de la mitad de los laboratorios. |
| Eje de la mayoría al azar, calibrado al azar entre los laboratorios | Sí. |
| Primera medición | **Al azar 50/50.** Las cartas no tienen eje: la app sortea el valor de cada carta en juego. El dorso solo identifica la carta (ver abajo). |
| Mismo eje, mismo resultado; otro eje, 50/50 y se actualiza el estado | Sí. |
| "¿Es la misma carta?" | Si el ID leído no es el de la carta en juego: *Escanear de nuevo* o *Es la misma, seguir*. |
| Solo SÍ/NO en pantalla | Nunca se muestra la flecha ni el eje. El SÍ/NO grande va en un solo color (verde y rojo se ven desde lejos). |
| Orden: arranca otro en cada ronda, la dirección se alterna, vuelve al que arrancó | Sí. El primer inicio se sortea y después avanza un asiento por ronda. |
| Observador escondido | Escanea igual que todos, con la misma animación y las mismas pantallas. Ve una medición verdadera al azar de un laboratorio que midió antes en la vuelta. No toca el qubit y no le salen acciones. |
| Observador que arranca la ronda | Cuenta como si hubiera medido en el eje de la mayoría (resultado al azar), y **la app le muestra lo que marca su detector**. Desde la ronda 2 ve además una medición verdadera de la ronda anterior; en la ronda 1, nada más. Ver §4.1. |
| Acciones | `pColapso ∈ [0,10; 0,25]` y `pSinColapso ∈ [0,10; 0,20]` se sortean por ronda. Nunca salen en la primera medición. Se muestran después del resultado, sin decir "colapsaste". |
| Agujero de gusano | Automático: la app elige al azar a alguien que ya midió la carta en la ronda (el Observador incluido), menos a uno mismo. |
| Par EPR | Automático, con el que te pasó la carta. |
| Acción sobre el Observador | Muestra el estado del qubit en su turno, o sea lo que "habría medido" en el eje del anterior. |
| Proporción Agujero / EPR | Configurable, 50/50 por defecto. |
| Votación y quién gana | Si el más votado (sin empate) es un distinto, ganan la mayoría y el Observador. Si no, o si hay empate, ganan los distintos. |
| Privacidad | Toda pantalla con información se abre con *Soy X* y se cierra con *Ocultar*. Si se apaga la pantalla o se cambia de app, se tapa. Se pide que la pantalla no se apague sola (Wake Lock). |
| Sin tells de tiempo | Todos los turnos tienen los mismos pasos y los mismos toques: Soy → escaneo → Ocultar. Una sola pantalla de resultado, con la misma forma y la misma pausa para todos. |
| Persistencia | `localStorage` después de cada paso. Al retomar se vuelve a la pantalla pública del turno. Lo ya medido no se vuelve a sortear. |
| Modo prueba | "Simular escaneo" y "Simular otra carta" (para probar el aviso). |
| Escaneo restringido | La cámara se abre **solo en tu turno** y lee **una** carta. Se cierra sola cuando lee el mismo ID seguro tres cuadros seguidos (unos 0,3 s), o cuando se acaba el tiempo (20 s, configurable). Hay "Sacar foto" por si el navegador no da video. |
| Tests | 23 del motor (primera medición al azar incluida): reparto, orden, qubit, acciones, Agujero, EPR, Observador, votación y guardado. Más 2 del lector con cartas sintéticas. |

### El ID en el dorso y el chequeo de "misma carta"

Cada dorso lleva **su ID (1 a 48)** en el anillo de 24 puntitos naranjas: los
8 de las puntas de los pétalos están siempre y de los otros 16 faltan 7, en un
patrón propio de cada carta. Se ve, pero parece decoración, y sin la tabla no
se sabe qué carta es. El detalle está en `COMO_FUNCIONA.md`.

- **Cualquier cambio de carta se detecta.** Cuando arranca la ronda, la app
  guarda el ID de la carta; si después se escanea otra, avisa.
- **Un puntito mal leído (o tapado con el dedo) nunca da otra carta:** los
  patrones se eligieron para que entre dos cartas haya al menos 4 puntitos
  distintos en cualquier giro. La app no la lee y se sigue intentando.
- En simulación lee seguras 150 de 150 fotos de celular (giradas, corridas,
  desenfocadas, con luz despareja y JPEG), y ninguna equivocada. **Falta
  confirmarlo con la hoja de prueba impresa** (`python tools/generar_dorsos.py
  --solo-prueba`).
- El escaneo es parte del juego: es lo que hace sentir el laboratorio. Por eso
  la cámara sigue en cada turno, aunque el resultado lo sortee la app.

En la tabla final, cada ronda dice con qué carta se jugó.

---

## 3. Modo sala (un celular por jugador) · evaluación

> No vi tu otro repo de minijuegos con Firebase; esto es lo que haría con ese
> enfoque (Firebase + GitHub Pages).

### Arquitectura

- **El estado secreto no puede vivir en un celular de jugador.** Si un
  "anfitrión" guarda los ejes, el anfitrión puede leerlos. En un juego de
  deducción eso lo rompe.
- La opción correcta es **Firestore + Cloud Functions** como autoridad. La
  función:
  - reparte los roles;
  - sortea los resultados y recibe el ID leído en cada turno (para el chequeo de carta);
  - calcula el resultado con `espia_motor.js`, que ya es JS puro y se puede
    usar tal cual en una función;
  - escribe en el documento privado de cada jugador solo lo que le toca.
- **Costo:** Cloud Functions pide el plan Blaze (pago por uso). Para un juego
  de mesa el gasto real es prácticamente cero, pero hay que poner una tarjeta.
  Sin funciones, solo queda "anfitrión de confianza".
- **Turno:** un documento público `salas/{id}` con el orden, el turno actual y la
  fase. Cada cliente lo escucha con `onSnapshot`. Solo el jugador de turno
  puede mandar su lectura; la función valida que sea su turno.
- **Desconexiones:** con autenticación anónima persistente, si alguien recarga
  vuelve a ser el mismo jugador y retoma. El turno lo espera. El anfitrión
  (solo para administrar, sin datos secretos) puede saltarlo o sacarlo. La
  presencia se marca con un "visto por última vez" cada pocos segundos.

### Privacidad

- Reglas de Firestore:
  - `salas/{id}/secreto` sin lectura para nadie;
  - `salas/{id}/privado/{uid}` legible solo por ese `uid`;
  - todo lo escriben las funciones.
- Así ningún celular recibe el eje de nadie, ni siquiera el propio, que el
  jugador tampoco conoce.
- La lectura del dorso se hace en el celular, pero ya no es un problema: solo
  identifica la carta. Todos los resultados los sortea el servidor.

### Anti-trampa: qué es realista en web

| Idea | ¿Se puede? |
|---|---|
| "Caro se fue de la app" | **Sí.** `visibilitychange` y `pagehide` avisan cuando la pestaña deja de estar visible, y se puede publicar "👀 Caro salió de la app". **No** se puede saber a qué app fue: "se fue a Instagram" no se puede. |
| Captura de pantalla | No se puede detectar en web. |
| Celu boca abajo con el acelerómetro | Técnicamente sí en Android (HTTPS). En iOS hay que pedir permiso con un toque (`DeviceOrientationEvent.requestPermission`). Con la pantalla apagada no hay eventos, y no prueba nada: boca abajo no impide mirar. Lo descartaría. |
| Mirar el celu del vecino | Igual que con cartas: es un juego de mesa, se resuelve con la mesa. |

### ¿Qué gana el juego?

- **Velocidad**, sobre todo con 7 u 8. La carta sigue dando la vuelta, pero cada
  uno escanea con su celu, que ya tiene en la mano, en vez de esperar el
  teléfono y el *Soy X*.
  - Calculo que el turno baja de ~20 s a ~8–10 s.
  - Reparto y votación pasan a ser simultáneos: de unos 2–3 min a segundos.
- **Cuaderno privado digital** sin pasar el celu (ver §4.5).
- **Menos riesgo de miradas** al pasar el teléfono.
- **Lo que no gana:** la deducción es la misma, y la carta igual tiene que dar
  la vuelta físicamente (es la gracia y el anclaje con la mesa).
- **Lo que pierde:** todos necesitan celu con cámara y conexión, más tiempo
  de preparación (unirse a la sala) y bastante más código y mantenimiento.

**Recomendación:** dejar el modo de un celular como el principal y probarlo con
gente. El modo sala vale la pena si con 7 u 8 jugadores el ritmo se hace pesado.
En ese caso, hacerlo con Cloud Functions; sin una autoridad del lado del
servidor, no lo haría.

---

## 4. Evaluación del juego

### 4.1 Observador que arranca la ronda (tu decisión 2 + la propuesta)

Cómo quedó: si arranca, el qubit queda como si hubiera medido en el eje de la
mayoría, con un resultado al azar, y **la app se lo muestra**: "arrancás la
ronda y tu detector viene calibrado con la mayoría. Marca SÍ". Desde la ronda 2
ve además una medición verdadera de la ronda anterior; en la ronda 1, nada más.
Al cerrar la vuelta el qubit pasa por él sin cambiar, y ahí ve una medición
verdadera de un laboratorio de esta ronda. Implicancias:

- **La ronda se ve igual que si arrancara un laboratorio.**
  - El segundo ya puede recibir una acción, como en cualquier ronda. Si no
    fuera así, que el segundo no pudiera tener acción delataría que el primero
    era el Observador.
  - Un Agujero de gusano o un Par EPR sobre él muestra justo lo que vio.
- **Puede jugar de ancla honesta de la mayoría.** Si dice la verdad, el
  siguiente de la mayoría lo confirma; antes no sabía qué decir y quedaba como
  sospechoso de distinto sin poder evitarlo.
- **Le regala poco:** es un bit que el siguiente de la mayoría igual va a
  repetir. Lo que sí sabe es que cualquiera que diga otra cosa sin colapso
  posible está mintiendo o es del otro eje, pero eso es lo que tiene que hacer
  un Observador.
- **Nota:** las rondas que arranca son las que más información le dan: lo que
  mediría la mayoría, una medición de la ronda anterior (desde la ronda 2) y
  un laboratorio al cerrar la vuelta. Con 4 jugadores, que son 4 rondas,
  arranca siempre una.

### 4.2 ¿Se hace lento con 7 u 8?

Estimación por turno: pasar el celu y *Soy X* (~3 s), escanear (3–6 s),
animación (1,2 s), resultado (2 s), segunda pantalla (3 s), ocultar y decir en
voz alta (~4 s). Total: **unos 20 s**.

| Jugadores | Turnos | Rondas | Partida (sin debate) |
|---|---|---|---|
| 4 | 5 por ronda | 4 | ~7 min de vueltas + ~2 min de reparto y voto |
| 8 | 9 por ronda | 2 | ~6 min de vueltas + ~3 min de reparto y voto |

Más 3 min de debate: **12–15 min por partida**. Se banca.

Lo que más pesa es la espera entre turnos: con 8, cada uno mide 2–3 veces en
toda la partida. Si se hace pesado, en este orden:

1. Bajar la pausa mínima a 2 s.
2. Juntar "resultado" y "segunda pantalla".
3. Ir al modo sala.

### 4.3 ¿Se puede deducir algo por cómo se comporta la app?

- **Cubierto:**
  - mismos pasos, toques y pausas para laboratorio con acción, sin acción y
    Observador;
  - el Observador escanea de verdad;
  - sin sonidos ni vibración (salvo el fin del debate);
  - el SÍ/NO grande sin color;
  - la pantalla de lectura dice "Buscando el dorso…" o "Leyendo…", igual para
    todos.
- **Lo que queda:**
  - **Tiempo de decisión del Agujero de gusano.** Elegir a quién mirar lleva
    más que tocar cualquier nombre. La pausa lo tapa en parte; el resto
    depende del jugador. Podría hacerse que los turnos sin acción pidan elegir
    algo con el mismo peso, pero lo vería en las pruebas.
  - **Botones apagados en el Agujero.** Ahí solo se pueden tocar los que ya
    midieron. Desde lejos se nota poco, pero se nota.
  - **Texto más largo del Observador.** Su pantalla tiene una frase más ("No
    tenés escáner, pero ves que…"); la pausa mínima lo compensa.
  - **Patrón estadístico:** el "valor verdadero" del Observador (si alguien lo
    espía con una acción) **siempre coincide con el del que le pasó la carta**,
    porque no colapsa nunca. En varias rondas, alguien muy atento podría
    notar que "X nunca colapsa". Pasa poco, porque las acciones son raras.
  - **Wake Lock:** si el navegador no lo soporta, la pantalla puede
    apagarse a mitad de turno. No delata a nadie, pero obliga a pasar de nuevo
    por *Soy X*.

### 4.4 El visor de otros celulares (tu punto 5)

- Dentro de la app el escaneo está restringido: solo en tu turno, una
  carta, con tiempo límite, y nunca muestra flecha ni eje.
- Desde que las cartas no tienen eje, **leer el dorso con el visor en otro
  celu ya no da ninguna ventaja**: el resultado lo sortea la app y el dorso
  solo identifica la carta. El problema de antes (saber el eje del primero que
  mide) desapareció.
- Igual conviene la regla de mesa "celus guardados durante El Espía", por
  prolijidad.

### 4.5 ¿Anotar en la app o en papel?

**Papel y lápiz, como dice el reglamento.**

- Con un celular compartido, un cuaderno en la app obligaría a pasar el celu y
  hacer *Soy X* cada vez que alguien quiere anotar: lento y lleno de tells
  ("¿por qué anotó tanto?").
- Lo que sí tiene sentido es lo que ya está:
  - la revelación final con la verdad;
  - la columna opcional "Dijo", para cargar después lo que se escuchó y ver
    quién mintió dónde.
- Para analizar las partidas de prueba sirve mucho, y no le pide nada a nadie
  durante el juego.
- En el modo sala, un cuaderno privado en el propio celu sí tiene sentido.

### 4.6 Otras cosas raras de las reglas

- **Empates con pocos jugadores.** Con 4 hay 4 votos y el empate 2–2 (que gana
  el distinto) es común. Conviene simularlo con los bots o en las pruebas, y
  pensar un desempate, por ejemplo que el voto del calibrado valga doble.
- **El que arranca mide dos veces** y, en la segunda, compara con lo que midió
  al principio. Si nadie colapsó en el medio, es casi una prueba de que todos
  los del medio midieron en su eje. Es información fuerte y siempre la tienen
  los mismos (en 5+ jugadores solo hay 2 rondas, o sea 2 que arrancan). Está
  bien si es intencional.
- **Las acciones casi no delatan colapso.** Las probabilidades se superponen
  (en promedio 17,5 % contra 15 %), así que recibir una acción es una pista
  muy débil de que el anterior era del otro eje. Me parece bien que sea ruido,
  pero si querés que signifique algo, separar más los rangos.
- **El calibrado distinto** sabe todo lo que necesita para esconderse desde el
  principio. Con 1 distinto entre 3 o 4 laboratorios puede desbalancear: vale
  mirarlo en las pruebas.
- **Lectura dudosa:** la app pide reescanear sin mostrar nada. Falta confirmar
  con la hoja de prueba impresa que el lector lea seguro en luz de mesa (ver
  `COMO_FUNCIONA.md`, §4).
