from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from .analysis import analyze_target


class BenchmarkCase(BaseModel):
    id: str
    repo_url: str
    commit: str
    repo_family: str
    repo_archetype: str
    orchestration_model: str
    memory_model: str
    confidence_expectation: str
    rationale: str
    calibration_note: str = ""
    tags: list[str] = Field(default_factory=list)


class BenchmarkCaseResult(BaseModel):
    id: str
    repo_url: str
    commit: str
    expected: dict
    actual: dict
    confidence: dict
    mismatches: list[str] = Field(default_factory=list)
    error: str = ""


class BenchmarkMetrics(BaseModel):
    total_cases: int
    archetype_exact_matches: int
    orchestration_exact_matches: int
    memory_exact_matches: int
    family_exact_matches: int
    low_confidence_cases: int
    major_regressions: list[str] = Field(default_factory=list)
    family_confusions: dict[str, int] = Field(default_factory=dict)
    archetype_confusions: dict[str, int] = Field(default_factory=dict)
    orchestration_confusions: dict[str, int] = Field(default_factory=dict)
    memory_confusions: dict[str, int] = Field(default_factory=dict)


class BenchmarkRun(BaseModel):
    generated_at: str
    config_path: str
    case_count: int
    baseline_name: str = ""
    results: list[BenchmarkCaseResult]
    metrics: BenchmarkMetrics


class BenchmarkDiff(BaseModel):
    left_path: str
    right_path: str
    summary: dict
    changed_cases: list[dict]


class BenchmarkConfig(BaseModel):
    confidence_thresholds: dict[str, float] = Field(default_factory=lambda: {"high": 0.8, "medium": 0.55})
    default_max_file_size_kb: int = 1024
    default_max_code_files_per_language: int = 400
    reduced_case_ids: list[str] = Field(default_factory=list)
    regression_thresholds: dict[str, int] = Field(
        default_factory=lambda: {
            "family_exact_match_delta_min": 0,
            "archetype_exact_match_delta_min": 0,
            "orchestration_exact_match_delta_min": 0,
            "memory_exact_match_delta_min": 0,
            "low_confidence_delta_max": 0,
        }
    )


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_benchmark_config(config_path: Path | None = None) -> BenchmarkConfig:
    path = config_path or (_project_root() / "benchmarks" / "config.json")
    return BenchmarkConfig.model_validate_json(path.read_text(encoding="utf-8"))


def load_cases(cases_dir: Path | None = None) -> list[BenchmarkCase]:
    root = cases_dir or (_project_root() / "benchmarks" / "cases")
    cases = []
    for path in sorted(root.glob("*.json")):
        cases.append(BenchmarkCase.model_validate_json(path.read_text(encoding="utf-8")))
    return cases


def _confidence_level(score: dict) -> str:
    return score.get("level", "low")


def _confusion_key(expected: str, actual: str) -> str:
    return f"{expected} -> {actual}"


def _evaluate_case(case: BenchmarkCase, max_file_size_kb: int, max_code_files_per_language: int) -> BenchmarkCaseResult:
    expected = case.model_dump(include={"repo_family", "repo_archetype", "orchestration_model", "memory_model"})
    try:
        report = analyze_target(
            case.repo_url,
            max_file_size_kb=max_file_size_kb,
            max_code_files_per_language=max_code_files_per_language,
            include_snippets=False,
            git_ref=case.commit,
        )
        actual = {
            "repo_family": report.summary.repo_family,
            "repo_archetype": report.summary.repo_archetype,
            "orchestration_model": report.summary.orchestration_model,
            "memory_model": report.summary.memory_model,
            "xray_call": report.summary.xray_call,
        }
        mismatches = [key for key, value in expected.items() if actual.get(key) != value]
        return BenchmarkCaseResult(
            id=case.id,
            repo_url=case.repo_url,
            commit=case.commit,
            expected=expected,
            actual=actual,
            confidence={
                "repo_family": report.repo_family_confidence.model_dump(mode="json"),
                "repo_archetype": report.repo_archetype_confidence.model_dump(mode="json"),
                "orchestration": report.orchestration_confidence.model_dump(mode="json"),
                "memory": report.memory_confidence.model_dump(mode="json"),
                "overall": report.overall_confidence.model_dump(mode="json"),
            },
            mismatches=mismatches,
        )
    except Exception as exc:
        return BenchmarkCaseResult(
            id=case.id,
            repo_url=case.repo_url,
            commit=case.commit,
            expected=expected,
            actual={},
            confidence={"overall": {"score": 0.0, "level": "low", "reasons": ["benchmark-case-error"]}},
            mismatches=sorted(expected.keys()),
            error=f"{type(exc).__name__}: {exc}",
        )


def _metrics(results: list[BenchmarkCaseResult]) -> BenchmarkMetrics:
    family_confusions: Counter[str] = Counter()
    archetype_confusions: Counter[str] = Counter()
    orchestration_confusions: Counter[str] = Counter()
    memory_confusions: Counter[str] = Counter()
    major_regressions: list[str] = []

    family_matches = 0
    archetype_matches = 0
    orchestration_matches = 0
    memory_matches = 0
    low_confidence = 0

    for result in results:
        actual_family = result.actual.get("repo_family", "error")
        actual_archetype = result.actual.get("repo_archetype", "error")
        actual_orchestration = result.actual.get("orchestration_model", "error")
        actual_memory = result.actual.get("memory_model", "error")

        if result.expected["repo_family"] == actual_family:
            family_matches += 1
        else:
            family_confusions[_confusion_key(result.expected["repo_family"], actual_family)] += 1
        if result.expected["repo_archetype"] == actual_archetype:
            archetype_matches += 1
        else:
            archetype_confusions[_confusion_key(result.expected["repo_archetype"], actual_archetype)] += 1
        if result.expected["orchestration_model"] == actual_orchestration:
            orchestration_matches += 1
        else:
            orchestration_confusions[_confusion_key(result.expected["orchestration_model"], actual_orchestration)] += 1
        if result.expected["memory_model"] == actual_memory:
            memory_matches += 1
        else:
            memory_confusions[_confusion_key(result.expected["memory_model"], actual_memory)] += 1

        if _confidence_level(result.confidence["overall"]) == "low":
            low_confidence += 1
        if len(result.mismatches) >= 2:
            major_regressions.append(result.id)
        if result.error:
            if result.id not in major_regressions:
                major_regressions.append(result.id)

    return BenchmarkMetrics(
        total_cases=len(results),
        archetype_exact_matches=archetype_matches,
        orchestration_exact_matches=orchestration_matches,
        memory_exact_matches=memory_matches,
        family_exact_matches=family_matches,
        low_confidence_cases=low_confidence,
        major_regressions=major_regressions,
        family_confusions=dict(family_confusions),
        archetype_confusions=dict(archetype_confusions),
        orchestration_confusions=dict(orchestration_confusions),
        memory_confusions=dict(memory_confusions),
    )


def run_benchmark(
    cases: list[BenchmarkCase],
    max_file_size_kb: int = 1024,
    max_code_files_per_language: int = 400,
    baseline_name: str = "",
) -> BenchmarkRun:
    results = [
        _evaluate_case(case, max_file_size_kb=max_file_size_kb, max_code_files_per_language=max_code_files_per_language)
        for case in cases
    ]
    return BenchmarkRun(
        generated_at=datetime.now(timezone.utc).isoformat(),
        config_path="benchmarks/cases",
        case_count=len(cases),
        baseline_name=baseline_name,
        results=results,
        metrics=_metrics(results),
    )


def render_benchmark_markdown(run: BenchmarkRun) -> str:
    return f"""# Prompt-xray Benchmark Run

- Generated at: {run.generated_at}
- Cases: {run.case_count}
- Baseline name: {run.baseline_name or 'ad hoc'}
- Family exact matches: {run.metrics.family_exact_matches}/{run.metrics.total_cases}
- Archetype exact matches: {run.metrics.archetype_exact_matches}/{run.metrics.total_cases}
- Orchestration exact matches: {run.metrics.orchestration_exact_matches}/{run.metrics.total_cases}
- Memory exact matches: {run.metrics.memory_exact_matches}/{run.metrics.total_cases}
- Low-confidence cases: {run.metrics.low_confidence_cases}

## Major regressions

{chr(10).join(f"- `{item}`" for item in run.metrics.major_regressions) or "- None"}

## Case errors

{chr(10).join(f"- `{item.id}`: {item.error}" for item in run.results if item.error) or "- None"}

## Family confusions

{chr(10).join(f"- `{key}`: {value}" for key, value in sorted(run.metrics.family_confusions.items())) or "- None"}

## Archetype confusions

{chr(10).join(f"- `{key}`: {value}" for key, value in sorted(run.metrics.archetype_confusions.items())) or "- None"}

## Orchestration confusions

{chr(10).join(f"- `{key}`: {value}" for key, value in sorted(run.metrics.orchestration_confusions.items())) or "- None"}

## Memory confusions

{chr(10).join(f"- `{key}`: {value}" for key, value in sorted(run.metrics.memory_confusions.items())) or "- None"}
"""


def write_benchmark_run(run: BenchmarkRun, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "benchmark.json"
    md_path = out_dir / "benchmark.md"
    json_path.write_text(json.dumps(run.model_dump(mode="json"), indent=2), encoding="utf-8")
    md_path.write_text(render_benchmark_markdown(run), encoding="utf-8")
    return [json_path, md_path]


def load_benchmark_run(path: Path) -> BenchmarkRun:
    return BenchmarkRun.model_validate_json(path.read_text(encoding="utf-8"))


def diff_benchmark_runs(left: BenchmarkRun, right: BenchmarkRun, left_path: Path, right_path: Path) -> BenchmarkDiff:
    left_by_id = {result.id: result for result in left.results}
    right_by_id = {result.id: result for result in right.results}
    changed_cases = []
    for case_id in sorted(set(left_by_id).intersection(right_by_id)):
        before = left_by_id[case_id]
        after = right_by_id[case_id]
        if before.actual != after.actual or before.confidence != after.confidence:
            changed_cases.append(
                {
                    "id": case_id,
                    "before": before.actual,
                    "after": after.actual,
                    "before_confidence": before.confidence["overall"],
                    "after_confidence": after.confidence["overall"],
                    "before_error": before.error,
                    "after_error": after.error,
                }
            )
    summary = {
        "family_delta": right.metrics.family_exact_matches - left.metrics.family_exact_matches,
        "archetype_delta": right.metrics.archetype_exact_matches - left.metrics.archetype_exact_matches,
        "orchestration_delta": right.metrics.orchestration_exact_matches - left.metrics.orchestration_exact_matches,
        "memory_delta": right.metrics.memory_exact_matches - left.metrics.memory_exact_matches,
        "low_confidence_delta": right.metrics.low_confidence_cases - left.metrics.low_confidence_cases,
    }
    return BenchmarkDiff(
        left_path=str(left_path),
        right_path=str(right_path),
        summary=summary,
        changed_cases=changed_cases,
    )


def render_benchmark_diff_markdown(diff: BenchmarkDiff) -> str:
    return f"""# Prompt-xray Benchmark Diff

- Left: `{diff.left_path}`
- Right: `{diff.right_path}`
- Family delta: {diff.summary['family_delta']}
- Archetype delta: {diff.summary['archetype_delta']}
- Orchestration delta: {diff.summary['orchestration_delta']}
- Memory delta: {diff.summary['memory_delta']}
- Low-confidence delta: {diff.summary['low_confidence_delta']}

## Changed cases

{chr(10).join(f"- `{item['id']}`" for item in diff.changed_cases) or "- None"}
"""


def write_benchmark_diff(diff: BenchmarkDiff, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "benchmark-diff.json"
    md_path = out_dir / "benchmark-diff.md"
    json_path.write_text(json.dumps(diff.model_dump(mode="json"), indent=2), encoding="utf-8")
    md_path.write_text(render_benchmark_diff_markdown(diff), encoding="utf-8")
    return [json_path, md_path]


def select_cases(cases: list[BenchmarkCase], case_ids: list[str]) -> list[BenchmarkCase]:
    if not case_ids:
        return cases
    selected = {case_id.strip() for case_id in case_ids if case_id.strip()}
    return [case for case in cases if case.id in selected]
