from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import AppConfig
from .services.download_store import DownloadStore
from .services.file_service import ensure_files_dir, list_files, resolve_file_for_download
from .services.range_count_guard import RangeCountGuard


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = Jinja2Templates(directory=str(PROJECT_ROOT / "templates"))
ICONS_DIR = PROJECT_ROOT / "icon"


def create_app(config: AppConfig | None = None) -> FastAPI:
    resolved_config = (config or AppConfig.from_env()).resolve_paths(PROJECT_ROOT)
    download_store = DownloadStore(resolved_config.db_path)
    range_guard = RangeCountGuard(resolved_config.range_count_window_seconds)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        ensure_files_dir(resolved_config.files_dir)
        download_store.init()
        yield

    app = FastAPI(title="Public File Download Web", lifespan=lifespan)
    app.state.config = resolved_config
    app.state.download_store = download_store
    app.state.range_guard = range_guard
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

    def get_serialized_files() -> list[dict[str, str | int]]:
        entries = list_files(
            files_dir=resolved_config.files_dir,
            download_counts=download_store.load_counts(),
        )
        serialized: list[dict[str, str | int]] = []
        for entry in entries:
            row = entry.to_dict()
            row["download_url"] = f"/download/{quote(entry.name)}"
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
        return {"files": get_serialized_files()}

    @app.get("/download/{filename}")
    def download(filename: str, request: Request):
        file_path = resolve_file_for_download(resolved_config.files_dir, filename)
        if file_path is None:
            raise HTTPException(status_code=404, detail="File not found.")

        forwarded_for = request.headers.get("x-forwarded-for", "")
        client_id = forwarded_for.split(",")[0].strip()
        if not client_id:
            client_id = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")

        # Some browsers/download managers open multiple requests for one click.
        # Count only once per short dedupe window for the same client.
        if range_guard.should_count(file_path.name, client_id, user_agent):
            download_store.increment(file_path.name)

        encoded_name = quote(file_path.name)
        headers = {
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}",
        }
        return FileResponse(
            path=file_path,
            media_type="application/octet-stream",
            filename=file_path.name,
            headers=headers,
        )

    return app


app = create_app()


if __name__ == "__main__":
    import os

    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
