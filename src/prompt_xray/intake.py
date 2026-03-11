from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .models import RepoInfo

GITHUB_RE = re.compile(r"^https?://github\.com/([^/\s]+)/([^/\s#]+?)(?:\.git)?/?$")


def is_github_url(target: str) -> bool:
    return bool(GITHUB_RE.match(target.strip()))


def slug_from_target(target: str) -> str:
    if is_github_url(target):
        match = GITHUB_RE.match(target.strip())
        assert match is not None
        return match.group(2).removesuffix(".git")

    path = Path(target).expanduser().resolve()
    return path.name or "scan-target"


def _git_output(repo_path: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args],
            cwd=repo_path,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _clone_repo(url: str, git_ref: str = "") -> Path:
    slug = slug_from_target(url)
    ref_part = git_ref.strip()[:12] if git_ref else "head"
    digest = hashlib.sha1(f"{url}@{ref_part}".encode("utf-8")).hexdigest()[:10]
    cache_root = Path(tempfile.gettempdir()) / "prompt_xray_cache"
    clone_path = cache_root / f"{slug}-{digest}"
    cache_root.mkdir(parents=True, exist_ok=True)

    if clone_path.exists() and (clone_path / ".git").exists():
        return clone_path
    if clone_path.exists():
        shutil.rmtree(clone_path, ignore_errors=True)

    try:
        if git_ref:
            subprocess.run(
                ["git", "clone", "--filter=blob:none", "--no-checkout", url, str(clone_path)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                subprocess.run(
                    ["git", "checkout", "--detach", git_ref],
                    cwd=clone_path,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except subprocess.CalledProcessError:
                subprocess.run(
                    ["git", "fetch", "--filter=blob:none", "origin", git_ref],
                    cwd=clone_path,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                subprocess.run(
                    ["git", "checkout", "--detach", git_ref],
                    cwd=clone_path,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        else:
            try:
                subprocess.run(
                    ["git", "clone", "--depth", "1", url, str(clone_path)],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except subprocess.CalledProcessError:
                shutil.rmtree(clone_path, ignore_errors=True)
                subprocess.run(
                    ["git", "clone", "--filter=blob:none", url, str(clone_path)],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        return clone_path
    except subprocess.CalledProcessError:
        shutil.rmtree(clone_path, ignore_errors=True)
        raise


def resolve_target(target: str, git_ref: str = "") -> tuple[RepoInfo, Path]:
    if is_github_url(target):
        repo_path = _clone_repo(target, git_ref=git_ref)
        info = RepoInfo(
            name=slug_from_target(target),
            target=target,
            source_type="github",
            commit=_git_output(repo_path, "rev-parse", "HEAD"),
            root_path=str(repo_path),
        )
        return info, repo_path

    repo_path = Path(target).expanduser().resolve()
    if not repo_path.exists():
        raise FileNotFoundError(f"Target does not exist: {target}")
    if not repo_path.is_dir():
        raise NotADirectoryError(f"Target is not a directory: {target}")

    info = RepoInfo(
        name=slug_from_target(target),
        target=str(repo_path),
        source_type="local",
        commit=_git_output(repo_path, "rev-parse", "HEAD"),
        root_path=str(repo_path),
    )
    return info, repo_path
