from __future__ import annotations

import json
from pathlib import Path

from prompt_xray.bench import BenchmarkConfig, BenchmarkMetrics, BenchmarkRun
from prompt_xray import bench_ci


def _write_run(path: Path, split: str, metrics: BenchmarkMetrics, baseline_name: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    run = BenchmarkRun(
        generated_at="2026-03-12T00:00:00+00:00",
        config_path="benchmarks/cases",
        case_count=metrics.total_cases,
        baseline_name=baseline_name,
        split=split,
        results=[],
        metrics=metrics,
        split_metrics={split: metrics},
        failure_clusters={},
    )
    path.write_text(json.dumps(run.model_dump(mode="json"), indent=2), encoding="utf-8")


def test_bench_ci_uses_split_thresholds_for_calibration_runs(monkeypatch, tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    candidate_path = tmp_path / "candidate.json"
    baseline_metrics = BenchmarkMetrics(
        total_cases=10,
        family_exact_matches=10,
        archetype_exact_matches=10,
        orchestration_exact_matches=10,
        memory_exact_matches=10,
        low_confidence_cases=0,
    )
    candidate_metrics = BenchmarkMetrics(
        total_cases=10,
        family_exact_matches=9,
        archetype_exact_matches=8,
        orchestration_exact_matches=9,
        memory_exact_matches=9,
        low_confidence_cases=0,
    )
    _write_run(baseline_path, "calibration", baseline_metrics, baseline_name="calibration")
    _write_run(candidate_path, "calibration", candidate_metrics, baseline_name="calibration")

    monkeypatch.setattr(
        bench_ci,
        "load_benchmark_config",
        lambda: BenchmarkConfig(
            regression_thresholds={
                "family_exact_match_delta_min": 0,
                "archetype_exact_match_delta_min": 0,
                "orchestration_exact_match_delta_min": 0,
                "memory_exact_match_delta_min": 0,
                "low_confidence_delta_max": 0,
            },
            minimum_split_floors={
                "calibration": {
                    "family_exact_matches_min": 8,
                    "archetype_exact_matches_min": 8,
                    "orchestration_exact_matches_min": 8,
                    "memory_exact_matches_min": 8,
                    "low_confidence_cases_max": 1,
                }
            },
            split_regression_thresholds={
                "calibration": {
                    "family_exact_match_delta_min": -2,
                    "archetype_exact_match_delta_min": -2,
                    "orchestration_exact_match_delta_min": -1,
                    "memory_exact_match_delta_min": -1,
                    "low_confidence_delta_max": 1,
                }
            },
        ),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "bench_ci",
            "--baseline",
            str(baseline_path),
            "--candidate",
            str(candidate_path),
        ],
    )

    assert bench_ci.main() == 0


def test_bench_ci_keeps_global_thresholds_for_full_runs(monkeypatch, tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline-full.json"
    candidate_path = tmp_path / "candidate-full.json"
    baseline_metrics = BenchmarkMetrics(
        total_cases=10,
        family_exact_matches=10,
        archetype_exact_matches=10,
        orchestration_exact_matches=10,
        memory_exact_matches=10,
        low_confidence_cases=0,
    )
    candidate_metrics = BenchmarkMetrics(
        total_cases=10,
        family_exact_matches=9,
        archetype_exact_matches=10,
        orchestration_exact_matches=10,
        memory_exact_matches=10,
        low_confidence_cases=0,
    )
    _write_run(baseline_path, "all", baseline_metrics, baseline_name="full")
    _write_run(candidate_path, "all", candidate_metrics, baseline_name="full")

    monkeypatch.setattr(
        bench_ci,
        "load_benchmark_config",
        lambda: BenchmarkConfig(
            regression_thresholds={
                "family_exact_match_delta_min": 0,
                "archetype_exact_match_delta_min": 0,
                "orchestration_exact_match_delta_min": 0,
                "memory_exact_match_delta_min": 0,
                "low_confidence_delta_max": 0,
            }
        ),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "bench_ci",
            "--baseline",
            str(baseline_path),
            "--candidate",
            str(candidate_path),
        ],
    )

    assert bench_ci.main() == 1
