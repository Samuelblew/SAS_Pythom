from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.bootstrap import ensure_schema
from app.config import get_settings
from app.deps import TenantMiddleware
from app.exceptions import AppError
from app.routers import analytics, auth, catalog, health, work

ensure_schema()

settings = get_settings()

app = FastAPI(
    title="IAS API",
    version="v1",
    docs_url="/swagger",
    redoc_url=None,
    openapi_url="/swagger/v1/swagger.json",
)

app.add_middleware(TenantMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(work.router)
app.include_router(analytics.router)


def problem(status: int, title: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content={
            "type": "https://tools.ietf.org/html/rfc7807",
            "title": title,
            "status": status,
            "detail": detail,
        },
    )


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError):
    return problem(exc.status, exc.title, exc.detail)


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    messages = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err.get("loc", []) if part != "body")
        messages.append(f"{loc}: {err.get('msg')}" if loc else str(err.get("msg")))
    return problem(400, "Erro de validação", "; ".join(messages))


@app.exception_handler(Exception)
async def unhandled(_: Request, __: Exception):
    return problem(500, "Erro interno", "Ocorreu um erro inesperado.")


def _frontend_dist() -> Path | None:
    if settings.frontend_dist:
        configured = Path(settings.frontend_dist)
        if (configured / "index.html").is_file():
            return configured
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2] / "Frontend" / "dist",
        here.parents[1].parent / "Frontend" / "dist",
        Path("/app/Frontend/dist"),
    ]
    for path in candidates:
        if (path / "index.html").is_file():
            return path
    return None


_dist = _frontend_dist()
if _dist is not None:
    assets = _dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/", include_in_schema=False)
    def spa_root():
        return FileResponse(_dist / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("swagger"):
            raise HTTPException(status_code=404, detail="Não encontrado")
        target = (_dist / full_path).resolve()
        if _dist.resolve() not in target.parents and target != _dist.resolve():
            raise HTTPException(status_code=404, detail="Não encontrado")
        if target.is_file():
            return FileResponse(target)
        return FileResponse(_dist / "index.html")
