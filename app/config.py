from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    db_path: Path
    range_count_window_seconds: int
    github_owner: str
    github_repo: str
    github_release_tag: str
    github_token: str
    github_cache_seconds: int

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            db_path=Path(os.getenv("DB_PATH", "data/downloads.db")).expanduser(),
            range_count_window_seconds=int(os.getenv("COUNT_DEDUPE_SECONDS", "60")),
            github_owner=os.getenv("GITHUB_OWNER", "Hungvip69").strip(),
            github_repo=os.getenv("GITHUB_REPO", "WEB-DOWNLOAD").strip(),
            github_release_tag=os.getenv("GITHUB_RELEASE_TAG", "").strip(),
            github_token=os.getenv("GITHUB_TOKEN", "").strip(),
            github_cache_seconds=int(os.getenv("GITHUB_CACHE_SECONDS", "60")),
        )

    def resolve_paths(self, base_dir: Path) -> "AppConfig":
        db_path = self.db_path

        if not db_path.is_absolute():
            db_path = base_dir / db_path

        return AppConfig(
            db_path=db_path.resolve(strict=False),
            range_count_window_seconds=self.range_count_window_seconds,
            github_owner=self.github_owner,
            github_repo=self.github_repo,
            github_release_tag=self.github_release_tag,
            github_token=self.github_token,
            github_cache_seconds=self.github_cache_seconds,
        )
