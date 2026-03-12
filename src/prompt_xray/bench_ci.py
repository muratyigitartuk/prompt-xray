from __future__ import annotations

import argparse
from pathlib import Path

from .bench import diff_benchmark_runs, load_benchmark_config, load_benchmark_run


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a benchmark run against a saved baseline.")
    parser.add_argument("--baseline", required=True, help="Path to the saved benchmark.json baseline.")
    parser.add_argument("--candidate", required=True, help="Path to the candidate benchmark.json file.")
    args = parser.parse_args()

    config = load_benchmark_config()
    baseline = load_benchmark_run(Path(args.baseline))
    candidate = load_benchmark_run(Path(args.candidate))
    diff = diff_benchmark_runs(baseline, candidate, Path(args.baseline), Path(args.candidate))
    thresholds = config.regression_thresholds

    failures: list[str] = []
    if diff.summary["family_delta"] < thresholds["family_exact_match_delta_min"]:
        failures.append(f"family exact-match delta {diff.summary['family_delta']} is below threshold")
    if diff.summary["archetype_delta"] < thresholds["archetype_exact_match_delta_min"]:
        failures.append(f"archetype exact-match delta {diff.summary['archetype_delta']} is below threshold")
    if diff.summary["orchestration_delta"] < thresholds["orchestration_exact_match_delta_min"]:
        failures.append(
            f"orchestration exact-match delta {diff.summary['orchestration_delta']} is below threshold"
        )
    if diff.summary["memory_delta"] < thresholds["memory_exact_match_delta_min"]:
        failures.append(f"memory exact-match delta {diff.summary['memory_delta']} is below threshold")
    if diff.summary["low_confidence_delta"] > thresholds["low_confidence_delta_max"]:
        failures.append(f"low-confidence delta {diff.summary['low_confidence_delta']} exceeds threshold")

    if not candidate.baseline_name.startswith("reduced-"):
        for split, floors in config.minimum_split_floors.items():
            metrics = candidate.split_metrics.get(split)
            if not metrics:
                continue
            if metrics.family_exact_matches < floors.get("family_exact_matches_min", 0):
                failures.append(f"{split} family exact matches {metrics.family_exact_matches} fell below floor")
            if metrics.archetype_exact_matches < floors.get("archetype_exact_matches_min", 0):
                failures.append(f"{split} archetype exact matches {metrics.archetype_exact_matches} fell below floor")
            if metrics.orchestration_exact_matches < floors.get("orchestration_exact_matches_min", 0):
                failures.append(f"{split} orchestration exact matches {metrics.orchestration_exact_matches} fell below floor")
            if metrics.memory_exact_matches < floors.get("memory_exact_matches_min", 0):
                failures.append(f"{split} memory exact matches {metrics.memory_exact_matches} fell below floor")
            if metrics.low_confidence_cases > floors.get("low_confidence_cases_max", 999999):
                failures.append(f"{split} low-confidence cases {metrics.low_confidence_cases} exceeded floor")

    for split, split_thresholds in config.split_regression_thresholds.items():
        split_delta = diff.summary.get("split_deltas", {}).get(split, {})
        if not split_delta:
            continue
        if split_delta.get("family_delta", 0) < split_thresholds.get("family_exact_match_delta_min", -999999):
            failures.append(f"{split} family exact-match delta {split_delta.get('family_delta', 0)} is below threshold")
        if split_delta.get("archetype_delta", 0) < split_thresholds.get("archetype_exact_match_delta_min", -999999):
            failures.append(f"{split} archetype exact-match delta {split_delta.get('archetype_delta', 0)} is below threshold")
        if split_delta.get("orchestration_delta", 0) < split_thresholds.get("orchestration_exact_match_delta_min", -999999):
            failures.append(f"{split} orchestration exact-match delta {split_delta.get('orchestration_delta', 0)} is below threshold")
        if split_delta.get("memory_delta", 0) < split_thresholds.get("memory_exact_match_delta_min", -999999):
            failures.append(f"{split} memory exact-match delta {split_delta.get('memory_delta', 0)} is below threshold")
        if split_delta.get("low_confidence_delta", 0) > split_thresholds.get("low_confidence_delta_max", 999999):
            failures.append(f"{split} low-confidence delta {split_delta.get('low_confidence_delta', 0)} exceeds threshold")

    if failures:
        for failure in failures:
            print(f"benchmark validation failed: {failure}")
        print(f"changed cases: {len(diff.changed_cases)}")
        for item in diff.changed_cases[:10]:
            before = item.get("before", {})
            after = item.get("after", {})
            if item.get("after_error"):
                print(f"- {item['id']}: error -> {item['after_error']}")
                continue
            print(
                f"- {item['id']}: "
                f"{before.get('repo_family', '?')}/{before.get('repo_archetype', '?')}/"
                f"{before.get('orchestration_model', '?')}/{before.get('memory_model', '?')} -> "
                f"{after.get('repo_family', '?')}/{after.get('repo_archetype', '?')}/"
                f"{after.get('orchestration_model', '?')}/{after.get('memory_model', '?')}"
            )
        return 1

    print("benchmark validation passed")
    print(
        "deltas:",
        f"family={diff.summary['family_delta']}",
        f"archetype={diff.summary['archetype_delta']}",
        f"orchestration={diff.summary['orchestration_delta']}",
        f"memory={diff.summary['memory_delta']}",
        f"low-confidence={diff.summary['low_confidence_delta']}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
