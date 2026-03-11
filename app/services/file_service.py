from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path


SYSTEM_FILENAMES = {"thumbs.db", "desktop.ini"}


@dataclass(frozen=True)
class FileEntry:
    name: str
    size_bytes: int
    updated_at: str
    download_count: int

    def to_dict(self) -> dict[str, str | int]:
        return asdict(self)


def ensure_files_dir(files_dir: Path) -> None:
    files_dir.mkdir(parents=True, exist_ok=True)


def list_files(files_dir: Path, download_counts: dict[str, int]) -> list[FileEntry]:
    entries: list[FileEntry] = []
    for file_path in sorted(files_dir.iterdir(), key=lambda item: item.name.lower()):
        if not _is_allowed_file(file_path):
            continue

        stat_result = file_path.stat()
        entries.append(
            FileEntry(
                name=file_path.name,
                size_bytes=stat_result.st_size,
                updated_at=datetime.fromtimestamp(
                    stat_result.st_mtime,
                    tz=timezone.utc,
                ).isoformat(),
                download_count=download_counts.get(file_path.name, 0),
            )
        )
    return entries


def resolve_file_for_download(files_dir: Path, filename: str) -> Path | None:
    if not filename:
        return None
    if "/" in filename or "\\" in filename:
        return None
    if filename in {".", ".."}:
        return None

    base_dir = files_dir.resolve(strict=False)
    requested_path = (base_dir / filename).resolve(strict=False)

    if requested_path.parent != base_dir:
        return None
    if not _is_allowed_file(requested_path):
        return None
    return requested_path


def _is_allowed_file(file_path: Path) -> bool:
    if not file_path.exists():
        return False
    if not file_path.is_file():
        return False
    if file_path.name.startswith("."):
        return False
    if file_path.name.lower() in SYSTEM_FILENAMES:
        return False
    return True

