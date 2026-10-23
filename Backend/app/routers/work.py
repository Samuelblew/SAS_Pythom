from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import RequestContext, get_ctx, require_tenant
from app.domain import (
    ACTIVE_PROJECTS,
    INACTIVE,
    covered_percent,
    d,
    find_first_overload,
    rank_candidates,
    resolve_need_status,
)
from app.exceptions import ConflictError, NotFoundError
from app.helpers import audit, by_tenant, get_or_404, guid_list, paginate, parse_page, soft_delete, utcnow
from app.maps import allocation_list, allocation_out, need_list, need_out, project_list, project_out, suggestion_out
from app.models import (
    Allocation,
    AllocationNeed,
    Client,
    MatchingSuggestion,
    Person,
    PersonSkill,
    Project,
    Unavailability,
    new_id,
)
from app.schemas import AllocationWrite, NeedWrite, ProjectWrite, SuggestionWrite, paged

router = APIRouter()


def _load_project(db, tenant_id, project_id) -> Project:
    item = (
        by_tenant(db.query(Project), Project, tenant_id)
        .options(joinedload(Project.client))
        .filter(Project.id == str(project_id))
        .first()
    )
    if not item:
        raise NotFoundError(f"Projeto '{project_id}' não encontrado.")
    return item


def _load_need(db, tenant_id, need_id) -> AllocationNeed:
    item = (
        by_tenant(db.query(AllocationNeed), AllocationNeed, tenant_id)
        .options(joinedload(AllocationNeed.project))
        .filter(AllocationNeed.id == str(need_id))
        .first()
    )
    if not item:
        raise NotFoundError(f"Necessidade '{need_id}' não encontrada.")
    return item


def _load_allocation(db, tenant_id, allocation_id) -> Allocation:
    item = (
        by_tenant(db.query(Allocation), Allocation, tenant_id)
        .options(joinedload(Allocation.person), joinedload(Allocation.project))
        .filter(Allocation.id == str(allocation_id))
        .first()
    )
    if not item:
        raise NotFoundError(f"Alocação '{allocation_id}' não encontrada.")
    return item


def sync_need_status(db: Session, tenant_id: str, project_id: str) -> None:
    needs = by_tenant(db.query(AllocationNeed).filter(AllocationNeed.project_id == project_id), AllocationNeed, tenant_id).all()
    allocations = by_tenant(db.query(Allocation).filter(Allocation.project_id == project_id), Allocation, tenant_id).all()
    now = utcnow()
    for need in needs:
        status = resolve_need_status(covered_percent(need, allocations), d(need.dedication_percent))
        if need.status != status:
            need.status = status
            need.updated_at = now


def validate_allocation(db, tenant_id, body: AllocationWrite, exclude_id: str | None = None):
    person = get_or_404(db, Person, body.person_id, tenant_id, "Pessoa")
    if person.status in INACTIVE:
        raise ConflictError("Pessoa inativa não pode receber nova alocação.")
    get_or_404(db, Project, body.project_id, tenant_id, "Projeto")
    overlapping = by_tenant(
        db.query(Allocation)
        .options(joinedload(Allocation.project))
        .filter(
            Allocation.person_id == str(body.person_id),
            Allocation.start_date <= body.end_date,
            Allocation.end_date >= body.start_date,
        ),
        Allocation,
        tenant_id,
    ).all()
    overload = find_first_overload(
        body.start_date,
        body.end_date,
        d(body.dedication_percent),
        overlapping,
        exclude_id,
    )
    if overload:
        existing_summary = ", ".join(
            f"{(a.project.name if a.project else a.project_id)} ({d(a.dedication_percent):g}%)"
            for a in overload["items"]
        )
        raise ConflictError(
            f"RN-001: na semana de {overload['week_start'].strftime('%d/%m/%Y')} a {overload['week_end'].strftime('%d/%m/%Y')}, "
            f"a pessoa já tem {overload['existing']:g}% alocados ({existing_summary}). "
            f"Com mais {overload['requested']:g}%, o total seria {overload['total']:g}%."
        )
    return person


@router.get("/api/v1/projects")
def list_projects(page: int = 1, pageSize: int = 20, clientId: UUID | None = None, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    page, size = parse_page(page, pageSize)
    query = by_tenant(db.query(Project), Project, tenant_id).options(joinedload(Project.client))
    if clientId:
        query = query.filter(Project.client_id == str(clientId))
    query = query.order_by(Project.name)
    items, total = paginate(query, page, size)
    return paged([project_list(i) for i in items], page, size, total)


def understaffed_items(db: Session, tenant_id: str) -> list[dict]:
    projects = by_tenant(db.query(Project).filter(Project.status.in_(ACTIVE_PROJECTS)), Project, tenant_id).order_by(Project.name).all()
    needs = by_tenant(db.query(AllocationNeed), AllocationNeed, tenant_id).all()
    allocations = by_tenant(db.query(Allocation), Allocation, tenant_id).all()
    needs_by = {}
    alloc_by = {}
    for n in needs:
        needs_by.setdefault(n.project_id, []).append(n)
    for a in allocations:
        alloc_by.setdefault(a.project_id, []).append(a)
    summaries = []
    for project in projects:
        project_needs = needs_by.get(project.id, [])
        if not project_needs:
            continue
        project_alloc = alloc_by.get(project.id, [])
        open_needs = 0
        total_gap = Decimal("0")
        for need in project_needs:
            covered = covered_percent(need, project_alloc)
            status = resolve_need_status(covered, d(need.dedication_percent))
            if status != "Filled":
                open_needs += 1
                total_gap += max(Decimal("0"), d(need.dedication_percent) - covered)
        if open_needs > 0:
            summaries.append({
                "projectId": project.id,
                "projectName": project.name,
                "status": project.status,
                "openNeedsCount": open_needs,
                "totalGapPercent": float(total_gap),
            })
    return summaries


@router.get("/api/v1/projects/understaffed")
def projects_understaffed(db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    return {"items": understaffed_items(db, tenant_id)}


@router.get("/api/v1/projects/{item_id}")
def get_project(item_id: UUID, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    return project_out(_load_project(db, tenant_id, item_id))


@router.post("/api/v1/projects", status_code=201)
def create_project(body: ProjectWrite, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant), ctx: RequestContext = Depends(get_ctx)):
    get_or_404(db, Client, body.client_id, tenant_id, "Cliente")
    item = Project(
        id=new_id(),
        tenant_id=tenant_id,
        client_id=str(body.client_id),
        name=body.name.strip(),
        status=body.status,
        start_date=body.start_date,
        end_date=body.end_date,
        priority=body.priority,
        budget=body.budget,
        estimated_revenue=body.estimated_revenue,
        project_type=body.project_type,
        commercial_owner=body.commercial_owner,
        delivery_owner=body.delivery_owner,
        created_at=utcnow(),
    )
    db.add(item)
    db.flush()
    audit(db, tenant_id, "Project", item.id, "Created", ctx.actor_id)
    return project_out(_load_project(db, tenant_id, item.id))


@router.put("/api/v1/projects/{item_id}")
def update_project(item_id: UUID, body: ProjectWrite, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant), ctx: RequestContext = Depends(get_ctx)):
    item = get_or_404(db, Project, item_id, tenant_id, "Projeto")
    get_or_404(db, Client, body.client_id, tenant_id, "Cliente")
    item.client_id = str(body.client_id)
    item.name = body.name.strip()
    item.status = body.status
    item.start_date = body.start_date
    item.end_date = body.end_date
    item.priority = body.priority
    item.budget = body.budget
    item.estimated_revenue = body.estimated_revenue
    item.project_type = body.project_type
    item.commercial_owner = body.commercial_owner
    item.delivery_owner = body.delivery_owner
    item.updated_at = utcnow()
    audit(db, tenant_id, "Project", item.id, "Updated", ctx.actor_id)
    return project_out(_load_project(db, tenant_id, item.id))


@router.delete("/api/v1/projects/{item_id}", status_code=204)
def delete_project(item_id: UUID, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant), ctx: RequestContext = Depends(get_ctx)):
    item = get_or_404(db, Project, item_id, tenant_id, "Projeto")
    soft_delete(item)
    audit(db, tenant_id, "Project", item.id, "Deleted", ctx.actor_id)


@router.get("/api/v1/projects/{item_id}/people")
def project_people(item_id: UUID, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    project = _load_project(db, tenant_id, item_id)
    allocations = (
        by_tenant(db.query(Allocation).filter(Allocation.project_id == project.id), Allocation, tenant_id)
        .options(joinedload(Allocation.person))
        .all()
    )
    by_person: dict[str, list] = {}
    people_map = {}
    for alloc in allocations:
        by_person.setdefault(alloc.person_id, []).append(alloc)
        if alloc.person:
            people_map[alloc.person_id] = alloc.person
    people = []
    for person_id, allocs in by_person.items():
        person = people_map.get(person_id)
        people.append({
            "personId": person_id,
            "personName": person.name if person else "",
            "jobTitle": person.job_title if person else None,
            "status": person.status if person else None,
            "allocations": [
                {
                    "id": a.id,
                    "role": a.role,
                    "dedicationPercent": float(d(a.dedication_percent)),
                    "startDate": a.start_date,
                    "endDate": a.end_date,
                    "status": a.status,
                    "notes": a.notes,
                }
                for a in allocs
            ],
        })
    people.sort(key=lambda p: p["personName"])
    return {"projectId": project.id, "projectName": project.name, "people": people}


@router.get("/api/v1/people/{item_id}/projects")
def person_projects(item_id: UUID, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    person = get_or_404(db, Person, item_id, tenant_id, "Pessoa")
    allocations = (
        by_tenant(db.query(Allocation).filter(Allocation.person_id == person.id), Allocation, tenant_id)
        .options(joinedload(Allocation.project))
        .all()
    )
    by_project: dict[str, list] = {}
    projects_map = {}
    for alloc in allocations:
        by_project.setdefault(alloc.project_id, []).append(alloc)
        if alloc.project:
            projects_map[alloc.project_id] = alloc.project
    projects = []
    for project_id, allocs in by_project.items():
        project = projects_map.get(project_id)
        projects.append({
            "projectId": project_id,
            "projectName": project.name if project else "",
            "projectStatus": project.status if project else None,
            "allocations": [
                {
                    "id": a.id,
                    "role": a.role,
                    "dedicationPercent": float(d(a.dedication_percent)),
                    "startDate": a.start_date,
                    "endDate": a.end_date,
                    "status": a.status,
                    "notes": a.notes,
                }
                for a in allocs
            ],
        })
    return {"personId": person.id, "personName": person.name, "projects": projects}


@router.get("/api/v1/allocation-needs")
def list_needs(page: int = 1, pageSize: int = 20, projectId: UUID | None = None, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    page, size = parse_page(page, pageSize)
    query = by_tenant(db.query(AllocationNeed), AllocationNeed, tenant_id).options(joinedload(AllocationNeed.project))
    if projectId:
        query = query.filter(AllocationNeed.project_id == str(projectId))
    query = query.order_by(AllocationNeed.created_at.desc())
    items, total = paginate(query, page, size)
    return paged([need_list(i) for i in items], page, size, total)


@router.get("/api/v1/allocation-needs/{item_id}")
def get_need(item_id: UUID, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    return need_out(_load_need(db, tenant_id, item_id))


@router.post("/api/v1/allocation-needs", status_code=201)
def create_need(body: NeedWrite, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant), ctx: RequestContext = Depends(get_ctx)):
    get_or_404(db, Project, body.project_id, tenant_id, "Projeto")
    item = AllocationNeed(
        id=new_id(),
        tenant_id=tenant_id,
        project_id=str(body.project_id),
        role=body.role.strip(),
        expected_seniority=body.expected_seniority,
        required_skill_ids=guid_list(body.required_skill_ids),
        desired_skill_ids=guid_list(body.desired_skill_ids),
        dedication_percent=body.dedication_percent,
        start_date=body.start_date,
        end_date=body.end_date,
        urgency=body.urgency,
        criticality=body.criticality,
        status=body.status,
        created_at=utcnow(),
    )
    db.add(item)
    db.flush()
    audit(db, tenant_id, "AllocationNeed", item.id, "Created", ctx.actor_id)
    return need_out(_load_need(db, tenant_id, item.id))


@router.put("/api/v1/allocation-needs/{item_id}")
def update_need(item_id: UUID, body: NeedWrite, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant), ctx: RequestContext = Depends(get_ctx)):
    item = get_or_404(db, AllocationNeed, item_id, tenant_id, "Necessidade")
    get_or_404(db, Project, body.project_id, tenant_id, "Projeto")
    item.project_id = str(body.project_id)
    item.role = body.role.strip()
    item.expected_seniority = body.expected_seniority
    item.required_skill_ids = guid_list(body.required_skill_ids)
    item.desired_skill_ids = guid_list(body.desired_skill_ids)
    item.dedication_percent = body.dedication_percent
    item.start_date = body.start_date
    item.end_date = body.end_date
    item.urgency = body.urgency
    item.criticality = body.criticality
    item.status = body.status
    item.updated_at = utcnow()
    audit(db, tenant_id, "AllocationNeed", item.id, "Updated", ctx.actor_id)
    return need_out(_load_need(db, tenant_id, item.id))


@router.delete("/api/v1/allocation-needs/{item_id}", status_code=204)
def delete_need(item_id: UUID, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant), ctx: RequestContext = Depends(get_ctx)):
    item = get_or_404(db, AllocationNeed, item_id, tenant_id, "Necessidade")
    soft_delete(item)
    audit(db, tenant_id, "AllocationNeed", item.id, "Deleted", ctx.actor_id)


def _candidates_for_need(db, tenant_id, need: AllocationNeed, max_results: int, min_available, exclude_on_project: bool):
    people = (
        by_tenant(db.query(Person).filter(Person.status.in_(["Active", "Contractor"])), Person, tenant_id)
        .options(joinedload(Person.skills).joinedload(PersonSkill.skill))
        .all()
    )
    allocations = by_tenant(db.query(Allocation), Allocation, tenant_id).options(joinedload(Allocation.project)).all()
    unavailabilities = by_tenant(db.query(Unavailability), Unavailability, tenant_id).all()
    period, candidates = rank_candidates(
        need,
        need.project.project_type if need.project else None,
        people,
        allocations,
        unavailabilities,
        max_results,
        min_available,
        exclude_on_project,
    )
    return {
        "allocationNeedId": need.id,
        "projectId": need.project_id,
        "projectName": need.project.name if need.project else "",
        "role": need.role,
        "dedicationPercent": float(d(need.dedication_percent)),
        "periodStart": period[0],
        "periodEnd": period[1],
        "candidates": candidates,
    }


@router.get("/api/v1/allocation-needs/{item_id}/candidates")
def need_candidates(
    item_id: UUID,
    maxResults: int = 20,
    minAvailablePercent: Decimal | None = None,
    excludePeopleOnProject: bool = False,
    db: Session = Depends(get_db, scope="function"),
    tenant_id: str = Depends(require_tenant),
):
    need = _load_need(db, tenant_id, item_id)
    return _candidates_for_need(db, tenant_id, need, maxResults, minAvailablePercent, excludePeopleOnProject)


@router.get("/api/v1/projects/{item_id}/matching-candidates")
def project_matching(
    item_id: UUID,
    maxResultsPerNeed: int = 10,
    minAvailablePercent: Decimal | None = None,
    excludePeopleOnProject: bool = False,
    openNeedsOnly: bool = True,
    db: Session = Depends(get_db, scope="function"),
    tenant_id: str = Depends(require_tenant),
):
    project = _load_project(db, tenant_id, item_id)
    needs = by_tenant(db.query(AllocationNeed).filter(AllocationNeed.project_id == project.id), AllocationNeed, tenant_id).options(joinedload(AllocationNeed.project)).all()
    if openNeedsOnly:
        needs = [n for n in needs if n.status != "Filled"]
    payload = [_candidates_for_need(db, tenant_id, need, maxResultsPerNeed, minAvailablePercent, excludePeopleOnProject) for need in needs]
    return {"projectId": project.id, "projectName": project.name, "needs": payload}


@router.get("/api/v1/allocation-needs/{item_id}/matching-suggestions")
def list_suggestions(item_id: UUID, page: int = 1, pageSize: int = 20, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    _load_need(db, tenant_id, item_id)
    page, size = parse_page(page, pageSize)
    query = (
        by_tenant(db.query(MatchingSuggestion).filter(MatchingSuggestion.allocation_need_id == str(item_id)), MatchingSuggestion, tenant_id)
        .options(joinedload(MatchingSuggestion.need).joinedload(AllocationNeed.project), joinedload(MatchingSuggestion.person))
        .order_by(MatchingSuggestion.created_at.desc())
    )
    items, total = paginate(query, page, size)
    return paged([suggestion_out(i) for i in items], page, size, total)


@router.post("/api/v1/allocation-needs/{item_id}/matching-suggestions", status_code=201)
def create_suggestion(item_id: UUID, body: SuggestionWrite, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant), ctx: RequestContext = Depends(get_ctx)):
    need = _load_need(db, tenant_id, item_id)
    get_or_404(db, Person, body.person_id, tenant_id, "Pessoa")
    item = MatchingSuggestion(
        id=new_id(),
        tenant_id=tenant_id,
        allocation_need_id=need.id,
        person_id=str(body.person_id),
        decision=body.decision,
        score=body.score,
        notes=body.notes,
        decided_by_user_id=ctx.actor_id,
        created_at=utcnow(),
    )
    db.add(item)
    db.flush()
    loaded = (
        by_tenant(db.query(MatchingSuggestion).filter(MatchingSuggestion.id == item.id), MatchingSuggestion, tenant_id)
        .options(joinedload(MatchingSuggestion.need).joinedload(AllocationNeed.project), joinedload(MatchingSuggestion.person))
        .first()
    )
    audit(db, tenant_id, "MatchingSuggestion", item.id, "Created", ctx.actor_id)
    return suggestion_out(loaded)


@router.get("/api/v1/allocations")
def list_allocations(page: int = 1, pageSize: int = 20, personId: UUID | None = None, projectId: UUID | None = None, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    page, size = parse_page(page, pageSize)
    query = by_tenant(db.query(Allocation), Allocation, tenant_id).options(joinedload(Allocation.person), joinedload(Allocation.project))
    if personId:
        query = query.filter(Allocation.person_id == str(personId))
    if projectId:
        query = query.filter(Allocation.project_id == str(projectId))
    query = query.order_by(Allocation.start_date.desc())
    items, total = paginate(query, page, size)
    return paged([allocation_list(i) for i in items], page, size, total)


@router.get("/api/v1/allocations/conflicts")
def list_conflicts(personId: UUID | None = None, projectId: UUID | None = None, from_: date | None = Query(None, alias="from"), to: date | None = None, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    query = by_tenant(db.query(Allocation), Allocation, tenant_id).options(joinedload(Allocation.person), joinedload(Allocation.project))
    if personId:
        query = query.filter(Allocation.person_id == str(personId))
    if projectId:
        query = query.filter(Allocation.project_id == str(projectId))
    allocations = query.all()
    if from_ and to:
        allocations = [a for a in allocations if a.start_date <= to and a.end_date >= from_]
    from app.domain import enumerate_weeks, overlaps
    conflicts = []
    by_person: dict[str, list] = {}
    for a in allocations:
        if a.status == "Closed":
            continue
        by_person.setdefault(a.person_id, []).append(a)
    for person_id, items in by_person.items():
        range_start = min(a.start_date for a in items)
        range_end = max(a.end_date for a in items)
        name = items[0].person.name if items[0].person else ""
        for week_start, week_end in enumerate_weeks(range_start, range_end):
            in_week = [a for a in items if overlaps(a.start_date, a.end_date, week_start, week_end)]
            total = sum((d(a.dedication_percent) for a in in_week), Decimal("0"))
            if total <= 100:
                continue
            conflicts.append({
                "personId": person_id,
                "personName": name,
                "weekStart": week_start,
                "weekEnd": week_end,
                "totalDedicationPercent": float(total),
                "allocations": [
                    {
                        "allocationId": a.id,
                        "projectId": a.project_id,
                        "projectName": a.project.name if a.project else "",
                        "dedicationPercent": float(d(a.dedication_percent)),
                        "startDate": a.start_date,
                        "endDate": a.end_date,
                        "status": a.status,
                    }
                    for a in in_week
                ],
            })
    conflicts.sort(key=lambda c: (c["weekStart"], c["personName"]))
    return {"items": conflicts}


@router.get("/api/v1/allocations/{item_id}")
def get_allocation(item_id: UUID, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    return allocation_out(_load_allocation(db, tenant_id, item_id))


@router.post("/api/v1/allocations", status_code=201)
def create_allocation(body: AllocationWrite, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant), ctx: RequestContext = Depends(get_ctx)):
    validate_allocation(db, tenant_id, body)
    item = Allocation(
        id=new_id(),
        tenant_id=tenant_id,
        person_id=str(body.person_id),
        project_id=str(body.project_id),
        role=body.role.strip(),
        dedication_percent=body.dedication_percent,
        start_date=body.start_date,
        end_date=body.end_date,
        status=body.status,
        notes=body.notes.strip() if body.notes and body.notes.strip() else None,
        created_at=utcnow(),
    )
    db.add(item)
    db.flush()
    sync_need_status(db, tenant_id, item.project_id)
    audit(db, tenant_id, "Allocation", item.id, "Created", ctx.actor_id)
    return allocation_out(_load_allocation(db, tenant_id, item.id))


@router.put("/api/v1/allocations/{item_id}")
def update_allocation(item_id: UUID, body: AllocationWrite, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant), ctx: RequestContext = Depends(get_ctx)):
    item = get_or_404(db, Allocation, item_id, tenant_id, "Alocação")
    previous = item.project_id
    validate_allocation(db, tenant_id, body, item.id)
    item.person_id = str(body.person_id)
    item.project_id = str(body.project_id)
    item.role = body.role.strip()
    item.dedication_percent = body.dedication_percent
    item.start_date = body.start_date
    item.end_date = body.end_date
    item.status = body.status
    item.notes = body.notes.strip() if body.notes and body.notes.strip() else None
    item.updated_at = utcnow()
    sync_need_status(db, tenant_id, item.project_id)
    if previous != item.project_id:
        sync_need_status(db, tenant_id, previous)
    audit(db, tenant_id, "Allocation", item.id, "Updated", ctx.actor_id)
    return allocation_out(_load_allocation(db, tenant_id, item.id))


@router.delete("/api/v1/allocations/{item_id}", status_code=204)
def delete_allocation(item_id: UUID, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant), ctx: RequestContext = Depends(get_ctx)):
    item = get_or_404(db, Allocation, item_id, tenant_id, "Alocação")
    project_id = item.project_id
    soft_delete(item)
    sync_need_status(db, tenant_id, project_id)
    audit(db, tenant_id, "Allocation", item.id, "Deleted", ctx.actor_id)
