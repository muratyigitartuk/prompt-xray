from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
import uvicorn

from .analysis import analyze_target
from .intake import slug_from_target
from .reporting import write_comparison_outputs, write_outputs
from .webapp import create_app

app = typer.Typer(add_completion=False, help="Prompt archaeology for AI repos.")


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
    )
    right_report = analyze_target(
        target=right,
        max_file_size_kb=max_file_size_kb,
        include_snippets=include_snippets,
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
