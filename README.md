# File Share Web

Web FastAPI de moi nguoi truy cap va tai file cong khai. Danh sach file duoc doc tu GitHub Releases (tag co dinh).

## Tinh nang

- `GET /`: giao dien danh sach file.
- `GET /api/files`: API JSON chua metadata file + warning.
- `GET /download/{file_id}`: tang `download_count`, sau do redirect sang link tai cua GitHub asset.
- Chong dem trung request tai trong mot khoang thoi gian ngan.
- Luu luot tai cuc bo bang SQLite.

## Yeu cau

- Python 3.10+
- Repo release public hoac private co token.

## Chay local

```bash
cd file-share-web
python -m venv .venv
.venv\\Scripts\\python.exe -m pip install -r requirements.txt
```

```powershell
$env:GITHUB_OWNER="Hungvip69"
$env:GITHUB_REPO="WEB-DOWNLOAD"
$env:GITHUB_RELEASE_TAG="v1.0.0"
$env:GITHUB_TOKEN=""   # de trong neu repo public
$env:GITHUB_CACHE_SECONDS="60"
$env:DB_PATH="data/downloads.db"
$env:COUNT_DEDUPE_SECONDS="60"
.\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Bien moi truong

- `GITHUB_OWNER`: owner repo (mac dinh `Hungvip69`).
- `GITHUB_REPO`: ten repo (mac dinh `WEB-DOWNLOAD`).
- `GITHUB_RELEASE_TAG`: tag release can doc (bat buoc).
- `GITHUB_TOKEN`: GitHub PAT (optional, can cho repo private/ tang rate limit).
- `GITHUB_CACHE_SECONDS`: TTL cache danh sach asset (mac dinh `60`).
- `DB_PATH`: duong dan SQLite (mac dinh `data/downloads.db`).
- `COUNT_DEDUPE_SECONDS`: cua so chong dem trung (mac dinh `60`).
- `PORT`: cong app (mac dinh `8000`).

## Van hanh

- Upload file len release asset theo tag da chon.
- Moi lan thay doi file, cap nhat release tag tuong ung.
- Kiem tra URL public bang route `/` sau deploy.

## Deploy Render

Project co san `render.yaml`:

- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Bien can set toi thieu:
  - `GITHUB_RELEASE_TAG`
  - `GITHUB_TOKEN` (neu repo private)
  - `DB_PATH=/var/data/downloads.db`
- Nen gan persistent disk tai `/var/data` de giu SQLite counter qua cac lan deploy.

## Test

```bash
cd file-share-web
python -m pytest -q
```
