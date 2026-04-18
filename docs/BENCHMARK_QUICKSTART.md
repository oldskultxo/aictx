# Benchmark Quickstart (A/B/C)

## 1) Crear suite

Guarda un `benchmark_suite.json`:

```json
{
  "repos": [
    "/abs/path/repo-1",
    "/abs/path/repo-2",
    "/abs/path/repo-3"
  ],
  "tasks": [
    {"id": "task_01", "prompt": "implement feature X", "task_type": "feature_work"},
    {"id": "task_02", "prompt": "fix failing test Y", "task_type": "testing"}
  ],
  "seeds": [1, 2, 3],
  "acceptance_checks": ["tests_pass", "no_regression"]
}
```

## 2) Ejecutar brazos A/B/C

```bash
aictx benchmark run --suite benchmark_suite.json --arm A --out .ai_context_engine/metrics/benchmark_runs
aictx benchmark run --suite benchmark_suite.json --arm B --out .ai_context_engine/metrics/benchmark_runs
aictx benchmark run --suite benchmark_suite.json --arm C --out .ai_context_engine/metrics/benchmark_runs
```

## 3) Generar reporte

```bash
aictx benchmark report --input .ai_context_engine/metrics/benchmark_runs --format json
aictx benchmark report --input .ai_context_engine/metrics/benchmark_runs --format md
```

Artefactos:
- `.ai_context_engine/metrics/benchmark_runs/benchmark_report.json`
- `.ai_context_engine/metrics/benchmark_runs/benchmark_report.md`

## 4) Gating de publicación

`claim_label` será:
- `material_repeatable` si cumple:
  - >= 3 repos
  - >= 12 tareas por repo
  - >= 3 seeds por tarea
  - A/B/C completos
- `exploratory` en caso contrario

No publicar claims fuertes si `claim_label != material_repeatable`.
