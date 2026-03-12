from __future__ import annotations

import json
from pathlib import Path

from prompt_xray.bench import (
    diff_benchmark_runs,
    load_benchmark_config,
    load_benchmark_run,
    load_cases,
    render_benchmark_markdown,
    run_benchmark,
    select_cases,
    write_benchmark_diff,
    write_benchmark_run,
)
from prompt_xray.models import (
    ConfidenceScore,
    Counts,
    RealVsPackaging,
    RepoInfo,
    ScanLimits,
    ScanReport,
    Summary,
)


def _write_case(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _fake_report(name: str, family: str, archetype: str, orchestration: str, memory: str) -> ScanReport:
    return ScanReport(
        repo=RepoInfo(name=name, target=name, source_type="github", commit="abc123"),
        summary=Summary(
            repo_family=family,
            repo_archetype=archetype,
            orchestration_model=orchestration,
            memory_model=memory,
            xray_call="Synthetic result.",
            verdict="Synthetic benchmark report.",
        ),
        counts=Counts(candidate_files=3, artifacts=1),
        real_vs_packaging=RealVsPackaging(),
        repo_family_confidence=ConfidenceScore(score=0.82, level="high", reasons=["synthetic"]),
        repo_archetype_confidence=ConfidenceScore(score=0.78, level="medium", reasons=["synthetic"]),
        orchestration_confidence=ConfidenceScore(score=0.74, level="medium", reasons=["synthetic"]),
        memory_confidence=ConfidenceScore(score=0.61, level="medium", reasons=["synthetic"]),
        overall_confidence=ConfidenceScore(score=0.74, level="medium", reasons=["synthetic"]),
        scan_limits=ScanLimits(max_file_size_kb=1024, max_code_files_per_language=400),
    )


def test_load_cases_reads_metadata_files(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    _write_case(
        cases_dir / "one.json",
        {
            "id": "one",
            "repo_url": "https://github.com/example/one.git",
            "commit": "deadbeef",
            "repo_family": "prompt-pack",
            "repo_archetype": "prompt-library",
            "orchestration_model": "prompt-defined",
            "memory_model": "documented-only",
            "confidence_expectation": "high",
            "rationale": "fixture",
            "split": "calibration",
            "tags": ["fixture"],
            "ambiguity_policy": "strict",
            "allowed_labels": {},
        },
    )

    cases = load_cases(cases_dir)

    assert len(cases) == 1
    assert cases[0].id == "one"


def test_benchmark_run_and_diff_are_stable(monkeypatch, tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    _write_case(
        cases_dir / "one.json",
        {
            "id": "one",
            "repo_url": "https://github.com/example/one.git",
            "commit": "deadbeef",
            "repo_family": "prompt-pack",
            "repo_archetype": "prompt-library",
            "orchestration_model": "prompt-defined",
            "memory_model": "documented-only",
            "confidence_expectation": "high",
            "rationale": "fixture",
            "split": "calibration",
            "tags": ["fixture"],
            "ambiguity_policy": "strict",
            "allowed_labels": {},
        },
    )
    cases = load_cases(cases_dir)

    def fake_analyze_target(*args, **kwargs):
        return _fake_report("one", "prompt-pack", "prompt-library", "prompt-defined", "documented-only")

    monkeypatch.setattr("prompt_xray.bench.analyze_target", fake_analyze_target)
    run = run_benchmark(cases)
    written = write_benchmark_run(run, tmp_path / "out")
    reloaded = load_benchmark_run(written[0])
    markdown = render_benchmark_markdown(reloaded)

    assert run.metrics.total_cases == 1
    assert run.split_metrics["calibration"].total_cases == 1
    assert run.metrics.family_exact_matches == 1
    assert "Prompt-xray Benchmark Run" in markdown

    changed = run.model_copy(deep=True)
    changed.results[0].actual["repo_archetype"] = "mixed"
    changed.metrics.archetype_exact_matches = 0
    diff = diff_benchmark_runs(run, changed, written[0], written[0])
    diff_written = write_benchmark_diff(diff, tmp_path / "diff")

    assert diff.changed_cases
    assert diff.summary["archetype_delta"] == -1
    assert all(path.exists() for path in diff_written)


def test_benchmark_config_and_subset_selection(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "confidence_thresholds": {"high": 0.8, "medium": 0.55},
                "default_max_file_size_kb": 256,
                "default_max_code_files_per_language": 123,
                "reduced_case_ids": ["one"],
                "regression_thresholds": {
                    "family_exact_match_delta_min": 0,
                    "archetype_exact_match_delta_min": 0,
                    "orchestration_exact_match_delta_min": 0,
                "memory_exact_match_delta_min": 0,
                "low_confidence_delta_max": 1,
                },
                "reduced_case_ids_by_split": {"holdout": ["two"]},
                "minimum_split_floors": {"holdout": {"family_exact_matches_min": 0}},
                "split_regression_thresholds": {"holdout": {"family_exact_match_delta_min": 0}},
            }
        ),
        encoding="utf-8",
    )
    config = load_benchmark_config(config_path)
    cases = [
        type("Case", (), {"id": "one"})(),
        type("Case", (), {"id": "two"})(),
    ]

    selected = select_cases(cases, config.reduced_case_ids)

    assert config.default_max_code_files_per_language == 123
    assert len(selected) == 1
    assert selected[0].id == "one"
    assert config.reduced_case_ids_by_split["holdout"] == ["two"]


def test_benchmark_run_records_case_errors(monkeypatch, tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    _write_case(
        cases_dir / "one.json",
        {
            "id": "one",
            "repo_url": "https://github.com/example/one.git",
            "commit": "deadbeef",
            "repo_family": "prompt-pack",
            "repo_archetype": "prompt-library",
            "orchestration_model": "prompt-defined",
            "memory_model": "documented-only",
            "confidence_expectation": "high",
            "rationale": "fixture",
            "split": "calibration",
            "tags": ["fixture"],
            "ambiguity_policy": "strict",
            "allowed_labels": {},
        },
    )
    cases = load_cases(cases_dir)

    def boom(*args, **kwargs):
        raise RuntimeError("cannot clone")

    monkeypatch.setattr("prompt_xray.bench.analyze_target", boom)
    run = run_benchmark(cases)

    assert run.metrics.total_cases == 1
    assert run.metrics.major_regressions == ["one"]
    assert run.results[0].error == "RuntimeError: cannot clone"
