```md
# Objetivo del trabajo

Estamos trabajando en el repositorio público de **PadelKit**, una librería open source de Python para análisis de pádel.

El objetivo principal ahora mismo NO es construir toda la librería completa, sino preparar lo antes posible una **primera versión mínima, funcional y publicable en PyPI** para reservar el nombre del proyecto y establecer una base limpia.

El paquete se llamará:

- Nombre PyPI: `padelkit`
- Import Python: `padelkit`
- Dominio documentación: `https://padelkit.dev`
- Repositorio GitHub: `https://github.com/padelkit/padelkit`

La licencia de la librería será **Apache 2.0**.

Hay un proyecto privado/comercial relacionado llamado **Padelamix**, que es un sistema más amplio de análisis automático de vídeo de pádel. El código de Padelamix está en local en:

```txt
/home/fidelechevarria/repos/padelamix
```

Puedes leer su archivo de conocimiento si necesitas entender la visión general:

```txt
/home/fidelechevarria/repos/padelamix/knowledge.md
```

Pero importante:

- No copies código propietario de Padelamix directamente a este repo.
- No incluyas modelos, pipelines de inferencia, lógica GPU, RunPod, Supabase, Stripe, datasets, heurísticas avanzadas ni nada sensible.
- PadelKit debe ser una librería open source limpia, pequeña y reutilizable.
- Si necesitas implementar algo inspirado por la idea general, hazlo desde cero y de forma simple.

---

# Visión de PadelKit

PadelKit será un toolkit open source para desarrolladores que quieran construir herramientas de análisis de pádel.

A largo plazo podrá incluir:

- Geometría oficial de pista de pádel.
- Landmarks 2D/3D de pista.
- Sistemas de coordenadas.
- Calibración de cámara.
- Proyección mundo↔imagen.
- Modelos de datos para jugadores, pelota, frames, rallies y partido.
- Sistema de tanteo de pádel.
- Eventos deportivos: saque, golpe, bote, red, winner, error, etc.
- Tracking y trayectorias.
- Métricas básicas.
- IO JSON/CSV/Parquet.
- Visualización.

Pero para esta primera versión queremos algo mucho más pequeño.

---

# Objetivo inmediato

Crear una versión mínima funcional de `padelkit`, por ejemplo `0.0.1`, lista para construir y publicar en PyPI.

Esta versión debe incluir como mínimo:

1. Estructura moderna de paquete Python.
2. `pyproject.toml` correctamente configurado.
3. Código fuente bajo `src/padelkit`.
4. API mínima funcional.
5. Tests básicos con `pytest`.
6. README adecuado para GitHub/PyPI.
7. Licencia Apache 2.0.
8. Comandos de build funcionando.
9. Idealmente GitHub Actions para CI.
10. No añadir dependencias pesadas todavía.

---

# Stack deseado

Usar una configuración Python moderna, sencilla y mantenible.

Preferencias:

- Python mínimo: `>=3.10`
- Build backend: `hatchling` o similar simple.
- Tests: `pytest`
- Lint/format: `ruff`
- Tipado: type hints en el código.
- Evitar dependencias runtime innecesarias en la primera versión.

Para esta primera versión, preferiblemente no usar:

- OpenCV
- JAX
- PyTorch
- TensorFlow
- pandas
- scipy
- matplotlib

La primera versión debe ser ligera.

---

# Funcionalidad mínima propuesta

Implementar principalmente dos áreas:

## 1. Geometría básica de pista

Crear un módulo:

```txt
src/padelkit/court/
```

Con clases/funciones simples para representar una pista oficial de pádel.

API deseada aproximada:

```python
from padelkit.court import PadelCourt

court = PadelCourt.fip_standard()

print(court.length)  # 20.0
print(court.width)   # 10.0

landmarks = court.landmarks_2d()
center = court.point("center")
```

Dimensiones oficiales básicas:

- Largo: 20.0 m
- Ancho: 10.0 m
- Altura de red en centro: 0.88 m
- Altura de red en postes: 0.92 m
- Distancia línea de saque desde pared de fondo: 3.0 m
- Pared/cristal de fondo: puede representarse de forma básica con altura 3.0 m
- Sistema de coordenadas inicial:
  - origen en el centro de la pista
  - eje X: ancho, izquierda/derecha
  - eje Y: largo, fondo/fondo
  - unidades en metros

Implementar landmarks 2D básicos en coordenadas de pista:

- center
- four corners
- net center
- net left
- net right
- service line y=-7 / y=7 si origen en centro y línea de saque a 3 m desde fondo
- service box intersections básicos
- back corners
- maybe side wall corners

No hace falta que sea perfecto o exhaustivo; debe ser útil, documentado y testeable.

Clases posibles:

```python
CourtDimensions
CourtPoint
PadelCourt
```

Usar `dataclasses` y enums si ayuda.

---

## 2. Tanteo básico de pádel

Crear un módulo:

```txt
src/padelkit/scoring/
```

Con una implementación mínima de marcador.

API deseada aproximada:

```python
from padelkit.scoring import MatchScore

score = MatchScore()
score.point_won_by("A")
score.point_won_by("B")
score.point_won_by("A")

print(score.game_points)
```

Para la primera versión basta con:

- Equipos `A` y `B`.
- Puntos de juego: 0, 15, 30, 40.
- Deuce/advantage en modo clásico.
- Opción de golden point, aunque si complica demasiado, puede dejarse para después.
- Avance de juegos.
- Avance básico de sets a 6 con diferencia de 2.
- No hace falta implementar tie-break completo en esta primera versión si retrasa.

Mejor una implementación pequeña y correcta que una grande incompleta.

Clases posibles:

```python
TeamId
GameScore
SetScore
MatchScore
```

Pero mantenerlo simple.

---

# API pública inicial

El paquete raíz debería exponer algo mínimo:

```python
import padelkit

print(padelkit.__version__)
```

Y permitir:

```python
from padelkit.court import PadelCourt
from padelkit.scoring import MatchScore
```

---

# Estructura de repo deseada

Si el repo está vacío o casi vacío, crear algo parecido a:

```txt
.
├── README.md
├── LICENSE
├── CHANGELOG.md
├── pyproject.toml
├── .gitignore
├── .github/
│   └── workflows/
│       └── ci.yml
├── src/
│   └── padelkit/
│       ├── __init__.py
│       ├── court/
│       │   ├── __init__.py
│       │   ├── dimensions.py
│       │   ├── landmarks.py
│       │   └── court.py
│       └── scoring/
│           ├── __init__.py
│           └── score.py
└── tests/
    ├── test_court.py
    └── test_scoring.py
```

Si ya existe estructura, respetarla salvo que esté claramente mal.

---

# README

El README debe ser breve pero presentable para PyPI.

Debe incluir:

- Nombre: PadelKit.
- Descripción corta.
- Instalación:

```bash
pip install padelkit
```

- Quickstart:

```python
from padelkit.court import PadelCourt
from padelkit.scoring import MatchScore

court = PadelCourt.fip_standard()
print(court.length, court.width)

score = MatchScore()
score.point_won_by("A")
print(score)
```

- Estado del proyecto: early alpha.
- Features iniciales.
- Roadmap breve.
- Licencia Apache 2.0.
- Link a docs: `https://padelkit.dev`
- Link a GitHub.

Importante: evitar prometer que ya hace análisis automático de vídeo. PadelKit no debe presentarse como un motor completo de visión por computador en esta primera versión.

---

# pyproject.toml

Configurar bien metadata de PyPI.

Campos deseados:

- name = `padelkit`
- version = `0.0.1`
- description
- readme
- requires-python = `>=3.10`
- license = `Apache-2.0`
- authors/maintainers con Fidel Echevarria, si hace falta sin email o con email de proyecto si ya existe.
- keywords:
  - padel
  - sports analytics
  - computer vision
  - court geometry
  - scoring
- classifiers:
  - Development Status :: 3 - Alpha
  - Intended Audience :: Developers
  - Intended Audience :: Science/Research
  - License :: OSI Approved :: Apache 2.0 License
  - Programming Language :: Python :: 3
  - Programming Language :: Python :: 3.10
  - Programming Language :: Python :: 3.11
  - Programming Language :: Python :: 3.12
  - Topic :: Software Development :: Libraries :: Python Modules
  - Topic :: Scientific/Engineering
- project.urls:
  - Homepage = `https://padelkit.dev`
  - Documentation = `https://padelkit.dev`
  - Source = GitHub repo
  - Issues = GitHub issues

Configurar ruff y pytest si procede.

---

# Tests

Crear tests simples pero reales:

Para `court`:

- `PadelCourt.fip_standard()` devuelve largo 20 y ancho 10.
- El centro es `(0, 0)`.
- Las cuatro esquinas tienen coordenadas esperadas:
  - `(-5, -10)`
  - `(5, -10)`
  - `(-5, 10)`
  - `(5, 10)`
- Hay landmarks básicos.
- `point("center")` funciona.
- pedir un punto inexistente lanza una excepción adecuada, probablemente `KeyError`.

Para `scoring`:

- marcador inicial es 0-0.
- después de un punto de A, el score refleja 15-0.
- secuencia de cuatro puntos gana un juego.
- deuce/advantage funciona si se implementa.
- juegos avanzan correctamente.

---

# GitHub Actions

Crear workflow simple:

```txt
.github/workflows/ci.yml
```

Que ejecute:

- checkout
- setup-python en 3.10, 3.11, 3.12
- install dev dependencies
- ruff check
- pytest
- python -m build

No configurar todavía publicación automática a PyPI salvo que sea limpio y seguro. Si se añade workflow de publicación, debe usar Trusted Publishing y no tokens hardcodeados.

---

# Build local

Al final, comprobar que funcionan estos comandos:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
ruff check .
pytest
python -m build
python -m twine check dist/*
```

Si `twine` no está en dev dependencies, añadirlo o indicar el comando correspondiente.

---

# Entregable final esperado

Al terminar:

1. El repo debe contener una librería Python mínima funcional.
2. Debe poder instalarse en editable mode.
3. Deben pasar tests.
4. Debe poder construirse un wheel y sdist.
5. Debe estar listo para que yo publique manualmente en PyPI.
6. Debes mostrarme:
   - resumen de archivos creados/modificados
   - comandos ejecutados
   - resultado de tests/build
   - siguientes pasos exactos para publicar en PyPI

---

# No hacer por ahora

No implementar todavía:

- Calibración de cámara con OpenCV.
- Física de pelota.
- Tracking.
- Modelos de inferencia.
- Integraciones con Padelamix.
- Documentación con Tailwind Plus/Protocol.
- App frontend.
- Dependencias pesadas.
- Publicación real en PyPI sin mi confirmación explícita.

La prioridad es una primera versión pequeña, estable y publicable.

Antes de empezar, inspecciona el estado actual del repositorio con `ls`, `find` y `git status`. No sobrescribas trabajo existente sin avisar. Si el repo está vacío, crea la estructura propuesta. Si ya hay archivos, adapta la solución respetando lo existente. Recuerda nunca hacer git commit ni git push, déjame eso a mí.

Ignora por completo la web de documentación privada por ahora. El dominio `padelkit.dev` ya existe, pero en esta tarea solo queremos preparar el paquete Python para PyPI.

```