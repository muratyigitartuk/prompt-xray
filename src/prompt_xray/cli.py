from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
import uvicorn

from .analysis import analyze_target
from .bench import (
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
from .intake import slug_from_target
from .reporting import write_comparison_outputs, write_outputs
from .webapp import create_app

app = typer.Typer(add_completion=False, help="Prompt archaeology for AI repos.")
bench_app = typer.Typer(add_completion=False, help="Run and compare benchmark corpora.")
app.add_typer(bench_app, name="bench")


@app.callback()
def main() -> None:
    """Prompt-xray CLI."""


@app.command()
def scan(
    target: str = typer.Argument(..., help="Local repo path or GitHub URL."),
    out: Optional[Path] = typer.Option(None, "--out", help="Output directory."),
    format_: str = typer.Option("both", "--format", help="markdown, json, or both."),
    html: bool = typer.Option(False, "--html", help="Also emit a screenshot-friendly HTML report."),
    max_file_size_kb: int = typer.Option(1024, "--max-file-size-kb", min=1),
    max_code_files_per_language: int = typer.Option(400, "--max-code-files-per-language", min=25),
    include_snippets: bool = typer.Option(True, "--include-snippets/--no-include-snippets"),
    verbose: bool = typer.Option(False, "--verbose"),
) -> None:
    fmt = format_.strip().lower()
    if fmt not in {"markdown", "json", "both"}:
        raise typer.BadParameter("Format must be one of: markdown, json, both")

    if verbose:
        typer.echo(f"Scanning target: {target}")

    report = analyze_target(
        target=target,
        max_file_size_kb=max_file_size_kb,
        include_snippets=include_snippets,
        max_code_files_per_language=max_code_files_per_language,
    )

    out_dir = out or (Path.cwd() / ".prompt-xray" / slug_from_target(target))
    written = write_outputs(report, out_dir=out_dir, fmt=fmt, html=html)

    typer.echo(f"Prompt-xray report for {report.repo.name}")
    typer.echo(f"- Archetype: {report.summary.repo_archetype}")
    typer.echo(f"- Orchestration: {report.summary.orchestration_model}")
    typer.echo(f"- Memory: {report.summary.memory_model}")
    typer.echo(f"- Candidate files: {report.counts.candidate_files}")
    typer.echo(f"- Artifacts: {report.counts.artifacts}")
    typer.echo(f"- Output: {out_dir}")

    if verbose and written:
        for path in written:
            typer.echo(f"  wrote {path}")


@app.command()
def compare(
    left: str = typer.Argument(..., help="First repo path or GitHub URL."),
    right: str = typer.Argument(..., help="Second repo path or GitHub URL."),
    out: Optional[Path] = typer.Option(None, "--out", help="Output directory."),
    format_: str = typer.Option("both", "--format", help="markdown, json, or both."),
    html: bool = typer.Option(False, "--html", help="Also emit a screenshot-friendly HTML comparison."),
    max_file_size_kb: int = typer.Option(1024, "--max-file-size-kb", min=1),
    max_code_files_per_language: int = typer.Option(400, "--max-code-files-per-language", min=25),
    include_snippets: bool = typer.Option(False, "--include-snippets/--no-include-snippets"),
    verbose: bool = typer.Option(False, "--verbose"),
) -> None:
    fmt = format_.strip().lower()
    if fmt not in {"markdown", "json", "both"}:
        raise typer.BadParameter("Format must be one of: markdown, json, both")

    if verbose:
        typer.echo(f"Comparing targets: {left} vs {right}")

    left_report = analyze_target(
        target=left,
        max_file_size_kb=max_file_size_kb,
        include_snippets=include_snippets,
        max_code_files_per_language=max_code_files_per_language,
    )
    right_report = analyze_target(
        target=right,
        max_file_size_kb=max_file_size_kb,
        include_snippets=include_snippets,
        max_code_files_per_language=max_code_files_per_language,
    )

    out_dir = out or (
        Path.cwd() / ".prompt-xray" / f"{slug_from_target(left)}-vs-{slug_from_target(right)}"
    )
    written = write_comparison_outputs(left_report, right_report, out_dir=out_dir, fmt=fmt, html=html)

    typer.echo(f"Prompt-xray compare: {left_report.repo.name} vs {right_report.repo.name}")
    typer.echo(f"- {left_report.repo.name}: {left_report.summary.xray_call}")
    typer.echo(f"- {right_report.repo.name}: {right_report.summary.xray_call}")
    typer.echo(f"- Output: {out_dir}")

    if verbose and written:
        for path in written:
            typer.echo(f"  wrote {path}")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind the UI server to."),
    port: int = typer.Option(8765, "--port", min=1, max=65535, help="Port for the UI server."),
) -> None:
    typer.echo(f"Serving Prompt-xray UI on http://{host}:{port}")
    uvicorn.run(create_app(), host=host, port=port, log_level="warning")


@bench_app.command("run")
def bench_run(
    cases_dir: Optional[Path] = typer.Option(None, "--cases-dir", help="Directory containing benchmark case JSON files."),
    out: Optional[Path] = typer.Option(None, "--out", help="Output directory."),
    max_file_size_kb: Optional[int] = typer.Option(None, "--max-file-size-kb", min=1),
    max_code_files_per_language: Optional[int] = typer.Option(None, "--max-code-files-per-language", min=25),
    subset: bool = typer.Option(False, "--subset", help="Run only the reduced benchmark subset from benchmarks/config.json."),
    verbose: bool = typer.Option(False, "--verbose"),
) -> None:
    config = load_benchmark_config()
    cases = load_cases(cases_dir)
    if not cases:
        raise typer.BadParameter("No benchmark cases found.")
    if subset:
        cases = select_cases(cases, config.reduced_case_ids)
        if not cases:
            raise typer.BadParameter("Reduced benchmark subset is empty.")

    run = run_benchmark(
        cases,
        max_file_size_kb=max_file_size_kb or config.default_max_file_size_kb,
        max_code_files_per_language=max_code_files_per_language or config.default_max_code_files_per_language,
        baseline_name="reduced" if subset else "full",
    )
    out_dir = out or (Path.cwd() / ".prompt-xray" / "bench" / "latest")
    written = write_benchmark_run(run, out_dir)

    typer.echo(f"Prompt-xray benchmark run: {run.case_count} cases")
    typer.echo(f"- Family exact matches: {run.metrics.family_exact_matches}/{run.metrics.total_cases}")
    typer.echo(f"- Archetype exact matches: {run.metrics.archetype_exact_matches}/{run.metrics.total_cases}")
    typer.echo(f"- Orchestration exact matches: {run.metrics.orchestration_exact_matches}/{run.metrics.total_cases}")
    typer.echo(f"- Memory exact matches: {run.metrics.memory_exact_matches}/{run.metrics.total_cases}")
    typer.echo(f"- Low-confidence cases: {run.metrics.low_confidence_cases}")
    typer.echo(f"- Output: {out_dir}")
    if verbose:
        for path in written:
            typer.echo(f"  wrote {path}")


@bench_app.command("diff")
def bench_diff(
    left: Path = typer.Argument(..., help="Path to a benchmark.json file from an earlier run."),
    right: Path = typer.Argument(..., help="Path to a benchmark.json file from a later run."),
    out: Optional[Path] = typer.Option(None, "--out", help="Output directory."),
    verbose: bool = typer.Option(False, "--verbose"),
) -> None:
    left_run = load_benchmark_run(left)
    right_run = load_benchmark_run(right)
    diff = diff_benchmark_runs(left_run, right_run, left, right)
    out_dir = out or (Path.cwd() / ".prompt-xray" / "bench" / "diff")
    written = write_benchmark_diff(diff, out_dir)

    typer.echo("Prompt-xray benchmark diff")
    typer.echo(f"- Family delta: {diff.summary['family_delta']}")
    typer.echo(f"- Archetype delta: {diff.summary['archetype_delta']}")
    typer.echo(f"- Orchestration delta: {diff.summary['orchestration_delta']}")
    typer.echo(f"- Memory delta: {diff.summary['memory_delta']}")
    typer.echo(f"- Low-confidence delta: {diff.summary['low_confidence_delta']}")
    typer.echo(f"- Changed cases: {len(diff.changed_cases)}")
    typer.echo(f"- Output: {out_dir}")
    if verbose:
        for path in written:
            typer.echo(f"  wrote {path}")


@bench_app.command("report")
def bench_report(
    benchmark_json: Path = typer.Argument(..., help="Path to a benchmark.json file."),
) -> None:
    run = load_benchmark_run(benchmark_json)
    typer.echo(render_benchmark_markdown(run))
