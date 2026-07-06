# Airstrike Python

Port multiplataforma en Python/Pygame del juego Airstrike incluido en este
repositorio. Reutiliza los sprites, fondos y sonidos originales de `data/`, pero
reemplaza el runtime SDL/C por una implementación Python organizada en módulos.

## Requisitos

- Python 3.10 o superior.
- Dependencias de `requirements.txt`: Pygame y Pillow.

Instalación recomendada:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

En Windows:

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

## Ejecutar

```bash
.venv/bin/python -m airstrike_py
```

También se puede usar:

```bash
.venv/bin/python play_airstrike.py
```

Opciones útiles:

```bash
.venv/bin/python -m airstrike_py --fullscreen
.venv/bin/python -m airstrike_py --nosound
```

Si la build local de Pygame no incluye `pygame.mixer`, el juego deshabilita el
sonido automáticamente y continúa en modo silencioso.

## Controles

- `F11`: alternar fullscreen.
- `Esc`: pausa/menu.
- `F1`: mostrar u ocultar ayuda.
- En pausa: `N` nueva partida, `Q` salir.
- Blue Baron: flechas izquierda/derecha para girar, `Arriba` para acelerar,
  `Z` para disparar, `RShift` o `Espacio` para soltar bomba.
- Red Baron: `A/D` para girar, `W` o `LCtrl` para acelerar, `LShift` para
  disparar, `Tab` para soltar bomba.

Por defecto `airstrikerc` mantiene un jugador humano y un rival IA. Cambiá
`nr_players` a `0`, `1` o `2` para elegir IA contra IA, humano contra IA o dos
humanos.

## Mecánicas portadas

- Los globos/bouncers se pinchan, se desinflan y sueltan pickups temporales.
- La máquina de bonus genera nuevos globos periódicamente.
- Los pickups pueden curar/reponer bombas, sumar score o activar molestias para
  el rival como pájaros, globos, nubes, zepelín, cañón o misil.
- Hay cañón con bolas de cañón, hangar dañable, pájaros, zepelín, globos y
  nubes del juego original.

## Estructura del port

- `airstrike_py/config.py`: lectura tolerante de `airstrikerc`.
- `airstrike_py/assets.py`: carga de sprites, animaciones y sonidos. Usa Pillow
  como fallback para PNG cuando la build de Pygame no trae soporte de imagen.
- `airstrike_py/entities.py`: aviones, proyectiles, bombas, efectos y objetos
  ambientales.
- `airstrike_py/game.py`: bucle principal, input, fullscreen, colisiones, score
  y UI.
- `airstrike_py/text.py`: fuente bitmap interna para no depender de SDL_ttf.
