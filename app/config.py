from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    files_dir: Path
    db_path: Path
    range_count_window_seconds: int

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            files_dir=Path(os.getenv("FILES_DIR", "files")).expanduser(),
            db_path=Path(os.getenv("DB_PATH", "data/downloads.db")).expanduser(),
            range_count_window_seconds=int(os.getenv("COUNT_DEDUPE_SECONDS", "60")),
        )

    def resolve_paths(self, base_dir: Path) -> "AppConfig":
        files_dir = self.files_dir
        db_path = self.db_path

        if not files_dir.is_absolute():
            files_dir = base_dir / files_dir
        if not db_path.is_absolute():
            db_path = base_dir / db_path

        return AppConfig(
            files_dir=files_dir.resolve(strict=False),
            db_path=db_path.resolve(strict=False),
            range_count_window_seconds=self.range_count_window_seconds,
        )
