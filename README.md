# File Share Web

Web FastAPI cho phép mọi người truy cập và tải file công khai.

## Tính năng

- `GET /`: giao diện danh sách file.
- `GET /api/files`: API JSON chứa metadata file và lượt tải.
- `GET /download/{filename}`: tải file và tự tăng `download_count`.
- Bảo vệ path traversal (`../`, `\`, đường dẫn ngoài thư mục gốc).
- Lưu lượt tải cục bộ bằng SQLite.

## Yêu cầu

- Python 3.10+

## Chạy local

```bash
cd file-share-web
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Biến môi trường

- `FILES_DIR`: thư mục chứa file tải về (mặc định: `files`)
- `DB_PATH`: đường dẫn SQLite (mặc định: `data/downloads.db`)
- `COUNT_DEDUPE_SECONDS`: thời gian chống đếm trùng cho mọi request tải lặp từ cùng client (mặc định: `60`)
- `PORT`: cổng chạy app (mặc định: `8000`)

Ví dụ PowerShell:

```powershell
$env:FILES_DIR="files"
$env:DB_PATH="data/downloads.db"
$env:COUNT_DEDUPE_SECONDS="60"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Vận hành

- Thêm file: chép trực tiếp vào thư mục `FILES_DIR`.
- Xóa file: xóa khỏi `FILES_DIR` (counter vẫn giữ trong DB, sẽ tự bỏ khỏi danh sách khi file không còn).
- Kiểm tra URL public: mở route `/` sau deploy.

## Deploy Render

Project có sẵn `render.yaml`:

- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- `FILES_DIR=/var/data/files`
- `DB_PATH=/var/data/downloads.db`
- Gắn persistent disk tại `/var/data` để giữ file + DB qua các lần deploy.

Lưu ý: nếu không có persistent disk, dữ liệu file và lượt tải có thể mất khi redeploy.

## Test

```bash
cd file-share-web
pytest -q
```
