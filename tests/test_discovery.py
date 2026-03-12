from __future__ import annotations

from pathlib import Path

from prompt_xray.discovery import discover_code_files


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_discover_code_files_applies_caps_deterministically(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo / "zeta.py", "print('z')\n")
    _write(repo / "alpha.py", "print('a')\n")
    _write(repo / "middle.py", "print('m')\n")

    code_files, totals, truncated = discover_code_files(
        repo_path=repo,
        max_file_size_kb=1024,
        max_files_per_language=2,
    )

    assert [path.name for path in code_files] == ["alpha.py", "middle.py"]
    assert totals["python"] == 3
    assert truncated == ["python"]
