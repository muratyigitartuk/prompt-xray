from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from prompt_xray.webapp import create_app


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_manifest_endpoint_works() -> None:
    client = TestClient(create_app())
    response = client.get("/api/manifest")

    assert response.status_code == 200
    payload = response.json()
    assert "reports" in payload
    assert "comparisons" in payload


def test_scan_endpoint_returns_report(tmp_path: Path) -> None:
    repo = tmp_path / "scan-repo"
    _write(
        repo / "AGENTS.md",
        """You are a strict agent.
Critical rules apply.
Remember prior state.
""",
    )

    client = TestClient(create_app())
    response = client.post("/api/scan", json={"target": str(repo)})

    assert response.status_code == 200
    payload = response.json()
    assert payload["repo"]["name"] == "scan-repo"
    assert payload["summary"]["xray_call"]


def test_compare_endpoint_returns_comparison(tmp_path: Path) -> None:
    left = tmp_path / "left-repo"
    right = tmp_path / "right-repo"
    _write(left / "SKILL.md", "---\nname: left\ndescription: left\n---\nUse this skill.")
    _write(right / "src" / "server.py", "print('runtime')\n")
    _write(right / "AGENTS.md", "You are a system prompt.")

    client = TestClient(create_app())
    response = client.post(
        "/api/compare",
        json={"left": str(left), "right": str(right)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["left"]["name"] == "left-repo"
    assert payload["right"]["name"] == "right-repo"
    assert "xray_call" in payload["left"]
