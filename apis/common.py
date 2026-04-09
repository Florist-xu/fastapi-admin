from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse


commonAPI = APIRouter(prefix="/common", tags=["common"])

UPLOAD_ROOT = Path(__file__).resolve().parent.parent / "uplode" / "wangeditor"
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
}


@commonAPI.post("/upload/wangeditor", summary="上传富文本图片")
async def upload_wangeditor_image(file: UploadFile = File(...)):
    extension = Path(file.filename or "").suffix.lower()
    if not extension:
        extension = CONTENT_TYPE_EXTENSIONS.get(file.content_type or "", "")

    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        return JSONResponse(
            status_code=400,
            content={"errno": 1, "message": "仅支持 jpg、png、gif、webp、bmp 图片"},
        )

    month_folder = datetime.now().strftime("%Y%m")
    target_dir = UPLOAD_ROOT / month_folder
    target_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid4().hex}{extension}"
    save_path = target_dir / filename
    content = await file.read()
    save_path.write_bytes(content)

    url = f"/files/wangeditor/{month_folder}/{filename}"
    return {
        "errno": 0,
        "message": "上传成功",
        "data": {"url": url, "alt": file.filename or "", "href": url},
        "url": url,
    }
