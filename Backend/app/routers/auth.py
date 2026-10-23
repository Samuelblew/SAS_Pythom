from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from jose import jwt
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.exceptions import NotFoundError
from app.helpers import alive, parse_page, paginate, audit, utcnow, get_or_404, by_tenant, soft_delete
from app.maps import tenant_out, user_out
from app.models import Tenant, User, new_id
from app.schemas import DevTokenIn, TenantCreate, UserCreate, UserUpdate, paged
from app.deps import get_ctx, require_tenant, RequestContext

router = APIRouter()


@router.post("/api/v1/tenants", status_code=201)
def create_tenant(body: TenantCreate, db: Session = Depends(get_db, scope="function")):
    name = body.name.strip()
    exists = alive(db.query(Tenant).filter(Tenant.name == name), Tenant).first()
    if exists:
        from app.exceptions import ConflictError
        raise ConflictError(f"Já existe um tenant com o nome '{name}'.")
    item = Tenant(id=new_id(), name=name, is_active=True, created_at=utcnow())
    db.add(item)
    db.flush()
    return tenant_out(item)


@router.get("/api/v1/tenants/{item_id}")
def get_tenant(item_id: UUID, db: Session = Depends(get_db, scope="function")):
    item = alive(db.query(Tenant).filter(Tenant.id == str(item_id)), Tenant).first()
    if not item:
        raise NotFoundError(f"Tenant '{item_id}' não encontrado.")
    return tenant_out(item)


@router.post("/api/v1/auth/dev-token")
def dev_token(body: DevTokenIn, db: Session = Depends(get_db, scope="function")):
    settings = get_settings()
    if not settings.is_dev:
        raise NotFoundError("Não encontrado")
    tenant = alive(db.query(Tenant).filter(Tenant.id == str(body.tenant_id)), Tenant).first()
    user = alive(db.query(User).filter(User.id == str(body.user_id), User.tenant_id == str(body.tenant_id)), User).first()
    if not tenant or not user:
        raise NotFoundError("Tenant ou usuário não encontrado.")
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": user.id,
            "nameid": user.id,
            "tenant_id": tenant.id,
            "email": user.email,
            "display_name": user.display_name,
            "unique_name": user.display_name,
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "exp": now + timedelta(hours=settings.jwt_expiration_hours),
            "iat": now,
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    return {
        "accessToken": token,
        "tokenType": "Bearer",
        "expiresInHours": settings.jwt_expiration_hours,
    }


@router.get("/api/v1/users")
def list_users(
    page: int = 1,
    pageSize: int = 20,
    db: Session = Depends(get_db, scope="function"),
    tenant_id: str = Depends(require_tenant),
):
    page, page_size = parse_page(page, pageSize)
    query = by_tenant(db.query(User), User, tenant_id).order_by(User.display_name)
    items, total = paginate(query, page, page_size)
    return paged([user_out(i) for i in items], page, page_size, total)


@router.get("/api/v1/users/{item_id}")
def get_user(item_id: UUID, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    return user_out(get_or_404(db, User, item_id, tenant_id, "Usuário"))


@router.post("/api/v1/users", status_code=201)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db, scope="function"),
    tenant_id: str = Depends(require_tenant),
    ctx: RequestContext = Depends(get_ctx),
):
    from app.exceptions import ConflictError
    email = body.email.strip()
    exists = by_tenant(db.query(User).filter(User.email == email), User, tenant_id).first()
    if exists:
        raise ConflictError(f"Já existe um usuário com o e-mail '{email}'.")
    item = User(
        id=new_id(),
        tenant_id=tenant_id,
        email=email,
        display_name=body.display_name.strip(),
        role=body.role,
        is_active=True,
        created_at=utcnow(),
    )
    db.add(item)
    db.flush()
    audit(db, tenant_id, "User", item.id, "Created", ctx.actor_id)
    return user_out(item)


@router.put("/api/v1/users/{item_id}")
def update_user(
    item_id: UUID,
    body: UserUpdate,
    db: Session = Depends(get_db, scope="function"),
    tenant_id: str = Depends(require_tenant),
    ctx: RequestContext = Depends(get_ctx),
):
    from app.exceptions import ConflictError
    item = get_or_404(db, User, item_id, tenant_id, "Usuário")
    email = body.email.strip()
    exists = by_tenant(db.query(User).filter(User.email == email, User.id != item.id), User, tenant_id).first()
    if exists:
        raise ConflictError(f"Já existe um usuário com o e-mail '{email}'.")
    item.email = email
    item.display_name = body.display_name.strip()
    item.role = body.role
    item.is_active = body.is_active
    item.updated_at = utcnow()
    audit(db, tenant_id, "User", item.id, "Updated", ctx.actor_id)
    return user_out(item)


@router.delete("/api/v1/users/{item_id}", status_code=204)
def delete_user(
    item_id: UUID,
    db: Session = Depends(get_db, scope="function"),
    tenant_id: str = Depends(require_tenant),
    ctx: RequestContext = Depends(get_ctx),
):
    item = get_or_404(db, User, item_id, tenant_id, "Usuário")
    soft_delete(item)
    audit(db, tenant_id, "User", item.id, "Deleted", ctx.actor_id)
    return None
