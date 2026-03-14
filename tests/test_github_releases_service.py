from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.services.github_releases_service import GithubReleasesService


@dataclass
class _FakeResponse:
    status_code: int
    payload: dict
    headers: dict[str, str] | None = None

    def json(self) -> dict:
        return self.payload


class _FakeClient:
    def __init__(self, responses: list[_FakeResponse], call_counter: dict[str, int]):
        self._responses = responses
        self._call_counter = call_counter

    def __enter__(self) -> "_FakeClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def get(self, url: str, headers: dict[str, str] | None = None) -> _FakeResponse:
        self._call_counter["count"] += 1
        if not self._responses:
            raise AssertionError(f"Unexpected GET call for URL: {url}")
        return self._responses.pop(0)


def _patch_http_client(
    monkeypatch,
    responses: list[_FakeResponse],
    call_counter: dict[str, int] | None = None,
) -> dict[str, int]:
    counter = call_counter or {"count": 0}
    queue = list(responses)

    def factory(*args, **kwargs):
        return _FakeClient(responses=queue, call_counter=counter)

    monkeypatch.setattr(httpx, "Client", factory)
    return counter


def _make_service(tag: str = "v1.0.0") -> GithubReleasesService:
    return GithubReleasesService(
        owner="Hungvip69",
        repo="WEB-DOWNLOAD",
        release_tag=tag,
        token="",
        cache_seconds=60,
        timeout_seconds=5,
    )


def test_parse_assets_from_release_payload(monkeypatch) -> None:
    release_payload = {
        "assets": [
            {
                "id": 22,
                "name": "tools.zip",
                "size": 4096,
                "updated_at": "2026-03-14T00:00:00Z",
                "browser_download_url": "https://github.com/x/tools.zip",
            },
            {
                "id": 21,
                "name": "alpha.bin",
                "size": 1024,
                "created_at": "2026-03-13T00:00:00Z",
                "browser_download_url": "https://github.com/x/alpha.bin",
            },
        ]
    }
    _patch_http_client(monkeypatch, [_FakeResponse(200, release_payload)])

    service = _make_service()
    entries = service.list_files()

    assert len(entries) == 2
    assert [e.name for e in entries] == ["alpha.bin", "tools.zip"]
    assert entries[0].id == "21"
    assert entries[0].size_bytes == 1024
    assert entries[0].link == "https://github.com/x/alpha.bin"
    assert service.get_last_warning() == ""


def test_warning_when_release_tag_not_found(monkeypatch) -> None:
    responses = [
        _FakeResponse(404, {"message": "Not Found"}),
        _FakeResponse(200, {"id": 1}),
    ]
    _patch_http_client(monkeypatch, responses)

    service = _make_service(tag="missing-tag")
    entries = service.list_files()

    assert entries == []
    assert "missing-tag" in service.get_last_warning()


def test_warning_when_repo_not_found(monkeypatch) -> None:
    responses = [
        _FakeResponse(404, {"message": "Not Found"}),
        _FakeResponse(404, {"message": "Not Found"}),
    ]
    _patch_http_client(monkeypatch, responses)

    service = _make_service(tag="v1.0.0")
    entries = service.list_files()

    assert entries == []
    assert "Khong tim thay repo" in service.get_last_warning()


def test_warning_when_rate_limited(monkeypatch) -> None:
    responses = [
        _FakeResponse(
            403,
            {"message": "API rate limit exceeded"},
            headers={"X-RateLimit-Remaining": "0"},
        )
    ]
    _patch_http_client(monkeypatch, responses)

    service = _make_service()
    entries = service.list_files()

    assert entries == []
    assert "rate limit" in service.get_last_warning().lower()


def test_warning_when_unauthorized(monkeypatch) -> None:
    responses = [_FakeResponse(401, {"message": "Bad credentials"})]
    _patch_http_client(monkeypatch, responses)

    service = _make_service()
    entries = service.list_files()

    assert entries == []
    assert "unauthorized" in service.get_last_warning().lower()


def test_cache_ttl_reuses_cached_entries(monkeypatch) -> None:
    release_payload = {
        "assets": [
            {
                "id": 11,
                "name": "bundle.zip",
                "size": 2048,
                "updated_at": "2026-03-14T00:00:00Z",
                "browser_download_url": "https://github.com/x/bundle.zip",
            }
        ]
    }
    counter = _patch_http_client(monkeypatch, [_FakeResponse(200, release_payload)])

    service = _make_service()
    first = service.list_files()
    second = service.list_files()

    assert len(first) == 1
    assert len(second) == 1
    assert first[0].id == "11"
    assert counter["count"] == 1
