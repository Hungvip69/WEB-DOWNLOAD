from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import AppConfig
from .services.download_store import DownloadStore
from .services.github_releases_service import GithubReleasesService
from .services.range_count_guard import RangeCountGuard


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = Jinja2Templates(directory=str(PROJECT_ROOT / "templates"))
ICONS_DIR = PROJECT_ROOT / "icon"


def create_app(config: AppConfig | None = None) -> FastAPI:
    resolved_config = (config or AppConfig.from_env()).resolve_paths(PROJECT_ROOT)
    download_store = DownloadStore(resolved_config.db_path)
    range_guard = RangeCountGuard(resolved_config.range_count_window_seconds)
    github_service = GithubReleasesService(
        owner=resolved_config.github_owner,
        repo=resolved_config.github_repo,
        release_tag=resolved_config.github_release_tag,
        token=resolved_config.github_token,
        cache_seconds=resolved_config.github_cache_seconds,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        download_store.init()
        yield

    app = FastAPI(title="Public File Download Web", lifespan=lifespan)
    app.state.config = resolved_config
    app.state.download_store = download_store
    app.state.range_guard = range_guard
    app.state.github_service = github_service
    app.mount(
        "/static",
        StaticFiles(directory=str(PROJECT_ROOT / "static")),
        name="static",
    )
    if ICONS_DIR.exists():
        app.mount(
            "/icon",
            StaticFiles(directory=str(ICONS_DIR)),
            name="icon",
        )

    def counter_key(file_id: str) -> str:
        return f"gh_asset:{file_id}"

    def get_serialized_files() -> list[dict[str, str | int]]:
        entries = github_service.list_files()
        counts = download_store.load_counts()
        serialized: list[dict[str, str | int]] = []
        for entry in entries:
            row = entry.to_public_dict()
            row["download_count"] = counts.get(counter_key(entry.id), 0)
            row["download_url"] = f"/download/{quote(entry.id)}"
            serialized.append(row)
        return serialized

    @app.get("/")
    def index(request: Request):
        return TEMPLATES.TemplateResponse(
            request=request,
            name="index.html",
            context={"files": get_serialized_files()},
        )

    @app.get("/api/files")
    def api_files():
        files = get_serialized_files()
        warning = github_service.get_last_warning()
        return {"files": files, "warning": warning}

    @app.get("/download/{file_id}")
    def download(file_id: str, request: Request):
        file_entry = github_service.get_file(file_id)
        if file_entry is None:
            raise HTTPException(status_code=404, detail="File not found.")

        forwarded_for = request.headers.get("x-forwarded-for", "")
        client_id = forwarded_for.split(",")[0].strip()
        if not client_id:
            client_id = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")

        # Some browsers/download managers open multiple requests for one click.
        # Count only once per short dedupe window for the same client.
        dedupe_key = counter_key(file_entry.id)
        if range_guard.should_count(dedupe_key, client_id, user_agent):
            download_store.increment(dedupe_key)

        return RedirectResponse(url=file_entry.link, status_code=307)

    return app


app = create_app()


if __name__ == "__main__":
    import os

    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
