from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import AppConfig
from app.main import create_app


def make_client(
    files_dir: Path,
    db_path: Path,
    dedupe_seconds: int = 1,
) -> TestClient:
    config = AppConfig(
        files_dir=files_dir,
        db_path=db_path,
        range_count_window_seconds=dedupe_seconds,
    )
    app = create_app(config)
    return TestClient(app)


def write_text_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_index_returns_200_and_renders_files(tmp_path: Path) -> None:
    files_dir = tmp_path / "files"
    db_path = tmp_path / "data" / "downloads.db"
    write_text_file(files_dir / "manual.txt", "hello")

    with make_client(files_dir, db_path) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "manual.txt" in response.text


def test_api_files_returns_expected_fields(tmp_path: Path) -> None:
    files_dir = tmp_path / "files"
    db_path = tmp_path / "data" / "downloads.db"
    write_text_file(files_dir / "asset.bin", "payload")

    with make_client(files_dir, db_path) as client:
        response = client.get("/api/files")
        assert response.status_code == 200
        payload = response.json()
        assert "files" in payload
        assert len(payload["files"]) == 1
        row = payload["files"][0]
        assert row["name"] == "asset.bin"
        assert isinstance(row["size_bytes"], int)
        assert isinstance(row["updated_at"], str)
        assert row["download_count"] == 0
        assert row["download_url"] == "/download/asset.bin"


def test_download_increments_counter(tmp_path: Path) -> None:
    files_dir = tmp_path / "files"
    db_path = tmp_path / "data" / "downloads.db"
    write_text_file(files_dir / "report.pdf", "content")

    with make_client(files_dir, db_path) as client:
        response = client.get("/download/report.pdf")
        assert response.status_code == 200
        content_disposition = response.headers.get("content-disposition", "")
        assert "attachment" in content_disposition.lower()

        time.sleep(1.1)
        response = client.get("/download/report.pdf")
        assert response.status_code == 200

        listing = client.get("/api/files").json()["files"]
        assert listing[0]["download_count"] == 2


def test_download_missing_file_returns_404(tmp_path: Path) -> None:
    files_dir = tmp_path / "files"
    db_path = tmp_path / "data" / "downloads.db"

    with make_client(files_dir, db_path) as client:
        response = client.get("/download/not-found.zip")
        assert response.status_code == 404


def test_download_rejects_path_traversal(tmp_path: Path) -> None:
    files_dir = tmp_path / "files"
    db_path = tmp_path / "data" / "downloads.db"
    write_text_file(files_dir / "ok.txt", "safe")
    write_text_file(tmp_path / "secret.txt", "secret")

    with make_client(files_dir, db_path) as client:
        attack_response = client.get("/download/..%2Fsecret.txt")
        assert attack_response.status_code == 404

        backslash_response = client.get("/download/..%5Csecret.txt")
        assert backslash_response.status_code == 404


def test_counter_persists_across_app_restart(tmp_path: Path) -> None:
    files_dir = tmp_path / "files"
    db_path = tmp_path / "data" / "downloads.db"
    write_text_file(files_dir / "persist.txt", "stateful")

    with make_client(files_dir, db_path) as client:
        response = client.get("/download/persist.txt")
        assert response.status_code == 200

    with make_client(files_dir, db_path) as client:
        rows = client.get("/api/files").json()["files"]
        assert rows[0]["download_count"] == 1


def test_range_requests_count_once(tmp_path: Path) -> None:
    files_dir = tmp_path / "files"
    db_path = tmp_path / "data" / "downloads.db"
    write_text_file(files_dir / "movie.mp4", "0123456789abcdef")

    with make_client(files_dir, db_path) as client:
        first = client.get("/download/movie.mp4", headers={"Range": "bytes=0-3"})
        second = client.get("/download/movie.mp4", headers={"Range": "bytes=4-7"})
        third = client.get("/download/movie.mp4", headers={"Range": "bytes=8-15"})

        assert first.status_code in (200, 206)
        assert second.status_code in (200, 206)
        assert third.status_code in (200, 206)

        rows = client.get("/api/files").json()["files"]
        assert rows[0]["download_count"] == 1


def test_duplicate_non_range_requests_count_once(tmp_path: Path) -> None:
    files_dir = tmp_path / "files"
    db_path = tmp_path / "data" / "downloads.db"
    write_text_file(files_dir / "archive.zip", "abcdefghijk")

    with make_client(files_dir, db_path, dedupe_seconds=2) as client:
        first = client.get("/download/archive.zip")
        second = client.get("/download/archive.zip")
        third = client.get("/download/archive.zip")

        assert first.status_code == 200
        assert second.status_code == 200
        assert third.status_code == 200

        rows = client.get("/api/files").json()["files"]
        assert rows[0]["download_count"] == 1
