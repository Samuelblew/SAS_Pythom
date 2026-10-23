from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import RequestContext, get_ctx, require_tenant
from app.exceptions import ConflictError, NotFoundError
from app.helpers import audit, by_tenant, get_or_404, paginate, parse_page, soft_delete, utcnow
from app.maps import (
    client_out,
    person_list,
    person_out,
    person_skill_out,
    skill_out,
    unavailability_out,
)
from app.models import Client, Person, PersonSkill, Project, Skill, Unavailability, new_id
from app.schemas import (
    ClientCreate,
    ClientUpdate,
    PersonSkillCreate,
    PersonSkillUpdate,
    PersonWrite,
    SkillCreate,
    UnavailabilityWrite,
    paged,
)

router = APIRouter()


@router.get("/api/v1/skills")
def list_skills(page: int = 1, pageSize: int = 20, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    page, size = parse_page(page, pageSize)
    query = by_tenant(db.query(Skill), Skill, tenant_id).order_by(Skill.name)
    items, total = paginate(query, page, size)
    return paged([skill_out(i) for i in items], page, size, total)


@router.get("/api/v1/skills/{item_id}")
def get_skill(item_id: UUID, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    return skill_out(get_or_404(db, Skill, item_id, tenant_id, "Skill"))


@router.post("/api/v1/skills", status_code=201)
def create_skill(body: SkillCreate, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant), ctx: RequestContext = Depends(get_ctx)):
    name = body.name.strip()
    if by_tenant(db.query(Skill).filter(Skill.name == name), Skill, tenant_id).first():
        raise ConflictError(f"Já existe uma skill com o nome '{name}'.")
    item = Skill(id=new_id(), tenant_id=tenant_id, name=name, category=body.category, created_at=utcnow())
    db.add(item)
    db.flush()
    audit(db, tenant_id, "Skill", item.id, "Created", ctx.actor_id)
    return skill_out(item)


@router.put("/api/v1/skills/{item_id}")
def update_skill(item_id: UUID, body: SkillCreate, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant), ctx: RequestContext = Depends(get_ctx)):
    item = get_or_404(db, Skill, item_id, tenant_id, "Skill")
    name = body.name.strip()
    if by_tenant(db.query(Skill).filter(Skill.name == name, Skill.id != item.id), Skill, tenant_id).first():
        raise ConflictError(f"Já existe uma skill com o nome '{name}'.")
    item.name = name
    item.category = body.category
    item.updated_at = utcnow()
    audit(db, tenant_id, "Skill", item.id, "Updated", ctx.actor_id)
    return skill_out(item)


@router.delete("/api/v1/skills/{item_id}", status_code=204)
def delete_skill(item_id: UUID, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant), ctx: RequestContext = Depends(get_ctx)):
    item = get_or_404(db, Skill, item_id, tenant_id, "Skill")
    soft_delete(item)
    audit(db, tenant_id, "Skill", item.id, "Deleted", ctx.actor_id)


@router.get("/api/v1/clients")
def list_clients(page: int = 1, pageSize: int = 20, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    page, size = parse_page(page, pageSize)
    query = by_tenant(db.query(Client), Client, tenant_id).order_by(Client.name)
    items, total = paginate(query, page, size)
    result = []
    for item in items:
        count = by_tenant(db.query(Project).filter(Project.client_id == item.id), Project, tenant_id).count()
        result.append({"id": item.id, "name": item.name, "projectCount": count, "createdAt": item.created_at})
    return paged(result, page, size, total)


@router.get("/api/v1/clients/{item_id}")
def get_client(item_id: UUID, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    return client_out(get_or_404(db, Client, item_id, tenant_id, "Cliente"))


@router.post("/api/v1/clients", status_code=201)
def create_client(body: ClientCreate, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant), ctx: RequestContext = Depends(get_ctx)):
    name = body.name.strip()
    if by_tenant(db.query(Client).filter(Client.name == name), Client, tenant_id).first():
        raise ConflictError(f"Já existe um cliente com o nome '{name}'.")
    item = Client(id=new_id(), tenant_id=tenant_id, name=name, notes=body.notes, created_at=utcnow())
    db.add(item)
    db.flush()
    audit(db, tenant_id, "Client", item.id, "Created", ctx.actor_id)
    return client_out(item)


@router.put("/api/v1/clients/{item_id}")
def update_client(item_id: UUID, body: ClientUpdate, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant), ctx: RequestContext = Depends(get_ctx)):
    item = get_or_404(db, Client, item_id, tenant_id, "Cliente")
    name = body.name.strip()
    if by_tenant(db.query(Client).filter(Client.name == name, Client.id != item.id), Client, tenant_id).first():
        raise ConflictError(f"Já existe um cliente com o nome '{name}'.")
    item.name = name
    item.notes = body.notes
    item.updated_at = utcnow()
    audit(db, tenant_id, "Client", item.id, "Updated", ctx.actor_id)
    return client_out(item)


@router.delete("/api/v1/clients/{item_id}", status_code=204)
def delete_client(item_id: UUID, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant), ctx: RequestContext = Depends(get_ctx)):
    item = get_or_404(db, Client, item_id, tenant_id, "Cliente")
    soft_delete(item)
    audit(db, tenant_id, "Client", item.id, "Deleted", ctx.actor_id)


def _load_person(db, tenant_id, person_id) -> Person:
    item = (
        by_tenant(db.query(Person), Person, tenant_id)
        .options(joinedload(Person.skills).joinedload(PersonSkill.skill))
        .filter(Person.id == str(person_id))
        .first()
    )
    if not item:
        raise NotFoundError(f"Pessoa '{person_id}' não encontrada.")
    return item


@router.get("/api/v1/people")
def list_people(page: int = 1, pageSize: int = 20, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    page, size = parse_page(page, pageSize)
    query = by_tenant(db.query(Person), Person, tenant_id).options(joinedload(Person.skills)).order_by(Person.name)
    items, total = paginate(query, page, size)
    return paged([person_list(i) for i in items], page, size, total)


@router.get("/api/v1/people/{item_id}")
def get_person(item_id: UUID, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    return person_out(_load_person(db, tenant_id, item_id))


@router.post("/api/v1/people", status_code=201)
def create_person(body: PersonWrite, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant), ctx: RequestContext = Depends(get_ctx)):
    item = Person(
        id=new_id(),
        tenant_id=tenant_id,
        name=body.name.strip(),
        job_title=body.job_title,
        seniority=body.seniority,
        hourly_cost=body.hourly_cost,
        monthly_cost=body.monthly_cost,
        weekly_capacity_hours=body.weekly_capacity_hours,
        location=body.location,
        team=body.team,
        status=body.status,
        created_at=utcnow(),
    )
    db.add(item)
    db.flush()
    audit(db, tenant_id, "Person", item.id, "Created", ctx.actor_id)
    return person_out(_load_person(db, tenant_id, item.id))


@router.put("/api/v1/people/{item_id}")
def update_person(item_id: UUID, body: PersonWrite, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant), ctx: RequestContext = Depends(get_ctx)):
    item = get_or_404(db, Person, item_id, tenant_id, "Pessoa")
    item.name = body.name.strip()
    item.job_title = body.job_title
    item.seniority = body.seniority
    item.hourly_cost = body.hourly_cost
    item.monthly_cost = body.monthly_cost
    item.weekly_capacity_hours = body.weekly_capacity_hours
    item.location = body.location
    item.team = body.team
    item.status = body.status
    item.updated_at = utcnow()
    audit(db, tenant_id, "Person", item.id, "Updated", ctx.actor_id)
    return person_out(_load_person(db, tenant_id, item.id))


@router.delete("/api/v1/people/{item_id}", status_code=204)
def delete_person(item_id: UUID, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant), ctx: RequestContext = Depends(get_ctx)):
    item = get_or_404(db, Person, item_id, tenant_id, "Pessoa")
    for skill in by_tenant(db.query(PersonSkill).filter(PersonSkill.person_id == item.id), PersonSkill, tenant_id).all():
        soft_delete(skill)
    soft_delete(item)
    audit(db, tenant_id, "Person", item.id, "Deleted", ctx.actor_id)


@router.post("/api/v1/people/{person_id}/skills", status_code=201)
def add_person_skill(person_id: UUID, body: PersonSkillCreate, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant), ctx: RequestContext = Depends(get_ctx)):
    person = get_or_404(db, Person, person_id, tenant_id, "Pessoa")
    skill = get_or_404(db, Skill, body.skill_id, tenant_id, "Skill")
    exists = by_tenant(
        db.query(PersonSkill).filter(PersonSkill.person_id == person.id, PersonSkill.skill_id == skill.id),
        PersonSkill,
        tenant_id,
    ).first()
    if exists:
        raise ConflictError("Skill já vinculada a esta pessoa.")
    item = PersonSkill(
        id=new_id(),
        tenant_id=tenant_id,
        person_id=person.id,
        skill_id=skill.id,
        level=body.level,
        last_used_at=body.last_used_at,
        notes=body.notes,
        created_at=utcnow(),
    )
    db.add(item)
    db.flush()
    audit(db, tenant_id, "PersonSkill", item.id, "Created", ctx.actor_id)
    item.skill = skill
    return person_skill_out(item)


@router.put("/api/v1/people/{person_id}/skills/{person_skill_id}")
def update_person_skill(person_id: UUID, person_skill_id: UUID, body: PersonSkillUpdate, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant), ctx: RequestContext = Depends(get_ctx)):
    get_or_404(db, Person, person_id, tenant_id, "Pessoa")
    item = (
        by_tenant(db.query(PersonSkill), PersonSkill, tenant_id)
        .options(joinedload(PersonSkill.skill))
        .filter(PersonSkill.id == str(person_skill_id), PersonSkill.person_id == str(person_id))
        .first()
    )
    if not item:
        raise NotFoundError(f"Skill da pessoa '{person_skill_id}' não encontrada.")
    item.level = body.level
    item.last_used_at = body.last_used_at
    item.notes = body.notes
    item.updated_at = utcnow()
    audit(db, tenant_id, "PersonSkill", item.id, "Updated", ctx.actor_id)
    return person_skill_out(item)


@router.delete("/api/v1/people/{person_id}/skills/{person_skill_id}", status_code=204)
def delete_person_skill(person_id: UUID, person_skill_id: UUID, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant), ctx: RequestContext = Depends(get_ctx)):
    get_or_404(db, Person, person_id, tenant_id, "Pessoa")
    item = by_tenant(
        db.query(PersonSkill).filter(PersonSkill.id == str(person_skill_id), PersonSkill.person_id == str(person_id)),
        PersonSkill,
        tenant_id,
    ).first()
    if not item:
        raise NotFoundError(f"Skill da pessoa '{person_skill_id}' não encontrada.")
    soft_delete(item)
    audit(db, tenant_id, "PersonSkill", item.id, "Deleted", ctx.actor_id)


@router.get("/api/v1/people/{person_id}/unavailabilities")
def list_unavailabilities(person_id: UUID, page: int = 1, pageSize: int = 20, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    get_or_404(db, Person, person_id, tenant_id, "Pessoa")
    page, size = parse_page(page, pageSize)
    query = by_tenant(db.query(Unavailability).filter(Unavailability.person_id == str(person_id)), Unavailability, tenant_id).order_by(Unavailability.start_date.desc())
    items, total = paginate(query, page, size)
    return paged([unavailability_out(i) for i in items], page, size, total)


@router.get("/api/v1/people/{person_id}/unavailabilities/{item_id}")
def get_unavailability(person_id: UUID, item_id: UUID, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    get_or_404(db, Person, person_id, tenant_id, "Pessoa")
    item = by_tenant(
        db.query(Unavailability).filter(Unavailability.id == str(item_id), Unavailability.person_id == str(person_id)),
        Unavailability,
        tenant_id,
    ).first()
    if not item:
        raise NotFoundError(f"Indisponibilidade '{item_id}' não encontrada.")
    return unavailability_out(item)


def _overlap_unavailability(db, tenant_id, person_id, start, end, exclude_id=None):
    query = by_tenant(
        db.query(Unavailability).filter(
            Unavailability.person_id == str(person_id),
            Unavailability.start_date <= end,
            Unavailability.end_date >= start,
        ),
        Unavailability,
        tenant_id,
    )
    if exclude_id:
        query = query.filter(Unavailability.id != str(exclude_id))
    return query.first()


@router.post("/api/v1/people/{person_id}/unavailabilities", status_code=201)
def create_unavailability(person_id: UUID, body: UnavailabilityWrite, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant), ctx: RequestContext = Depends(get_ctx)):
    get_or_404(db, Person, person_id, tenant_id, "Pessoa")
    if _overlap_unavailability(db, tenant_id, person_id, body.start_date, body.end_date):
        raise ConflictError("Já existe indisponibilidade no período informado.")
    item = Unavailability(
        id=new_id(),
        tenant_id=tenant_id,
        person_id=str(person_id),
        start_date=body.start_date,
        end_date=body.end_date,
        type=body.type,
        notes=body.notes,
        created_at=utcnow(),
    )
    db.add(item)
    db.flush()
    audit(db, tenant_id, "Unavailability", item.id, "Created", ctx.actor_id)
    return unavailability_out(item)


@router.put("/api/v1/people/{person_id}/unavailabilities/{item_id}")
def update_unavailability(person_id: UUID, item_id: UUID, body: UnavailabilityWrite, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant), ctx: RequestContext = Depends(get_ctx)):
    get_or_404(db, Person, person_id, tenant_id, "Pessoa")
    item = by_tenant(
        db.query(Unavailability).filter(Unavailability.id == str(item_id), Unavailability.person_id == str(person_id)),
        Unavailability,
        tenant_id,
    ).first()
    if not item:
        raise NotFoundError(f"Indisponibilidade '{item_id}' não encontrada.")
    if _overlap_unavailability(db, tenant_id, person_id, body.start_date, body.end_date, item.id):
        raise ConflictError("Já existe indisponibilidade no período informado.")
    item.start_date = body.start_date
    item.end_date = body.end_date
    item.type = body.type
    item.notes = body.notes
    item.updated_at = utcnow()
    audit(db, tenant_id, "Unavailability", item.id, "Updated", ctx.actor_id)
    return unavailability_out(item)


@router.delete("/api/v1/people/{person_id}/unavailabilities/{item_id}", status_code=204)
def delete_unavailability(person_id: UUID, item_id: UUID, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant), ctx: RequestContext = Depends(get_ctx)):
    get_or_404(db, Person, person_id, tenant_id, "Pessoa")
    item = by_tenant(
        db.query(Unavailability).filter(Unavailability.id == str(item_id), Unavailability.person_id == str(person_id)),
        Unavailability,
        tenant_id,
    ).first()
    if not item:
        raise NotFoundError(f"Indisponibilidade '{item_id}' não encontrada.")
    soft_delete(item)
    audit(db, tenant_id, "Unavailability", item.id, "Deleted", ctx.actor_id)
