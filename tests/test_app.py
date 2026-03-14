from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import AppConfig
from app.main import create_app
from app.services.github_releases_service import GithubReleaseAssetEntry


def make_client(
    db_path: Path,
    entries: list[GithubReleaseAssetEntry] | None = None,
    dedupe_seconds: int = 1,
) -> TestClient:
    config = AppConfig(
        db_path=db_path,
        range_count_window_seconds=dedupe_seconds,
        github_owner="Hungvip69",
        github_repo="WEB-DOWNLOAD",
        github_release_tag="v1.0.0",
        github_token="",
        github_cache_seconds=60,
    )
    app = create_app(config)
    items = entries or []
    app.state.github_service.list_files = lambda: items
    app.state.github_service.get_file = (
        lambda file_id: next((x for x in items if x.id == file_id), None)
    )
    app.state.github_service.get_last_warning = lambda: ""
    return TestClient(app)


def build_entry(file_id: str, name: str, link: str) -> GithubReleaseAssetEntry:
    return GithubReleaseAssetEntry(
        id=file_id,
        name=name,
        size_bytes=1234,
        updated_at="2026-03-14T00:00:00+00:00",
        link=link,
    )


def test_index_returns_200_and_renders_files(tmp_path: Path) -> None:
    db_path = tmp_path / "data" / "downloads.db"
    entries = [build_entry("f1", "manual.txt", "https://example.com/manual.txt")]

    with make_client(db_path, entries) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "manual.txt" in response.text


def test_api_files_returns_expected_fields(tmp_path: Path) -> None:
    db_path = tmp_path / "data" / "downloads.db"
    entries = [build_entry("f2", "asset.bin", "https://example.com/asset.bin")]

    with make_client(db_path, entries) as client:
        response = client.get("/api/files")
        assert response.status_code == 200
        payload = response.json()
        assert "files" in payload
        assert "warning" in payload
        assert payload["warning"] == ""
        assert len(payload["files"]) == 1
        row = payload["files"][0]
        assert row["name"] == "asset.bin"
        assert isinstance(row["size_bytes"], int)
        assert isinstance(row["updated_at"], str)
        assert row["download_count"] == 0
        assert row["download_url"] == "/download/f2"


def test_api_files_includes_warning(tmp_path: Path) -> None:
    db_path = tmp_path / "data" / "downloads.db"
    entries = [build_entry("f3", "pack.zip", "https://example.com/pack.zip")]

    with make_client(db_path, entries) as client:
        client.app.state.github_service.get_last_warning = (
            lambda: "Khong tim thay release tag 'v9'."
        )
        payload = client.get("/api/files").json()
        assert payload["warning"] == "Khong tim thay release tag 'v9'."


def test_download_increments_counter(tmp_path: Path) -> None:
    db_path = tmp_path / "data" / "downloads.db"
    entries = [build_entry("file-report", "report.pdf", "https://example.com/report.pdf")]

    with make_client(db_path, entries) as client:
        response = client.get("/download/file-report", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "https://example.com/report.pdf"

        time.sleep(1.1)
        response = client.get("/download/file-report", follow_redirects=False)
        assert response.status_code == 307

        listing = client.get("/api/files").json()["files"]
        assert listing[0]["download_count"] == 2


def test_download_missing_file_returns_404(tmp_path: Path) -> None:
    db_path = tmp_path / "data" / "downloads.db"

    with make_client(db_path, []) as client:
        response = client.get("/download/not-found-id", follow_redirects=False)
        assert response.status_code == 404


def test_download_unknown_id_returns_404(tmp_path: Path) -> None:
    db_path = tmp_path / "data" / "downloads.db"
    entries = [build_entry("ok-id", "ok.txt", "https://example.com/ok.txt")]

    with make_client(db_path, entries) as client:
        response = client.get("/download/not-this-id", follow_redirects=False)
        assert response.status_code == 404


def test_counter_persists_across_app_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "data" / "downloads.db"
    entries = [build_entry("persist-id", "persist.txt", "https://example.com/persist.txt")]

    with make_client(db_path, entries) as client:
        response = client.get("/download/persist-id", follow_redirects=False)
        assert response.status_code == 307

    with make_client(db_path, entries) as client:
        rows = client.get("/api/files").json()["files"]
        assert rows[0]["download_count"] == 1


def test_range_requests_count_once(tmp_path: Path) -> None:
    db_path = tmp_path / "data" / "downloads.db"
    entries = [build_entry("movie-id", "movie.mp4", "https://example.com/movie.mp4")]

    with make_client(db_path, entries) as client:
        first = client.get(
            "/download/movie-id",
            headers={"Range": "bytes=0-3"},
            follow_redirects=False,
        )
        second = client.get(
            "/download/movie-id",
            headers={"Range": "bytes=4-7"},
            follow_redirects=False,
        )
        third = client.get(
            "/download/movie-id",
            headers={"Range": "bytes=8-15"},
            follow_redirects=False,
        )

        assert first.status_code == 307
        assert second.status_code == 307
        assert third.status_code == 307

        rows = client.get("/api/files").json()["files"]
        assert rows[0]["download_count"] == 1


def test_duplicate_non_range_requests_count_once(tmp_path: Path) -> None:
    db_path = tmp_path / "data" / "downloads.db"
    entries = [build_entry("archive-id", "archive.zip", "https://example.com/archive.zip")]

    with make_client(db_path, entries, dedupe_seconds=2) as client:
        first = client.get("/download/archive-id", follow_redirects=False)
        second = client.get("/download/archive-id", follow_redirects=False)
        third = client.get("/download/archive-id", follow_redirects=False)

        assert first.status_code == 307
        assert second.status_code == 307
        assert third.status_code == 307

        rows = client.get("/api/files").json()["files"]
        assert rows[0]["download_count"] == 1
