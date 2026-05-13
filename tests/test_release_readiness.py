from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _make_target_line(name: str) -> str:
    for line in _read("Makefile").splitlines():
        if line.startswith(f"{name}:"):
            return line
    raise AssertionError(f"missing make target: {name}")


def _make_recipe(name: str) -> str:
    lines = _read("Makefile").splitlines()
    recipe: list[str] = []
    capture = False
    for line in lines:
        if line.startswith(f"{name}:"):
            capture = True
            continue
        if not capture:
            continue
        if line and not line.startswith("\t"):
            break
        if line.startswith("\t"):
            recipe.append(line.strip())
    return "\n".join(recipe)


def test_local_smoke_prepare_uses_canonical_task_flag():
    recipe = _make_recipe("smoke")
    assert '--task "review middleware behavior"' in recipe
    assert "--request" not in recipe


def test_ci_workflow_delegates_release_readiness_to_make_ci():
    workflow = _read(".github/workflows/ci.yml")
    ci_target = _make_target_line("ci")
    wheel_recipe = _make_recipe("wheel-install-check")

    assert "smoke" in ci_target.split(":", 1)[1].split()
    assert "wheel-install-check" in ci_target.split(":", 1)[1].split()
    assert "tomllib" in wheel_recipe
    assert 'dist/aictx-" + tomllib.loads' in wheel_recipe
    assert "--version" in wheel_recipe
    assert "run: make ci PYTHON=python" in workflow
    assert "name: Smoke flow" not in workflow
    assert "aictx internal execution prepare" not in workflow
