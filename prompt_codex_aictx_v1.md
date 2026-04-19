# Prompt para Codex — llevar `aictx` a una v1 real, limpia y publicable

## Objetivo

Quiero que implementes una evolución completa de `aictx` para dejar el repositorio en estado **v1 real**, técnicamente sólido, sin simulaciones ni métricas inventadas, preparado para una demo reproducible y para publicación pública ante perfiles técnicos exigentes.

El resultado final debe dejar `aictx` como:

- un **repo-local runtime** para agentes de código
- con **métricas 100% reales y trazables**
- con **strategy memory** basada en ejecuciones reales
- con **feedback útil al final de cada tarea**
- con **uso automático por parte del agente** (sin intervención manual del usuario)
- con **surface UX mínima** y coherente
- sin humo, sin “fake benchmarks”, sin claims no medidos
- con documentación y posicionamiento honestos y atractivos

---

## Contexto y criterio de producto

La propuesta correcta de `aictx` NO es:
- “memoria mágica”
- “más contexto”
- “benchmarks sintéticos”
- “scores heurísticos decorativos”

La propuesta correcta de `aictx` SÍ es:
- **runtime contract repo-local**
- **execution discipline**
- **persistencia estructurada**
- **aprendizaje basado en tareas reales**
- **guidance al agente durante la ejecución**
- **medición verificable del impacto real**

---

## Requisitos obligatorios

### 1) Eliminar toda simulación y métrica no real

Esto es no negociable.

Debes:
- eliminar del flujo productivo cualquier benchmark, simulación o métrica sintética
- quitar cualquier lógica que genere métricas inventadas o derivadas de funciones tipo `simulate_run`, `stable_score`, etc.
- eliminar cualquier narrativa o output que pueda interpretarse como rendimiento real si no lo es
- si alguna parte sintética se conserva por valor histórico o experimental, debe moverse fuera del core productivo, fuera del flujo principal, y quedar claramente marcada como experimental/no productiva

**El repositorio final no puede parecer inflado ni tramposo a ojos de un perfil técnico.**

---

### 2) Sustituir el benchmark sintético por medición real

El producto debe medir solo datos observables de ejecuciones reales.

Debes implementar un sistema de medición real que permita comparar ejecuciones baseline vs ejecuciones con `aictx`, pero sin inventar resultados.

Datos válidos:
- ficheros abiertos
- ficheros reabiertos
- duración real de ejecución
- éxito/fracaso
- uso real de packet / strategy / memoria
- hints reutilizados
- trazas de ejecución observables

Datos no válidos:
- tokens estimados si no vienen del runner
- scores artificiales
- mejoras inferidas sin evidencia
- calidad sintética
- pass rates inventados

---

### 3) Añadir strategy memory basada en tareas reales

Quiero una capa nueva de memoria de estrategia, separada de la memoria actual, basada en ejecuciones que realmente han acabado bien.

Debe guardar al menos:
- task type
- fingerprint mínimo de la tarea
- entry points reales útiles
- files usados
- pasos/approach resumidos de forma estructurada
- outcome
- timestamp
- evidencia mínima de reutilización

No quiero una capa “AI-looking”. Quiero una capa sobria, útil y verificable.

---

### 4) Reutilización real en `prepare_execution`

Cuando llega una tarea nueva:
- si hay estrategias previas exitosas relevantes, deben reutilizarse
- el output de `prepare_execution()` debe incluir `execution_hint` o estructura equivalente
- ese hint debe estar basado en estrategias reales previas, no en scores decorativos

El hint debe ayudar al agente a:
- abrir primero los ficheros más prometedores
- evitar exploración redundante
- evitar rutas ya fallidas
- converger más rápido

---

### 5) Añadir comandos mid-execution para uso por el agente

Quiero comandos CLI claros, pensados para que los ejecute el agente automáticamente:

- `aictx suggest`
- `aictx reflect`
- `aictx reuse`

Si consideras que los nombres deben ser ligeramente distintos por coherencia de CLI, puedes proponerlo, pero mantén el espíritu.

Estos comandos deben:
- devolver solo datos reales o derivados de historial real
- no usar confidence fake
- no devolver humo
- ser útiles dentro del loop de trabajo del agente

Ejemplos esperables:
- sugerir próximos ficheros
- reflejar si se están reabriendo los mismos ficheros
- reutilizar estrategias reales previas

---

### 6) Integración para uso automático por el agente

Quiero que el agente use `aictx` de forma automática, sin intervención del usuario.

Eso implica:
- actualizar instrucciones repo-level y runner-level
- enseñar al agente cuándo llamar a `aictx suggest`, `reflect`, `reuse`
- hacerlo especialmente para:
  - apertura de demasiados ficheros
  - relecturas
  - tareas similares a previas
  - incertidumbre sobre próximo paso

No quiero que esto dependa de que el usuario “se acuerde” de ejecutar nada manualmente.

---

### 7) Feedback final útil tras cada tarea

Cuando termina una tarea, el sistema debe producir feedback real y útil sobre lo que aportó `aictx`.

Ese feedback debe:
- ser operativo
- no narrativo
- no marketiniano
- no inventado

Ejemplos válidos:
- cuántos ficheros se abrieron
- cuántos se reabrieron
- si se reutilizó estrategia previa
- si se usó packet
- si se evitó exploración redundante detectable

Ese feedback debe:
- devolverse al final de la ejecución
- persistirse
- poder alimentar futuras decisiones del sistema

---

### 8) UX mínima y v1-ready

La experiencia v1 debe quedar conceptualmente así:

```bash
pip install aictx
aictx install
aictx init
```

Y a partir de ahí:
- el repo queda instrumentado
- el agente aprovecha `aictx`
- hay métricas reales
- hay hints reutilizables
- hay reportes reales
- no hace falta babysitting del usuario

No añadas fricción innecesaria.

---

## Resultado esperado de producto

Al acabar, `aictx` debe quedar posicionado y preparado como:

> a repo-local runtime layer for coding agents that measures real execution, reuses successful strategies, and reduces redundant exploration over time

No como:
- “framework”
- “prompt pack”
- “magic memory”
- “synthetic benchmark engine”

---

# Cambios a implementar

## A. Limpieza de simulaciones y claims sintéticos

### Revisar y modificar / mover fuera del core:
- `src/aictx/benchmark.py`
- cualquier otro módulo que produzca simulación, estimación artificial o métricas inventadas
- `README.md`
- `docs/BENCHMARK_QUICKSTART.md`
- cualquier doc que prometa o sugiera mejoras no medidas

### Objetivo:
- el benchmark actual basado en simulación no puede seguir formando parte del core vendible del producto
- si se conserva, debe quedar explícitamente fuera del runtime productivo

---

## B. Instrumentación real de ejecución

### Modificar:
- `src/aictx/middleware.py`
- `src/aictx/runtime_launcher.py`
- `src/aictx/agent_runtime.py`
- si hace falta, crear nuevos módulos bajo `src/aictx/`

### Implementar:
- captura real de ejecución
- logging real por tarea
- persistencia en `.ai_context_engine/metrics/`
- estructura extensible pero sobria

### Crear o actualizar artifacts:
- `.ai_context_engine/metrics/execution_logs.jsonl`
- `.ai_context_engine/metrics/execution_status.json`
- cualquier otro artifact necesario, siempre basado en datos reales

---

## C. Strategy memory

### Crear:
- `src/aictx/strategy_memory.py` (o nombre equivalente coherente)
- scaffold repo-local para:
  - `.ai_context_engine/strategy_memory/`
  - estado e índices necesarios

### Modificar:
- `src/aictx/scaffold.py`
- `src/aictx/middleware.py`
- `src/aictx/runtime_launcher.py` si aplica
- `src/aictx/state.py` para declarar nuevas rutas si es necesario

### Requisitos:
- generación automática al finalizar tareas exitosas validadas
- lectura/reutilización durante `prepare_execution()`
- sin ML ni humo
- basado en historial real

---

## D. Reutilización en `prepare_execution`

### Modificar:
- `src/aictx/middleware.py`
- `src/aictx/runtime_tasks.py` si la lógica de packet debe enriquecerse
- módulos auxiliares necesarios

### Añadir:
- `execution_hint`
- entry points sugeridos
- strategy reuse basado en tareas previas

### Condición:
- si no hay evidencia suficiente, debe devolverse vacío o `unknown`
- nunca inventar

---

## E. Comandos nuevos para runtime mid-execution

### Añadir comandos CLI:
- `aictx suggest`
- `aictx reflect`
- `aictx reuse`

### Revisar:
- entrypoints CLI existentes
- `__main__`
- parser de argparse
- docs de uso

### Comportamiento:
- datos reales
- salidas útiles para agente
- JSON limpio y deterministic-friendly

---

## F. Uso automático por el agente

### Modificar:
- `src/aictx/runner_integrations.py`
- `src/aictx/agent_runtime.py`
- runtime/instruction blocks que se escriben en:
  - `AGENTS.override.md`
  - `CLAUDE.md`
  - `.claude/settings.json`
  - hooks `.claude/hooks/*`

### Reglas a enseñar al agente:
- antes de abrir demasiados ficheros → `aictx suggest`
- si reabre ficheros → `aictx reflect`
- si detecta tarea similar → `aictx reuse`
- si duda sobre siguiente paso → `aictx suggest`

### Importante:
- no sobrecargar las instrucciones con texto innecesario
- redactarlas para que sean muy utilizables por agentes reales

---

## G. Feedback final

### Modificar:
- `src/aictx/middleware.py`
- `src/aictx/runtime_launcher.py` si aplica
- docs relevantes

### Añadir en finalize:
- `aictx_feedback`
- persistencia de ese feedback
- posibilidad de reutilización posterior

### El feedback debe incluir solo cosas como:
- files_opened
- reopened_files
- used_strategy
- used_packet
- maybe_redundant_exploration_detected
- previous_strategy_reused

Sin narrativa marketiniana.

---

## H. Reporte real de uso

### Añadir:
- comando/report real:
  - `aictx report real-usage`
  - o equivalente coherente con la CLI actual

### Debe mostrar:
- métricas agregadas reales
- baseline vs aictx cuando exista
- estado de evidencia
- suficiente info para preparar demo/publicación
- sin claims inventados

---

## I. Simplificación y limpieza del repo

### Revisar y limpiar:
- scripts redundantes en `scripts/`
- docs obsoletas
- referencias a benchmark sintético
- naming inconsistente
- surface pública excesiva

### Objetivo:
- repo impecable ante un perfil técnico
- pero también claro y atractivo para un perfil no tan profundo

---

# Condiciones de diseño

## 1. Honestidad radical
Si no hay dato real:
- devolver `unknown`
- no inferir como verdad
- no llenar huecos con heurística vendida como medición

## 2. Compatibilidad con lo existente
Haz cambios incrementales y coherentes con la arquitectura actual.
No reescribas todo innecesariamente.

## 3. Mantener el valor actual del producto
Conservar:
- runtime contract
- scaffold repo-local
- integrations runner-aware
- middleware prepare/finalize
- packet system donde siga teniendo sentido

## 4. Reducir claims, aumentar evidencia
El repo final debe convencer más por:
- estructura
- trazabilidad
- outputs reales

que por lenguaje de marketing.

---

# Deliverables obligatorios

## 1. Código
Implementación completa de lo anterior.

## 2. Docs actualizadas
Actualizar al menos:
- `README.md`
- `docs/TECHNICAL_OVERVIEW.md`
- `docs/DEMO.md`
- `docs/LIMITATIONS.md`
- docs del benchmark/report si cambian o desaparecen
- docs de uso para nuevos comandos

## 3. CLI usable
Los comandos nuevos deben funcionar y tener ayuda clara.

## 4. Estado v1-ready
El repo debe quedar listo para:
- hacer una demo real
- publicar públicamente una v1
- ser revisado por un perfil técnico sin que encuentre simulaciones escondidas o métricas dudosas

---

# Qué NO hacer

- no dejar simulaciones en el flujo productivo
- no mantener métricas sintéticas con otro nombre
- no introducir “confidence” ficticio
- no meter LLM magic donde no hace falta
- no complicar la UX
- no romper el flujo `install + init`
- no sobreprometer en README/docs

---

# Criterios de aceptación (DoD)

La tarea solo está terminada si:

1. no queda ninguna simulación en el core vendible del producto
2. las métricas del producto son reales y trazables
3. existe strategy memory funcional y basada en ejecuciones reales
4. `prepare_execution()` reutiliza estrategia previa cuando procede
5. existen comandos tipo `suggest/reflect/reuse`
6. el agente está instruido para usarlos automáticamente
7. `finalize_execution()` genera feedback útil y persistido
8. existe una vía de reporte real de uso
9. README y docs reflejan el producto real sin humo
10. el repo queda técnicamente impecable y listo para v1 pública

---

# Enfoque de implementación esperado

Trabaja en este orden:

1. limpiar simulaciones / benchmark sintético / claims
2. instrumentación real
3. strategy memory
4. execution hints en prepare
5. nuevos comandos CLI
6. integración automática con runners
7. feedback final
8. reporting real
9. limpieza final de docs y surface pública

---

# Salida que quiero de ti al terminar

1. resumen de cambios realizados
2. lista de ficheros modificados
3. lista de ficheros nuevos
4. explicación breve de la nueva arquitectura
5. comandos para validar manualmente el flujo completo
6. notas sobre cualquier limitación real que permanezca

---

# Importante

Prefiero:
- menos features
- más verdad
- más trazabilidad
- más claridad
- mejor producto

sobre:
- más complejidad
- más capas
- más heurística
- más apariencia de inteligencia

Implementa con criterio de producto serio.
