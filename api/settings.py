"""
Settings API — password-protected configuration for data sources.
"""
import hashlib
import hmac
from pathlib import Path

from fastapi import APIRouter, Cookie, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from config import get_settings
from tools import settings_store

router = APIRouter()

KB_DIR = Path(__file__).parent.parent / "data" / "kb"
KB_DIR.mkdir(parents=True, exist_ok=True)


# ─── Auth helpers ──────────────────────────────────────────────

def _make_token() -> str:
    """Derive a fixed token from the admin password (stateless cookie auth)."""
    key = get_settings().admin_password.encode()
    return hmac.new(key, b"bio-agents-settings", hashlib.sha256).hexdigest()


def _require_auth(settings_auth: str | None):
    if not settings_auth:
        raise HTTPException(status_code=401, detail="Unauthorized")
    expected = _make_token()
    if not hmac.compare_digest(settings_auth, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


# ─── Auth routes ───────────────────────────────────────────────

class AuthRequest(BaseModel):
    password: str


@router.post("/settings/auth")
async def auth(req: AuthRequest):
    if req.password != get_settings().admin_password:
        raise HTTPException(status_code=401, detail="Wrong password")
    token = _make_token()
    response = JSONResponse({"ok": True})
    response.set_cookie(
        key="settings_auth",
        value=token,
        max_age=60 * 60 * 24,
        samesite="lax",
        httponly=True,
    )
    return response


@router.post("/settings/logout")
async def logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie("settings_auth")
    return response


# ─── Config GET ────────────────────────────────────────────────

@router.get("/settings")
async def get_settings_api(settings_auth: str = Cookie(default=None)):
    _require_auth(settings_auth)
    data = settings_store.load()
    # List actual KB files from disk
    data["designer"]["kb_files"] = sorted(f.name for f in KB_DIR.glob("*.md"))
    return data


# ─── Farmer ────────────────────────────────────────────────────

class FarmerSettings(BaseModel):
    runs_url: str = ""
    treatments_url: str = ""


@router.post("/settings/farmer")
async def save_farmer(req: FarmerSettings, settings_auth: str = Cookie(default=None)):
    _require_auth(settings_auth)
    data = settings_store.load()
    data["farmer"]["runs_url"] = req.runs_url.strip()
    data["farmer"]["treatments_url"] = req.treatments_url.strip()
    settings_store.save(data)
    return {"ok": True}


# ─── Designer ──────────────────────────────────────────────────

class DesignerSettings(BaseModel):
    replicate_version: str = ""


@router.post("/settings/designer")
async def save_designer(
    req: DesignerSettings, settings_auth: str = Cookie(default=None)
):
    _require_auth(settings_auth)
    data = settings_store.load()
    data["designer"]["replicate_version"] = req.replicate_version.strip()
    settings_store.save(data)
    return {"ok": True}


# ─── CFO — TEM model upload ────────────────────────────────────

@router.post("/settings/upload/tem")
async def upload_tem(
    file: UploadFile = File(...),
    settings_auth: str = Cookie(default=None),
):
    _require_auth(settings_auth)
    if not (file.filename or "").endswith(".md"):
        raise HTTPException(status_code=400, detail="Only .md files accepted")
    dest = KB_DIR / "tem_model.md"
    dest.write_bytes(await file.read())
    data = settings_store.load()
    data["cfo"]["tem_model_file"] = "tem_model.md"
    settings_store.save(data)
    return {"ok": True, "filename": "tem_model.md"}


# ─── Designer — KB file upload / delete ────────────────────────

@router.post("/settings/upload/kb")
async def upload_kb(
    file: UploadFile = File(...),
    settings_auth: str = Cookie(default=None),
):
    _require_auth(settings_auth)
    if not (file.filename or "").endswith(".md"):
        raise HTTPException(status_code=400, detail="Only .md files accepted")
    safe_name = Path(file.filename or "upload.md").name
    (KB_DIR / safe_name).write_bytes(await file.read())
    return {"ok": True, "filename": safe_name}


@router.delete("/settings/kb/{filename}")
async def delete_kb(filename: str, settings_auth: str = Cookie(default=None)):
    _require_auth(settings_auth)
    target = KB_DIR / Path(filename).name  # prevent path traversal
    if target.exists():
        target.unlink()
    return {"ok": True}
