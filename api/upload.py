"""
Image upload endpoint — stores uploaded images for Designer agent analysis.
"""
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

router = APIRouter()

UPLOAD_DIR = Path(__file__).parent.parent / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/upload/image")
async def upload_image(file: UploadFile = File(...)):
    suffix = Path(file.filename or "image.jpg").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Use: {', '.join(ALLOWED_EXTENSIONS)}",
        )
    content = await file.read()
    if len(content) > MAX_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File too large. Max 10 MB.")

    image_id = f"{uuid.uuid4()}{suffix}"
    (UPLOAD_DIR / image_id).write_bytes(content)
    return {"image_id": image_id}


@router.get("/upload/image/{image_id}")
async def get_image(image_id: str):
    """Serve uploaded images so the chat UI can display previews."""
    target = UPLOAD_DIR / Path(image_id).name  # prevent path traversal
    if not target.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(target)
