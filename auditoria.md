
# Auditoría profesional de producto y técnica de AICTX

## 1. Diagnóstico actual del producto

AICTX ya tiene una tesis fuerte: **runtime ligero de continuidad repo-local para agentes de código**. El README, `pyproject.toml` y la CLI pública apuntan en esa dirección: `install`, `init`, `resume`, `finalize`, `view`, `doctor`.

Pero el repositorio emite señales contradictorias:

- **Núcleo claro:** resume capsule, finalize, Work State, handoffs, decisions, Failure Memory, MCP/CLI, Continuity View, RepoMap opcional.
- **Superficie demasiado grande:** 76 módulos en `src/aictx`, 26k LOC, 70 tests, 565 tests, muchos comandos ocultos y varias generaciones de runtime coexistiendo.
- **Documentación sobredimensionada:** `docs/` tiene 66 archivos y 7.8 MB, con páginas SEO, HTML estático, imágenes grandes y guías repetidas.
- **Código legacy visible:** `runtime_knowledge.py`, `runtime_memory.py`, `runtime_graph.py`, `runtime_task_memory.py`, scripts `ctx-*`, comandos `internal`, `suggest`, `reuse`, `next`, `reflect`, `task-memory`, `memory-graph` parecen de una etapa anterior más parecida a “memory framework”.
- **Calidad técnica real:** la suite pasa: `565 passed in 63.60s`. El proyecto no está roto.
- **Calidad de continuidad propia mala:** `aictx doctor` reporta `continuity quality: 44/100`, decisiones obsoletas, referencias a rutas antiguas como `src/aictx/continuity.py`, y contrato histórico con gaps. Esto daña la credibilidad de un producto que vende continuidad.

Conclusión: **el producto es prometedor, pero necesita recorte.** Hoy parece mitad herramienta profesional enfocada, mitad laboratorio acumulativo de memoria/agent-runtime.

---

## 2. Superficie central del producto

| Componente | Por qué pertenece al núcleo | Problema que resuelve | Mejora necesaria |
|---|---|---|---|
| `aictx install` / `aictx init` | Primeros 5 minutos del producto | Instala runtime y genera integración repo-local | Reducir prompts, explicar exactamente qué archivos toca |
| `aictx resume --repo . --task ... --json` | Es la promesa principal | Evita redescubrimiento al inicio de sesión | Payload más estable, menos ruido, mejor calidad de selección |
| `aictx finalize --status ... --summary ... --json` | Cierra el loop | Guarda evidencia para la siguiente sesión | Captura más fiable de comandos/tests/files |
| Work State | Estado vivo de trabajo suspendido | Continuar tareas interrumpidas | Reforzar como “suspended work”, no task manager |
| Handoffs + Decisions | Memoria explícita y durable | No repetir decisiones/contexto clave | UI/CLI simple para inspección y limpieza |
| Failure Memory | Diferenciador fuerte | No repetir comandos o enfoques fallidos | Mejor modelo de “fallo accionable” vs ruido histórico |
| MCP + CLI fallback | Encaja con agentes reales | Funciona con Codex/Claude/Copilot/runners distintos | Hacer la superficie MCP tan pequeña como la CLI principal |
| Continuity Quality / Doctor | Profesionaliza la confianza | Sabe cuándo la memoria no es fiable | Promocionar `doctor`; añadir comando de repair/cleanup guiado |
| Continuity View | Inspeccionabilidad | Hace visible la memoria repo-local | Mantener como inspectable, no como dashboard principal |
| RepoMap opcional | Ayuda a elegir entrypoints | Evita escaneo bruto inicial | Mantener estrictamente opcional y secundario |

---

## 3. Funcionalidades a eliminar, ocultar, deprecar, rebajar o fusionar

| Elemento | Recomendación | Por qué no encaja actualmente | Riesgo | Zonas afectadas |
|---|---:|---|---|---|
| `runtime_knowledge.py` / “mod library” / remote ingest | **ELIMINAR o DEPRECAR** | Parece RAG/document ingestion, no continuidad repo-local ligera | Posiciona AICTX como framework de conocimiento pesado | `src/aictx/runtime_knowledge.py`, docs técnicas, comandos internal |
| `runtime_memory.py`, `.aictx_memory`, generic memory store | **FUSIONAR/ELIMINAR** | Duplica continuidad con memoria genérica | Confunde “operational continuity” con memory DB | `src/aictx/runtime_memory.py`, `core_runtime`, docs legacy |
| `runtime_graph.py` / memory graph | **REBAJAR** | Suena a knowledge graph experimental | Gimmick si no aporta al loop resume/finalize | `src/aictx/runtime_graph.py`, `bin/ctx-graph`, docs technical |
| `runtime_task_memory.py` / task-memory | **DEPRECAR** | Se parece a task manager/memory taxonomy | Dilución del modelo mental | `src/aictx/runtime_task_memory.py`, scripts, `aictx internal task-memory` |
| `aictx suggest`, `reuse`, `next`, `reflect` | **OCULTAR o FUSIONAR en `resume`/`doctor`** | Son comandos paralelos al loop principal | Usuarios no saben cuál usar | `src/aictx/cli/__init__.py`, docs/USAGE.md |
| `aictx task ...` | **REBAJAR** | Work State sí; task manager no | Scope creep | CLI task subcommands, docs/WORK_STATE.md |
| Area Memory | **FUSIONAR** | Es señal interna, no concepto público fuerte | Demasiados “tipos de memoria” | `src/aictx/area_memory.py`, docs/AREA_MEMORY.md |
| Strategy Memory como feature pública | **REESCRIBIR** | Buena idea, nombre parece agente planificador | Puede sonar a automatización no confiable | `src/aictx/strategy_memory.py`, docs/STRATEGY_MEMORY.md |
| SEO/docs website cluster | **REBAJAR** | Mucho marketing comparativo antes de producto estable | Parecer growth-hack, no devtool serio | `docs/compare`, `docs/concepts`, HTML estático |
| Imágenes grandes incluidas en package | **REBAJAR/EXCLUIR de wheel** | `MANIFEST.in` incluye `docs *`; docs/images pesan mucho | Bloat de distribución | `MANIFEST.in`, docs/images |
| Scripts `bin/ctx-*` y `scripts/*.py` bash disguised as `.py` | **DEPRECAR** | Superficie legacy extraña | Mala señal profesional | `bin/`, `scripts/` |
| `caveman_*` communication modes como feature visible | **REBAJAR** | Suena gimmicky | Resta seriedad | `runtime_contract.py`, docs INSTALLATION/USAGE |
| Open-Launch/star CTAs en README/docs | **REBAJAR** | Marketing social antes de confianza técnica | Menos credibilidad OSS | `README.md`, `docs/index.html`, layout |

---

## 4. Capacidades ausentes que deberían añadirse

Prioridad alta:

- **`aictx doctor --fix-plan` o `aictx cleanup-plan`:** reporte accionable de memoria obsoleta, rutas inexistentes, sesiones sin finalize.
- **`aictx continuity prune` seguro:** limpiar decisiones/handoffs/failures obsoletos sin borrar `.aictx` manualmente.
- **Guía “what gets written where”:** tabla clara de archivos generados por `install`, `init`, `resume`, `finalize`, `view`.
- **Golden end-to-end tests de primer uso:** fresh repo → init → resume → finalize → second resume.
- **Policy de payload estable:** documentar qué campos JSON son public contract vs diagnostic.
- **Mejor failure memory:** separar errores reales reutilizables de “resúmenes de tareas fallidas”.
- **Release/package hygiene:** excluir docs pesados del wheel salvo docs mínimas necesarias.

Prioridad media:

- **Score medible de continuidad útil:** no prometer token savings; medir “loaded relevant context”, “stale ratio”, “missing path ratio”.
- **`aictx inspect` simple:** una vista humana corta: active work, last handoff, decisions, failures, quality.
- **Compat matrix por runner:** Codex / Claude / Copilot / generic con qué puede automatizar cada uno.
- **Docs de integración por agente más pequeñas:** una página por agente, sin duplicar toda la teoría.

---

## 5. Forma ideal del producto profesional

### Superficie principal

```text
aictx install
aictx init
aictx resume --repo . --task "<goal>" --json
aictx finalize --repo . --status success|failure --summary "<summary>" --json
aictx view --repo .
aictx doctor --repo . --json
aictx clean --repo .
```

Avanzado, fuera del camino principal:

```text
aictx mcp status/install
aictx portability status/compact
aictx map status/query/refresh
aictx guard
aictx steer
```

Legacy/oculto:

```text
internal, suggest, reuse, next, reflect, task-memory, memory-graph, ctx-* wrappers
```

### Modelo mental recomendado

```text
Repo-local continuity, not agent memory platform.

resume = what the next agent should know before work
finalize = what this session proved/did
doctor = whether continuity is trustworthy
view = inspect what is stored
```

### README ideal

Debe mostrar:

1. Problema: agentes empiezan fríos.
2. Loop: `resume -> work -> finalize`.
3. 60-second setup.
4. Ejemplo real de resume/finalize.
5. Qué guarda y qué no guarda.
6. MCP/CLI fallback.
7. Trust model: local, inspectable, advisory.
8. Link a docs mínimas.

Debe quitar o bajar:

- Star CTA agresivo.
- Open-Launch badge como prueba central.
- Listas largas de features.
- SEO comparison links en la primera impresión.
- Imágenes grandes si desplazan la comprensión.

### Primeros 5 minutos ideales

```bash
pip install aictx
aictx init --repo .
aictx doctor --repo .
aictx resume --repo . --task "first test" --json
aictx finalize --repo . --status success --summary "Initialized AICTX and verified lifecycle" --json
aictx view --repo .
```

El usuario debe entender exactamente:
- qué archivos aparecieron;
- qué queda en `.aictx/`;
- qué verá su agente al empezar;
- cómo apagarlo o limpiarlo.

---

## 6. Roadmap

### Fase 1: Recortar y clarificar

- **Tareas**
  - Reescribir README alrededor de `resume -> finalize`.
  - Mover `suggest/reuse/next/task/map/report/internal` a “advanced/legacy”.
  - Quitar docs SEO de la ruta principal.
  - Marcar `runtime_knowledge`, generic memory graph/task memory como legacy.
  - Arreglar help CLI inconsistente: `mcp`, `guard`, `steer` aparecen descritos pero no en la lista de choices visible.
- **Áreas**
  - `README.md`, `docs/USAGE.md`, `docs/TECHNICAL_OVERVIEW.md`, `src/aictx/cli/__init__.py`.
- **Resultado**
  - Producto explicable en 2 minutos.
- **Riesgo**
  - Bajo/medio.
- **Complejidad**
  - Media.

### Fase 2: Estabilizar flujos principales

- **Tareas**
  - Tests E2E fresh repo lifecycle.
  - Contract tests para JSON público de `resume` y `finalize`.
  - Mejorar `doctor` para convertir `continuity quality: 44/100` en acciones.
  - Separar public fields vs diagnostics.
  - Verificar package build y reducir wheel/sdist.
- **Áreas**
  - `tests/test_resume_command.py`, `tests/test_smoke.py`, `tests/test_doctor.py`, `MANIFEST.in`.
- **Resultado**
  - Loop confiable y auditable.
- **Riesgo**
  - Medio.
- **Complejidad**
  - Media.

### Fase 3: Reforzar diferenciación

- **Tareas**
  - Handoff más claro: qué debe continuar, qué quedó validado, qué no.
  - Failure Memory más precisa y menos ruidosa.
  - Continuity Quality como indicador principal de confianza.
  - Continuity View enfocada en “what should the next agent know”.
- **Áreas**
  - `continuity/`, `failure_memory.py`, `continuity_view.py`, `doctor.py`.
- **Resultado**
  - AICTX se diferencia de chat history, AGENTS.md y RAG.
- **Riesgo**
  - Medio.
- **Complejidad**
  - Media/grande.

### Fase 4: Capa avanzada opcional

- **Tareas**
  - RepoMap avanzado.
  - Portability para equipos pequeños.
  - MCP full profile.
  - Guard/Steer como runner hardening.
  - Strategy reuse solo como hint interno.
- **Áreas**
  - `repo_map/`, `portability.py`, `mcp/`, `continuity_guard.py`, `steer_guard.py`.
- **Resultado**
  - Power users sin contaminar el producto principal.
- **Riesgo**
  - Medio.
- **Complejidad**
  - Grande si se mantiene todo; media si se encapsula.

---

## 7. Tabla final mantener / recortar / añadir

| Componente / funcionalidad | Estado actual | Recomendación | Motivo | Prioridad | Archivos/áreas |
|---|---|---|---|---:|---|
| Resume capsule | Fuerte | Mantener | Núcleo del producto | Alta | `continuity/`, `mcp/tools.py`, CLI |
| Finalize summary | Fuerte | Mantener | Cierra continuidad | Alta | `middleware/`, `continuity/` |
| Work State | Útil pero amplio | Mantener con límites | Suspended work, no task manager | Alta | `work_state.py`, docs |
| Handoffs/Decisions | Núcleo | Mantener | Memoria explícita | Alta | `docs/HANDOFFS.md`, continuity |
| Failure Memory | Diferenciador | Reescribir parcialmente | Debe ser accionable | Alta | `failure_memory.py`, `failures/` |
| Doctor | Bueno | Expandir | Profesionaliza confianza | Alta | `doctor.py` |
| Continuity Quality | Bueno pero alerta | Expandir | Hoy detecta problemas reales | Alta | `continuity/quality.py` |
| Continuity View | Bueno | Mantener/rebajar visual | Inspección, no dashboard | Media | `continuity_view.py` |
| RepoMap | Útil opcional | Mantener avanzado | Ayuda a entrypoints | Media | `repo_map/` |
| MCP | Fuerte | Mantener | Integración real con agentes | Alta | `mcp/` |
| Portability | Valioso avanzado | Rebajar | Equipos, no primer uso | Media | `portability.py` |
| Guard/Steer | Útil runner-hardening | Rebajar | Avanzado/agente | Media | `continuity_guard.py`, `steer_guard.py` |
| Strategy Memory | Ambigua | Reescribir como “prior successful hints” | Evitar planner vibes | Media | `strategy_memory.py` |
| Area Memory | Secundaria | Fusionar interna | Otro concepto público sobra | Baja | `area_memory.py` |
| Generic memory store | Legacy | Eliminar/deprecar | Diluye producto | Alta | `runtime_memory.py` |
| Knowledge ingest/mod library | Legacy | Eliminar/deprecar | Parece RAG | Alta | `runtime_knowledge.py` |
| Memory graph | Experimental | Rebajar/deprecar | Gimmick si visible | Media | `runtime_graph.py` |
| Task memory taxonomy | Legacy | Deprecar | Confunde con task manager | Media | `runtime_task_memory.py` |
| `suggest/reuse/next/reflect` | Oculto pero documentado | Fusionar/ocultar más | Superficie redundante | Alta | CLI/docs |
| `bin/ctx-*`, script wrappers | Legacy | Deprecar | Mala señal profesional | Media | `bin/`, `scripts/` |
| SEO docs clusters | Excesivo | Rebajar | Distraen del producto | Media | `docs/compare`, `docs/concepts` |
| Heavy docs/images in package | Actual | Excluir del wheel | Bloat | Alta | `MANIFEST.in` |

---

## 8. Prompts de implementación

### Prompt 1 — Ejecutar solo Fase 1

```text
Audita y ejecuta la Fase 1 de recorte/clarificación de AICTX sin tocar comportamiento runtime crítico.

Objetivo:
hacer que el producto se explique como “runtime ligero de continuidad repo-local para agentes de código” centrado en install/init/resume/finalize/view/doctor.

Tareas:
- Reescribe README.md para priorizar el loop resume -> work -> finalize.
- Mueve comandos y conceptos avanzados/legacy fuera del camino principal en docs/USAGE.md y docs/TECHNICAL_OVERVIEW.md.
- Marca suggest/reuse/next/reflect/task/internal/map/report como avanzado o legacy.
- Rebaja Strategy Memory, Area Memory, memory graph, generic memory y knowledge ingest como internos/legacy.
- No elimines código todavía salvo referencias documentales claramente obsoletas.
- Mantén todos los comandos existentes funcionando.
- Ejecuta PYTHONPATH=src .venv/bin/python -m pytest -q.
```

### Prompt 2 — Ejecutar solo Fase 2

```text
Ejecuta la Fase 2 de estabilización de flujos principales de AICTX.

Objetivo:
endurecer los flujos install/init/resume/finalize/view/doctor y documentar el contrato público JSON.

Tareas:
- Añade tests E2E de fresh repo: init -> resume -> finalize -> second resume -> view/doctor.
- Añade tests de compatibilidad para campos públicos de resume/finalize.
- Mejora doctor para convertir continuidad obsoleta/missing/stale en acciones concretas.
- Revisa MANIFEST.in para reducir bloat del paquete sin romper docs publicadas.
- No añadas features grandes.
- Ejecuta PYTHONPATH=src .venv/bin/python -m pytest -q y, si procede, make package-check.
```

### Prompt 3 — Reescribir README y docs de posicionamiento

```text
Reescribe README.md y la documentación de posicionamiento de AICTX después de las decisiones de recorte.

Tesis obligatoria:
AICTX es un runtime ligero de continuidad repo-local para agentes de código. Ayuda a nuevas sesiones a empezar con memoria útil del proyecto: decisiones, fallos, estado actual, contexto de tarea y handoff. No es agente, vector DB, dashboard, RAG ni task manager.

Entregables:
- README.md nuevo, sobrio y técnico.
- docs/QUICK-START.md alineado con primeros 5 minutos.
- docs/USAGE.md con superficie principal vs avanzada.
- docs/TECHNICAL_OVERVIEW.md más corto, sin vender features legacy como core.
- Mantén enlaces reales y comandos correctos.
- No inventes métricas de productividad.
- Ejecuta tests de docs/CLI existentes.
```

## Validación hecha

- `PYTHONPATH=src .venv/bin/python -m pytest -q` → `565 passed in 63.60s`.
- `PYTHONPATH=src python3 -m pytest -q` falló porque el Python del sistema no tiene `pytest`.
- `aictx doctor` reportó estado `error` por `continuity quality: 44/100`, memoria obsoleta y gaps históricos.
- `aictx guard --repo . --action final_answer --json` → `decision: caution`, por decisión obsoleta en continuity quality.
- No implementé cambios de producto/código.

