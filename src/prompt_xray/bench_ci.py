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

    if failures:
        for failure in failures:
            print(f"benchmark validation failed: {failure}")
        print(f"changed cases: {len(diff.changed_cases)}")
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
