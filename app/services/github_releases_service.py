from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx


@dataclass(frozen=True)
class GithubReleaseAssetEntry:
    id: str
    name: str
    size_bytes: int
    updated_at: str
    link: str

    def to_public_dict(self) -> dict[str, str | int]:
        return {
            "id": self.id,
            "name": self.name,
            "size_bytes": self.size_bytes,
            "updated_at": self.updated_at,
        }


class GithubReleasesService:
    def __init__(
        self,
        owner: str,
        repo: str,
        release_tag: str,
        token: str,
        cache_seconds: int = 60,
        timeout_seconds: int = 25,
    ) -> None:
        self.owner = owner.strip()
        self.repo = repo.strip()
        self.release_tag = release_tag.strip()
        self.token = token.strip()
        self.cache_seconds = max(1, int(cache_seconds))
        self.timeout_seconds = timeout_seconds

        self._last_warning = ""
        self._cache_entries: list[GithubReleaseAssetEntry] | None = None
        self._cache_warning = ""
        self._cache_expires_at = 0.0
        self._lock = threading.Lock()

    def list_files(self) -> list[GithubReleaseAssetEntry]:
        now = time.monotonic()
        with self._lock:
            if self._cache_entries is not None and now < self._cache_expires_at:
                self._last_warning = self._cache_warning
                return list(self._cache_entries)

        entries, warning = self._fetch_files_uncached()

        with self._lock:
            self._cache_entries = list(entries)
            self._cache_warning = warning
            self._cache_expires_at = time.monotonic() + self.cache_seconds
            self._last_warning = warning
            return list(self._cache_entries)

    def get_last_warning(self) -> str:
        return self._last_warning

    def get_file(self, file_id: str) -> GithubReleaseAssetEntry | None:
        lookup_id = file_id.strip()
        if not lookup_id:
            return None
        for item in self.list_files():
            if item.id == lookup_id:
                return item
        return None

    def _fetch_files_uncached(self) -> tuple[list[GithubReleaseAssetEntry], str]:
        if not self.owner or not self.repo:
            return [], "Thieu GITHUB_OWNER hoac GITHUB_REPO."
        if not self.release_tag:
            return [], "Chua cau hinh GITHUB_RELEASE_TAG."

        payload, warning = self._fetch_release_payload()
        if payload is None:
            return [], warning

        raw_assets = payload.get("assets", [])
        if not isinstance(raw_assets, list):
            return [], "GitHub API tra ve assets khong hop le."

        entries: list[GithubReleaseAssetEntry] = []
        for item in raw_assets:
            if not isinstance(item, dict):
                continue

            asset_id = str(item.get("id", "")).strip()
            file_name = str(item.get("name", "")).strip()
            file_link = str(item.get("browser_download_url", "")).strip()
            if not asset_id or not file_name or not file_link:
                continue

            entries.append(
                GithubReleaseAssetEntry(
                    id=asset_id,
                    name=file_name,
                    size_bytes=_safe_int(item.get("size", 0)),
                    updated_at=_normalize_iso_datetime(
                        item.get("updated_at") or item.get("created_at")
                    ),
                    link=file_link,
                )
            )

        entries.sort(key=lambda x: x.name.lower())
        if not entries:
            return [], f"Release tag '{self.release_tag}' khong co asset de tai."
        return entries, ""

    def _fetch_release_payload(self) -> tuple[dict | None, str]:
        url = (
            f"https://api.github.com/repos/{self.owner}/{self.repo}"
            f"/releases/tags/{self.release_tag}"
        )
        headers = self._build_headers()

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.get(url, headers=headers)
        except httpx.HTTPError:
            return None, "Khong ket noi duoc GitHub API."

        payload = _json_or_none(response)
        message = _extract_error_message(payload)

        if response.status_code == 200:
            if not isinstance(payload, dict):
                return None, "GitHub API tra ve du lieu khong hop le."
            return payload, ""

        if response.status_code == 401:
            return None, "GitHub token khong hop le (unauthorized)."

        if response.status_code in (403, 429):
            if _is_rate_limited(response, payload):
                return None, "GitHub API rate limit. Thu lai sau hoac dat GITHUB_TOKEN."
            return None, "Khong du quyen truy cap GitHub release (forbidden)."

        if response.status_code == 404:
            repo_exists, repo_warning = self._check_repo_exists()
            if repo_warning:
                return None, repo_warning
            if repo_exists is False:
                return (
                    None,
                    f"Khong tim thay repo '{self.owner}/{self.repo}' hoac repo private.",
                )
            return None, f"Khong tim thay release tag '{self.release_tag}'."

        if message:
            return None, f"GitHub API loi: {message}"
        return None, f"GitHub API loi HTTP {response.status_code}."

    def _check_repo_exists(self) -> tuple[bool | None, str]:
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}"
        headers = self._build_headers()

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.get(url, headers=headers)
        except httpx.HTTPError:
            return None, "Khong ket noi duoc GitHub API de kiem tra repo."

        payload = _json_or_none(response)
        if response.status_code == 200:
            return True, ""
        if response.status_code == 404:
            return False, ""
        if response.status_code == 401:
            return None, "GitHub token khong hop le (unauthorized)."
        if response.status_code in (403, 429) and _is_rate_limited(response, payload):
            return None, "GitHub API rate limit. Thu lai sau hoac dat GITHUB_TOKEN."
        return None, ""

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "file-share-web",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers


def _safe_int(raw_value: object) -> int:
    try:
        return int(raw_value or 0)
    except (TypeError, ValueError):
        return 0


def _normalize_iso_datetime(raw_value: object) -> str:
    value = str(raw_value or "").strip()
    if value:
        return value
    return datetime.now(timezone.utc).isoformat()


def _json_or_none(response: httpx.Response) -> dict | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _extract_error_message(payload: dict | None) -> str:
    if not payload:
        return ""
    raw = payload.get("message")
    return str(raw or "").strip()


def _is_rate_limited(response: httpx.Response, payload: dict | None) -> bool:
    if response.status_code == 429:
        return True
    remaining = response.headers.get("X-RateLimit-Remaining", "")
    if remaining == "0":
        return True
    message = _extract_error_message(payload).lower()
    return "rate limit" in message
