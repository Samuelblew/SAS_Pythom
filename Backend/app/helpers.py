from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.exceptions import NotFoundError, ValidationAppError
from app.models import AuditLog, new_id


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def parse_page(page: int, page_size: int) -> tuple[int, int]:
    if page < 1:
        raise ValidationAppError("page deve ser >= 1")
    if page_size < 1 or page_size > 100:
        raise ValidationAppError("pageSize deve estar entre 1 e 100")
    return page, page_size


def alive(query, model):
    return query.filter(model.deleted_at.is_(None))


def by_tenant(query, model, tenant_id: str):
    return alive(query.filter(model.tenant_id == tenant_id), model)


def get_or_404(db: Session, model, item_id: UUID | str, tenant_id: str | None, label: str):
    q = db.query(model).filter(model.id == str(item_id))
    if tenant_id is not None and hasattr(model, "tenant_id"):
        q = q.filter(model.tenant_id == tenant_id)
    if hasattr(model, "deleted_at"):
        q = q.filter(model.deleted_at.is_(None))
    entity = q.first()
    if entity is None:
        raise NotFoundError(f"{label} '{item_id}' não encontrado.")
    return entity


def paginate(query, page: int, page_size: int):
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return items, total


def audit(db: Session, tenant_id: str, entity_type: str, entity_id: str, action: str, actor_id: str | None, changes: Any = None):
    payload = None
    if changes is not None:
        payload = changes if isinstance(changes, (dict, list)) else json.loads(json.dumps(changes, default=str))
    db.add(
        AuditLog(
            id=new_id(),
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor_id=actor_id,
            summary=f"{action} {entity_type} {entity_id}",
            changes_json=payload,
            occurred_at=utcnow(),
        )
    )


def guid_list(raw) -> list[str]:
    if not raw:
        return []
    return [str(item) for item in raw]


def as_uuid_list(raw) -> list[UUID]:
    return [UUID(str(item)) for item in (raw or [])]


def money(value) -> float | None:
    if value is None:
        return None
    return float(Decimal(str(value)))


def soft_delete(entity) -> None:
    now = utcnow()
    entity.deleted_at = now
    entity.updated_at = now
