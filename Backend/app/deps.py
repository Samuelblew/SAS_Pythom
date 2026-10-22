from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.database import get_db
from app.exceptions import AppError, ValidationAppError

TENANT_HEADER = "X-Tenant-Id"
ACTOR_HEADER = "X-Actor-Id"
BYPASS_PREFIXES = (
    "/swagger",
    "/openapi.json",
    "/api/v1/health",
    "/api/v1/tenants",
    "/api/v1/auth/dev-token",
)


@dataclass
class RequestContext:
    tenant_id: str | None = None
    actor_id: str | None = None


def _bypass(path: str) -> bool:
    return any(path.lower().startswith(prefix) for prefix in BYPASS_PREFIXES)


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.ctx = RequestContext()
        if request.method == "OPTIONS" or _bypass(request.url.path):
            return await call_next(request)

        settings = get_settings()
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
            try:
                payload = jwt.decode(
                    token,
                    settings.jwt_secret,
                    algorithms=["HS256"],
                    audience=settings.jwt_audience,
                    issuer=settings.jwt_issuer,
                )
                tenant = payload.get("tenant_id")
                user_id = payload.get("sub") or payload.get("nameid")
                if tenant:
                    request.state.ctx.tenant_id = str(tenant)
                if user_id:
                    request.state.ctx.actor_id = str(user_id)
            except JWTError:
                pass

        if request.state.ctx.tenant_id is None:
            header = request.headers.get(TENANT_HEADER)
            try:
                request.state.ctx.tenant_id = str(UUID(header)) if header else None
            except (ValueError, TypeError):
                request.state.ctx.tenant_id = None

        if not request.state.ctx.tenant_id:
            return JSONResponse(
                status_code=400,
                media_type="application/problem+json",
                content={
                    "type": "https://tools.ietf.org/html/rfc7807",
                    "title": "Tenant obrigatório",
                    "status": 400,
                    "detail": f"Informe o header '{TENANT_HEADER}' com um GUID válido.",
                },
            )

        actor = request.headers.get(ACTOR_HEADER)
        if actor and not request.state.ctx.actor_id:
            request.state.ctx.actor_id = actor
        return await call_next(request)


def get_ctx(request: Request) -> RequestContext:
    return getattr(request.state, "ctx", RequestContext())


def require_tenant(ctx: RequestContext = Depends(get_ctx)) -> str:
    if not ctx.tenant_id:
        raise ValidationAppError("Tenant não resolvido.")
    return ctx.tenant_id


DbDep = Session
TenantDep = str
