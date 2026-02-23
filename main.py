from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from api.chat import router as chat_router
from api.settings import router as settings_router
from api.upload import router as upload_router

app = FastAPI(title="bio-agents")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def iframe_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "ALLOWALL"
    response.headers["Content-Security-Policy"] = "frame-ancestors *"
    return response


app.include_router(chat_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(upload_router, prefix="/api")
app.mount("/", StaticFiles(directory="static", html=True), name="static")
