from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


VALID_ARMS = {"A", "B", "C"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def stable_score(key: str, lo: float = 0.0, hi: float = 1.0) -> float:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    bucket = int(digest[:16], 16) / float(16**16 - 1)
    return lo + (hi - lo) * bucket


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * p))))
    return float(ordered[idx])


def variance(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    avg = sum(values) / len(values)
    return sum((item - avg) ** 2 for item in values) / len(values)


@dataclass
class SuiteSelection:
    repos: list[str]
    tasks: list[dict[str, Any]]
    seeds: list[int]
    acceptance_checks: list[str]


def parse_suite(path: Path) -> dict[str, Any]:
    payload = read_json(path, {})
    if not isinstance(payload, dict):
        raise ValueError("Suite file must be a JSON object.")
    repos = payload.get("repos", [])
    tasks = payload.get("tasks", [])
    seeds = payload.get("seeds", [])
    checks = payload.get("acceptance_checks", [])
    if not repos or not isinstance(repos, list):
        raise ValueError("Suite must define repos[]")
    if not tasks or not isinstance(tasks, list):
        raise ValueError("Suite must define tasks[]")
    if not seeds or not isinstance(seeds, list):
        raise ValueError("Suite must define seeds[]")
    for task in tasks:
        if not isinstance(task, dict) or not str(task.get("id", "")).strip():
            raise ValueError("Each task entry must include a non-empty id.")
        if not str(task.get("prompt", "")).strip():
            raise ValueError(f"Task {task.get('id')} must include prompt.")
    payload["repos"] = [str(repo) for repo in repos]
    payload["tasks"] = tasks
    payload["seeds"] = [int(seed) for seed in seeds]
    payload["acceptance_checks"] = [str(item) for item in checks]
    return payload


def select_suite_rows(
    suite: dict[str, Any],
    selected_repo: str | None,
    selected_seed: int | None,
) -> SuiteSelection:
    repos = list(suite["repos"])
    if selected_repo:
        repos = [repo for repo in repos if Path(repo).resolve().as_posix() == Path(selected_repo).resolve().as_posix() or repo == selected_repo]
    seeds = list(suite["seeds"])
    if selected_seed is not None:
        seeds = [seed for seed in seeds if seed == selected_seed]
    if not repos:
        raise ValueError("No repos matched --repo filter.")
    if not seeds:
        raise ValueError("No seeds matched --seed filter.")
    return SuiteSelection(
        repos=repos,
        tasks=list(suite["tasks"]),
        seeds=seeds,
        acceptance_checks=[str(item) for item in suite.get("acceptance_checks", [])],
    )


def arm_factor(arm: str) -> dict[str, float]:
    if arm == "A":
        return {"token_mult": 1.00, "latency_mult": 1.00, "cost_mult": 1.00, "quality_bias": -0.06}
    if arm == "B":
        return {"token_mult": 0.88, "latency_mult": 0.90, "cost_mult": 0.88, "quality_bias": 0.02}
    return {"token_mult": 0.74, "latency_mult": 0.80, "cost_mult": 0.74, "quality_bias": 0.08}


def simulate_run(repo: str, task: dict[str, Any], seed: int, arm: str, checks: list[str], suite_hash: str) -> dict[str, Any]:
    factors = arm_factor(arm)
    task_id = str(task["id"])
    key = f"{suite_hash}|{repo}|{task_id}|{seed}|{arm}"

    base_tokens = int(2100 + stable_score(f"{key}:tokens", 0, 3800))
    base_latency = int(1800 + stable_score(f"{key}:latency", 0, 3600))
    token_total = int(round(base_tokens * factors["token_mult"]))
    token_in = int(round(token_total * stable_score(f"{key}:in_ratio", 0.54, 0.72)))
    token_out = max(1, token_total - token_in)
    latency_ms = int(round(base_latency * factors["latency_mult"]))
    cost_usd = round((token_total / 1_000_000.0) * 1.2 * factors["cost_mult"], 6)

    quality_raw = stable_score(f"{key}:quality", 0.45, 0.95) + factors["quality_bias"]
    quality_raw = max(0.0, min(1.0, quality_raw))
    checks_total = max(len(checks), len(task.get("acceptance_checks", [])), 1)
    checks_passed = int(round(quality_raw * checks_total))
    checks_passed = max(0, min(checks_total, checks_passed))
    acceptance_passed = checks_passed == checks_total
    retries = 0 if acceptance_passed else int(round(stable_score(f"{key}:retry", 0, 2)))
    rework_cycles = 0 if acceptance_passed else int(round(stable_score(f"{key}:rework", 1, 3)))

    return {
        "run_id": hashlib.sha256(f"{key}:run".encode("utf-8")).hexdigest()[:16],
        "suite_hash": suite_hash,
        "timestamp": now_iso(),
        "metadata": {
            "repo": repo,
            "task_id": task_id,
            "task_prompt": str(task.get("prompt", "")),
            "task_type": str(task.get("task_type", "unknown")),
            "arm": arm,
            "seed": int(seed),
        },
        "metrics": {
            "tokens_in": token_in,
            "tokens_out": token_out,
            "tokens_total": token_total,
            "latency_ms": latency_ms,
            "cost_usd_estimated": cost_usd,
        },
        "quality": {
            "acceptance_checks_total": checks_total,
            "acceptance_checks_passed": checks_passed,
            "acceptance_passed": acceptance_passed,
            "retries": retries,
            "rework_cycles": rework_cycles,
        },
    }


def run_suite(suite_path: Path, out_dir: Path, arm: str, repo: str | None, seed: int | None) -> dict[str, Any]:
    arm = arm.upper()
    if arm not in VALID_ARMS:
        raise ValueError("Arm must be one of A/B/C.")
    suite = parse_suite(suite_path)
    suite_bytes = json.dumps(suite, sort_keys=True).encode("utf-8")
    suite_hash = hashlib.sha256(suite_bytes).hexdigest()
    selection = select_suite_rows(suite, repo, seed)
    run_rows: list[dict[str, Any]] = []
    runs_dir = out_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    for repo_item in selection.repos:
        for task in selection.tasks:
            checks = [str(item) for item in task.get("acceptance_checks", selection.acceptance_checks)]
            for seed_item in selection.seeds:
                row = simulate_run(repo_item, task, seed_item, arm=arm, checks=checks, suite_hash=suite_hash)
                run_rows.append(row)
                write_json(runs_dir / f"{row['run_id']}.json", row)
    manifest = {
        "version": 1,
        "generated_at": now_iso(),
        "suite_path": suite_path.resolve().as_posix(),
        "suite_hash": suite_hash,
        "arm": arm,
        "selected_repo": repo,
        "selected_seed": seed,
        "runs_generated": len(run_rows),
        "runs_dir": runs_dir.resolve().as_posix(),
        "deterministic": True,
        "notes": "Synthetic benchmark scaffold for reproducible A/B/C comparisons.",
    }
    write_json(out_dir / f"run_manifest_{arm}.json", manifest)
    return manifest


def _group(values: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in values:
        grouped.setdefault(str(row["metadata"][key]), []).append(row)
    return grouped


def _arm_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "runs": 0,
            "tokens_total": {"mean": 0.0, "median": 0.0, "p95": 0.0, "variance": 0.0},
            "latency_ms": {"mean": 0.0, "median": 0.0, "p95": 0.0, "variance": 0.0},
            "cost_usd_estimated": {"mean": 0.0, "median": 0.0, "p95": 0.0, "variance": 0.0},
            "quality": {"pass_rate": 0.0, "avg_retries": 0.0, "avg_rework_cycles": 0.0},
        }
    tokens = [float(row["metrics"]["tokens_total"]) for row in rows]
    latency = [float(row["metrics"]["latency_ms"]) for row in rows]
    costs = [float(row["metrics"]["cost_usd_estimated"]) for row in rows]
    retries = [float(row["quality"]["retries"]) for row in rows]
    rework = [float(row["quality"]["rework_cycles"]) for row in rows]
    pass_rate = sum(1.0 for row in rows if row["quality"]["acceptance_passed"]) / len(rows)
    return {
        "runs": len(rows),
        "tokens_total": {
            "mean": round(sum(tokens) / len(tokens), 4),
            "median": round(float(median(tokens)), 4),
            "p95": round(percentile(tokens, 0.95), 4),
            "variance": round(variance(tokens), 4),
        },
        "latency_ms": {
            "mean": round(sum(latency) / len(latency), 4),
            "median": round(float(median(latency)), 4),
            "p95": round(percentile(latency, 0.95), 4),
            "variance": round(variance(latency), 4),
        },
        "cost_usd_estimated": {
            "mean": round(sum(costs) / len(costs), 8),
            "median": round(float(median(costs)), 8),
            "p95": round(percentile(costs, 0.95), 8),
            "variance": round(variance(costs), 8),
        },
        "quality": {
            "pass_rate": round(pass_rate, 4),
            "avg_retries": round(sum(retries) / len(retries), 4),
            "avg_rework_cycles": round(sum(rework) / len(rework), 4),
        },
    }


def _delta_ratio(lower_is_better_base: float, lower_is_better_candidate: float) -> float:
    if lower_is_better_base <= 0:
        return 0.0
    return round((lower_is_better_base - lower_is_better_candidate) / lower_is_better_base, 4)


def _infer_confidence(runs_by_arm: dict[str, list[dict[str, Any]]]) -> str:
    mins = min(len(rows) for rows in runs_by_arm.values()) if runs_by_arm else 0
    if mins >= 100:
        return "high"
    if mins >= 30:
        return "medium"
    if mins > 0:
        return "low"
    return "unknown"


def _compute_gating(rows: list[dict[str, Any]], complete_abc: bool) -> dict[str, Any]:
    repos = sorted({str(row["metadata"]["repo"]) for row in rows})
    grouped_by_repo = _group(rows, "repo")
    tasks_per_repo = {
        repo: len({str(item["metadata"]["task_id"]) for item in repo_rows}) for repo, repo_rows in grouped_by_repo.items()
    }
    seeds_per_repo_task: dict[str, int] = {}
    for row in rows:
        key = f"{row['metadata']['repo']}::{row['metadata']['task_id']}"
        seeds_per_repo_task.setdefault(key, 0)
    for key in list(seeds_per_repo_task.keys()):
        repo, task_id = key.split("::", 1)
        matched = [row for row in rows if str(row["metadata"]["repo"]) == repo and str(row["metadata"]["task_id"]) == task_id]
        seeds_per_repo_task[key] = len({int(item["metadata"]["seed"]) for item in matched})
    min_tasks_by_repo = min(tasks_per_repo.values()) if tasks_per_repo else 0
    min_seeds_by_repo_task = min(seeds_per_repo_task.values()) if seeds_per_repo_task else 0
    gates = {
        "min_repos": {"required": 3, "actual": len(repos), "met": len(repos) >= 3},
        "min_tasks_per_repo": {"required": 12, "actual": min_tasks_by_repo, "met": min_tasks_by_repo >= 12},
        "min_seeds_per_task": {"required": 3, "actual": min_seeds_by_repo_task, "met": min_seeds_by_repo_task >= 3},
        "complete_abc": {"required": True, "actual": complete_abc, "met": complete_abc},
    }
    all_met = all(item["met"] for item in gates.values())
    return {
        "gates": gates,
        "all_met": all_met,
        "claim_label": "material_repeatable" if all_met else "exploratory",
        "repos": repos,
        "tasks_per_repo": tasks_per_repo,
        "min_seeds_per_repo_task": min_seeds_by_repo_task,
    }


def load_runs(input_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted((input_dir / "runs").glob("*.json")):
        payload = read_json(path, {})
        if not isinstance(payload, dict):
            continue
        if not isinstance(payload.get("metadata"), dict) or str(payload["metadata"].get("arm", "")).upper() not in VALID_ARMS:
            continue
        payload["metadata"]["arm"] = str(payload["metadata"]["arm"]).upper()
        rows.append(payload)
    return rows


def _format_markdown(report: dict[str, Any]) -> str:
    agg = report["aggregation"]
    gating = report["publication_gating"]
    lines = [
        "# AICTX Benchmark Report",
        "",
        f"- Generated (UTC): `{report['generated_at']}`",
        f"- Input dir: `{report['input_dir']}`",
        f"- Suite hashes: `{', '.join(report['suite_hashes'])}`",
        f"- Confidence: `{report['confidence']}`",
        f"- Claim label: `{gating['claim_label']}`",
        "",
        "## Methodology",
        "- Arms: A (baseline), B (baseline+discipline/search), C (aictx full)",
        f"- Runs total: {report['runs_total']}",
        "",
        "## Results",
        "| Arm | Runs | Token mean | Latency mean (ms) | Cost mean (USD) | Pass rate |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for arm in ["A", "B", "C"]:
        row = agg["by_arm"].get(arm, {})
        lines.append(
            f"| {arm} | {row.get('runs', 0)} | {row.get('tokens_total', {}).get('mean', 0)} | "
            f"{row.get('latency_ms', {}).get('mean', 0)} | {row.get('cost_usd_estimated', {}).get('mean', 0)} | "
            f"{row.get('quality', {}).get('pass_rate', 0)} |"
        )
    deltas = agg.get("deltas", {})
    lines.extend(
        [
            "",
            "## Deltas (C vs baseline)",
            f"- Tokens (C vs A): {deltas.get('C_vs_A', {}).get('tokens_total_reduction_ratio', 0)}",
            f"- Tokens (C vs B): {deltas.get('C_vs_B', {}).get('tokens_total_reduction_ratio', 0)}",
            f"- Latency (C vs A): {deltas.get('C_vs_A', {}).get('latency_reduction_ratio', 0)}",
            f"- Cost (C vs A): {deltas.get('C_vs_A', {}).get('cost_reduction_ratio', 0)}",
            f"- Pass rate lift (C vs A): {deltas.get('C_vs_A', {}).get('pass_rate_lift', 0)}",
            "",
            "## Publication gating",
            f"- Repos >= 3: {gating['gates']['min_repos']['met']} ({gating['gates']['min_repos']['actual']})",
            f"- Tasks/repo >= 12: {gating['gates']['min_tasks_per_repo']['met']} ({gating['gates']['min_tasks_per_repo']['actual']})",
            f"- Seeds/task >= 3: {gating['gates']['min_seeds_per_task']['met']} ({gating['gates']['min_seeds_per_task']['actual']})",
            f"- A/B/C complete: {gating['gates']['complete_abc']['met']}",
            "",
            "## Limits",
            "- This scaffold report is deterministic and benchmark-structured; validate against real executions before external claims.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_benchmark_status(rows: list[dict[str, Any]], report: dict[str, Any]) -> None:
    by_repo = _group(rows, "repo")
    for repo, repo_rows in by_repo.items():
        repo_path = Path(repo)
        metrics_dir = repo_path / ".ai_context_engine" / "metrics"
        if not metrics_dir.exists():
            continue
        arms = sorted({str(item["metadata"]["arm"]).upper() for item in repo_rows})
        status = {
            "version": 1,
            "generated_at": now_iso(),
            "benchmark_present": bool(repo_rows),
            "arms_covered": arms,
            "complete_abc": set(VALID_ARMS).issubset(set(arms)),
            "runs_total": len(repo_rows),
            "claim_label": report["publication_gating"]["claim_label"],
            "report_confidence": report["confidence"],
            "report_path": str((Path(report["output_dir"]) / "benchmark_report.json").resolve()),
        }
        write_json(metrics_dir / "benchmark_status.json", status)


def build_report(input_dir: Path) -> tuple[dict[str, Any], int]:
    rows = load_runs(input_dir)
    runs_by_arm = {arm: [row for row in rows if row["metadata"]["arm"] == arm] for arm in sorted(VALID_ARMS)}
    complete_abc = all(len(items) > 0 for items in runs_by_arm.values())
    by_arm = {arm: _arm_stats(runs_by_arm.get(arm, [])) for arm in sorted(VALID_ARMS)}
    deltas = {
        "C_vs_A": {
            "tokens_total_reduction_ratio": _delta_ratio(by_arm["A"]["tokens_total"]["mean"], by_arm["C"]["tokens_total"]["mean"]),
            "latency_reduction_ratio": _delta_ratio(by_arm["A"]["latency_ms"]["mean"], by_arm["C"]["latency_ms"]["mean"]),
            "cost_reduction_ratio": _delta_ratio(by_arm["A"]["cost_usd_estimated"]["mean"], by_arm["C"]["cost_usd_estimated"]["mean"]),
            "pass_rate_lift": round(by_arm["C"]["quality"]["pass_rate"] - by_arm["A"]["quality"]["pass_rate"], 4),
        },
        "C_vs_B": {
            "tokens_total_reduction_ratio": _delta_ratio(by_arm["B"]["tokens_total"]["mean"], by_arm["C"]["tokens_total"]["mean"]),
            "latency_reduction_ratio": _delta_ratio(by_arm["B"]["latency_ms"]["mean"], by_arm["C"]["latency_ms"]["mean"]),
            "cost_reduction_ratio": _delta_ratio(by_arm["B"]["cost_usd_estimated"]["mean"], by_arm["C"]["cost_usd_estimated"]["mean"]),
            "pass_rate_lift": round(by_arm["C"]["quality"]["pass_rate"] - by_arm["B"]["quality"]["pass_rate"], 4),
        },
    }
    gating = _compute_gating(rows, complete_abc=complete_abc)
    report = {
        "version": 1,
        "generated_at": now_iso(),
        "input_dir": str(input_dir.resolve()),
        "output_dir": str(input_dir.resolve()),
        "runs_total": len(rows),
        "suite_hashes": sorted({str(row.get("suite_hash", "")) for row in rows if str(row.get("suite_hash", "")).strip()}),
        "arms_covered": [arm for arm in sorted(VALID_ARMS) if len(runs_by_arm[arm]) > 0],
        "complete_abc": complete_abc,
        "confidence": _infer_confidence(runs_by_arm),
        "aggregation": {"by_arm": by_arm, "deltas": deltas},
        "publication_gating": gating,
        "missing_requirements": [] if complete_abc else ["missing_runs_for_one_or_more_arms"],
    }
    if not complete_abc:
        report["missing_requirements"].append("required_arms_A_B_C")
    return report, (0 if complete_abc else 1)


def cli_benchmark_run(args: Any) -> int:
    try:
        manifest = run_suite(
            suite_path=Path(args.suite).expanduser().resolve(),
            out_dir=Path(args.out).expanduser().resolve(),
            arm=str(args.arm).upper(),
            repo=args.repo,
            seed=int(args.seed) if args.seed is not None else None,
        )
    except Exception as exc:  # pragma: no cover - defensive CLI
        print(json.dumps({"error": str(exc)}, indent=2, ensure_ascii=False))
        return 1
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


def cli_benchmark_report(args: Any) -> int:
    input_dir = Path(args.input).expanduser().resolve()
    report, exit_code = build_report(input_dir)
    write_json(input_dir / "benchmark_report.json", report)
    markdown = _format_markdown(report)
    (input_dir / "benchmark_report.md").write_text(markdown, encoding="utf-8")
    write_benchmark_status(load_runs(input_dir), report)

    if args.format == "md":
        print(markdown)
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    return exit_code
