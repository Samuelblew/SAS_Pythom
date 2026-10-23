from collections import defaultdict
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import require_tenant
from app.domain import (
    ACTIVE_PEOPLE,
    ACTIVE_PROJECTS,
    FILLED,
    add_months,
    allocation_cost,
    covered_percent,
    d,
    enumerate_weeks,
    person_weeks,
    project_margin,
    r2,
    resolve_need_status,
    resolve_period,
    simulate_feasibility,
    week_hours,
)
from app.exceptions import NotFoundError, ValidationAppError
from app.helpers import by_tenant, get_or_404, paginate, parse_page
from app.models import Allocation, AllocationNeed, AuditLog, Person, PersonSkill, Project, Unavailability
from app.routers.work import understaffed_items, _load_project
from app.schemas import FeasibilityIn, MarginSimIn, paged

router = APIRouter()


def _active_people(db, tenant_id, with_skills=False):
    query = by_tenant(db.query(Person).filter(Person.status.in_(list(ACTIVE_PEOPLE))), Person, tenant_id)
    if with_skills:
        query = query.options(joinedload(Person.skills).joinedload(PersonSkill.skill))
    return query.order_by(Person.name).all()


def _period_data(db, tenant_id, from_date: date, to_date: date, with_skills=False):
    people = _active_people(db, tenant_id, with_skills)
    allocations = (
        by_tenant(
            db.query(Allocation).filter(Allocation.start_date <= to_date, Allocation.end_date >= from_date),
            Allocation,
            tenant_id,
        )
        .options(joinedload(Allocation.project), joinedload(Allocation.person))
        .all()
    )
    unavailabilities = by_tenant(
        db.query(Unavailability).filter(Unavailability.start_date <= to_date, Unavailability.end_date >= from_date),
        Unavailability,
        tenant_id,
    ).all()
    return people, allocations, unavailabilities


def _grouped(items, key):
    grouped: dict = defaultdict(list)
    for item in items:
        grouped[key(item)].append(item)
    return grouped


@router.get("/api/v1/capacity/overview")
def capacity_overview(from_: date = Query(..., alias="from"), to: date = Query(...), benchThreshold: Decimal = Decimal("50"), db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    people, allocations, unavailabilities = _period_data(db, tenant_id, from_, to)
    alloc_by = _grouped(allocations, lambda a: a.person_id)
    unav_by = _grouped(unavailabilities, lambda u: u.person_id)
    availability = {
        p.id: (d(p.weekly_capacity_hours), person_weeks(from_, to, alloc_by.get(p.id, []), unav_by.get(p.id, [])))
        for p in people
    }
    weeks_out = []
    for week_start, week_end in enumerate_weeks(from_, to):
        samples = []
        total_cap = Decimal("0")
        total_alloc_h = Decimal("0")
        total_avail_h = Decimal("0")
        for weekly_hours, weeks in availability.values():
            week = next((w for w in weeks if w.week_start == week_start), None)
            if week is None:
                continue
            samples.append(week)
            total_cap += weekly_hours
            ah, vh = week_hours(week, weekly_hours)
            total_alloc_h += ah
            total_avail_h += vh
        if not samples:
            weeks_out.append({
                "weekStart": week_start, "weekEnd": week_end, "activePeopleCount": 0,
                "avgAllocatedPercent": 0, "avgAvailablePercent": 0, "benchPeopleCount": 0,
                "overallocatedPeopleCount": 0, "totalCapacityHours": 0, "totalAllocatedHours": 0, "totalAvailableHours": 0,
            })
            continue
        weeks_out.append({
            "weekStart": week_start,
            "weekEnd": week_end,
            "activePeopleCount": len(samples),
            "avgAllocatedPercent": float(r2(sum((s.allocated_percent for s in samples), Decimal("0")) / len(samples))),
            "avgAvailablePercent": float(r2(sum((s.available_percent for s in samples), Decimal("0")) / len(samples))),
            "benchPeopleCount": sum(1 for s in samples if s.available_percent >= benchThreshold and not s.is_unavailable),
            "overallocatedPeopleCount": sum(1 for s in samples if s.allocated_percent > 100),
            "totalCapacityHours": float(r2(total_cap)),
            "totalAllocatedHours": float(r2(total_alloc_h)),
            "totalAvailableHours": float(r2(total_avail_h)),
        })
    teams = []
    for team, group in _grouped(people, lambda p: p.team).items():
        allocated_samples = []
        available_samples = []
        for person in group:
            weeks = person_weeks(from_, to, alloc_by.get(person.id, []), unav_by.get(person.id, []))
            allocated_samples.extend(w.allocated_percent for w in weeks)
            available_samples.extend(w.available_percent for w in weeks)
        teams.append({
            "team": team,
            "peopleCount": len(group),
            "avgAllocatedPercent": float(r2(sum(allocated_samples, Decimal("0")) / len(allocated_samples))) if allocated_samples else 0,
            "avgAvailablePercent": float(r2(sum(available_samples, Decimal("0")) / len(available_samples))) if available_samples else 0,
        })
    teams.sort(key=lambda t: t["team"] or "")
    return {"from": from_, "to": to, "weeks": weeks_out, "teams": teams}


@router.get("/api/v1/capacity/people/{person_id}/availability")
def person_availability(person_id: UUID, from_: date = Query(..., alias="from"), to: date = Query(...), db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    person = get_or_404(db, Person, person_id, tenant_id, "Pessoa")
    allocations = by_tenant(
        db.query(Allocation).filter(Allocation.person_id == person.id, Allocation.start_date <= to, Allocation.end_date >= from_),
        Allocation,
        tenant_id,
    ).all()
    unavailabilities = by_tenant(
        db.query(Unavailability).filter(Unavailability.person_id == person.id, Unavailability.start_date <= to, Unavailability.end_date >= from_),
        Unavailability,
        tenant_id,
    ).all()
    weeks = person_weeks(from_, to, allocations, unavailabilities)
    weekly = d(person.weekly_capacity_hours)
    return {
        "personId": person.id,
        "personName": person.name,
        "weeklyCapacityHours": float(weekly),
        "from": from_,
        "to": to,
        "weeks": [
            {
                "weekStart": w.week_start,
                "weekEnd": w.week_end,
                "allocatedPercent": float(w.allocated_percent),
                "availablePercent": float(w.available_percent),
                "weeklyCapacityHours": float(weekly),
                "allocatedHours": float(week_hours(w, weekly)[0]),
                "availableHours": float(week_hours(w, weekly)[1]),
                "isUnavailable": w.is_unavailable,
            }
            for w in weeks
        ],
    }


@router.get("/api/v1/capacity/projects/{project_id}/staffing-gaps")
def staffing_gaps(project_id: UUID, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    project = _load_project(db, tenant_id, project_id)
    needs = by_tenant(db.query(AllocationNeed).filter(AllocationNeed.project_id == project.id), AllocationNeed, tenant_id).order_by(AllocationNeed.role).all()
    allocations = by_tenant(db.query(Allocation).filter(Allocation.project_id == project.id), Allocation, tenant_id).all()
    items = []
    for need in needs:
        covered = covered_percent(need, allocations)
        status = resolve_need_status(covered, d(need.dedication_percent))
        items.append({
            "needId": need.id,
            "role": need.role,
            "requiredPercent": float(d(need.dedication_percent)),
            "coveredPercent": float(covered),
            "gapPercent": float(max(Decimal("0"), d(need.dedication_percent) - covered)),
            "status": status,
        })
    return {"projectId": project.id, "projectName": project.name, "needs": items}


@router.get("/api/v1/capacity/people-available")
def people_available(from_: date = Query(..., alias="from"), to: date = Query(...), minAvailablePercent: Decimal = Decimal("1"), db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    people, allocations, unavailabilities = _period_data(db, tenant_id, from_, to)
    alloc_by = _grouped(allocations, lambda a: a.person_id)
    unav_by = _grouped(unavailabilities, lambda u: u.person_id)
    results = []
    for person in people:
        weeks = person_weeks(from_, to, alloc_by.get(person.id, []), unav_by.get(person.id, []))
        if not weeks:
            continue
        min_av = min(w.available_percent for w in weeks)
        if min_av < minAvailablePercent:
            continue
        results.append({
            "personId": person.id,
            "personName": person.name,
            "minAvailablePercentInPeriod": float(min_av),
            "avgAvailablePercent": float(r2(sum((w.available_percent for w in weeks), Decimal("0")) / len(weeks))),
        })
    results.sort(key=lambda p: -p["minAvailablePercentInPeriod"])
    return {"from": from_, "to": to, "people": results}


@router.get("/api/v1/capacity/bench")
def capacity_bench(from_: date = Query(..., alias="from"), to: date = Query(...), minAvailablePercent: Decimal = Decimal("50"), db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    people, allocations, unavailabilities = _period_data(db, tenant_id, from_, to)
    alloc_by = _grouped(allocations, lambda a: a.person_id)
    unav_by = _grouped(unavailabilities, lambda u: u.person_id)
    results = []
    for person in people:
        weeks = person_weeks(from_, to, alloc_by.get(person.id, []), unav_by.get(person.id, []))
        if not weeks:
            continue
        min_av = min(w.available_percent for w in weeks)
        if min_av < minAvailablePercent:
            continue
        results.append({
            "personId": person.id,
            "personName": person.name,
            "team": person.team,
            "seniority": person.seniority,
            "minAvailablePercentInPeriod": float(min_av),
            "avgAvailablePercent": float(r2(sum((w.available_percent for w in weeks), Decimal("0")) / len(weeks))),
        })
    results.sort(key=lambda p: -p["avgAvailablePercent"])
    return {"from": from_, "to": to, "minAvailablePercent": float(minAvailablePercent), "people": results}


@router.get("/api/v1/capacity/future-gaps")
def future_gaps(from_: date = Query(..., alias="from"), to: date = Query(...), db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    people, allocations, unavailabilities = _period_data(db, tenant_id, from_, to)
    needs = (
        by_tenant(db.query(AllocationNeed), AllocationNeed, tenant_id)
        .options(joinedload(AllocationNeed.project))
        .all()
    )
    needs = [n for n in needs if n.project and n.project.status in ACTIVE_PROJECTS]
    all_alloc = by_tenant(db.query(Allocation), Allocation, tenant_id).all()
    alloc_by_project = _grouped(all_alloc, lambda a: a.project_id)
    open_needs = []
    for need in needs:
        covered = covered_percent(need, alloc_by_project.get(need.project_id, []))
        status = resolve_need_status(covered, d(need.dedication_percent))
        if status == FILLED:
            continue
        gap = max(Decimal("0"), d(need.dedication_percent) - covered)
        open_needs.append({
            "needId": need.id,
            "projectId": need.project_id,
            "projectName": need.project.name if need.project else "",
            "role": need.role,
            "requiredPercent": float(d(need.dedication_percent)),
            "coveredPercent": float(covered),
            "gapPercent": float(gap),
            "status": status,
            "startDate": need.start_date,
            "endDate": need.end_date,
            "_gap": gap,
            "_start": need.start_date,
            "_end": need.end_date,
        })
    alloc_by = _grouped(allocations, lambda a: a.person_id)
    unav_by = _grouped(unavailabilities, lambda u: u.person_id)
    availability = {p.id: person_weeks(from_, to, alloc_by.get(p.id, []), unav_by.get(p.id, [])) for p in people}
    weeks_out = []
    peak = Decimal("0")

    def overlaps_week(n_start, n_end, week_start, week_end):
        if n_start is None and n_end is None:
            return True
        range_start = n_start or date.min
        range_end = n_end or date.max
        return range_start <= week_end and range_end >= week_start

    for week_start, week_end in enumerate_weeks(from_, to):
        demand = sum((n["_gap"] for n in open_needs if overlaps_week(n["_start"], n["_end"], week_start, week_end)), Decimal("0"))
        supply = Decimal("0")
        for weeks in availability.values():
            week = next((w for w in weeks if w.week_start == week_start), None)
            if week:
                supply += week.available_percent
        shortfall = max(Decimal("0"), demand - supply)
        peak = max(peak, shortfall)
        weeks_out.append({
            "weekStart": week_start,
            "weekEnd": week_end,
            "totalGapDemandPercent": float(r2(demand)),
            "totalAvailableSupplyPercent": float(r2(supply)),
            "netShortfallPercent": float(r2(shortfall)),
            "openNeedsInWeek": sum(1 for n in open_needs if overlaps_week(n["_start"], n["_end"], week_start, week_end)),
        })
    open_needs.sort(key=lambda n: (-n["_gap"], n["projectName"]))
    for n in open_needs:
        n.pop("_gap", None)
        n.pop("_start", None)
        n.pop("_end", None)
    return {"from": from_, "to": to, "peakShortfallPercent": float(r2(peak)), "weeks": weeks_out, "openNeeds": open_needs}


@router.get("/api/v1/capacity/skills-occupation")
def skills_occupation(from_: date = Query(..., alias="from"), to: date = Query(...), db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    people, allocations, unavailabilities = _period_data(db, tenant_id, from_, to, with_skills=True)
    alloc_by = _grouped(allocations, lambda a: a.person_id)
    unav_by = _grouped(unavailabilities, lambda u: u.person_id)
    skill_people: dict[str, list] = defaultdict(list)
    for person in people:
        skills = [s for s in person.skills if s.deleted_at is None]
        if not skills:
            continue
        weeks = person_weeks(from_, to, alloc_by.get(person.id, []), unav_by.get(person.id, []))
        for person_skill in skills:
            skill_people[person_skill.skill_id].append((person_skill, weeks, d(person.weekly_capacity_hours)))
    skills_out = []
    for skill_id, entries in skill_people.items():
        first = entries[0][0]
        allocated_p, available_p, allocated_h, available_h = [], [], [], []
        for _, weeks, weekly in entries:
            allocated_p.extend(w.allocated_percent for w in weeks)
            available_p.extend(w.available_percent for w in weeks)
            for week in weeks:
                ah, vh = week_hours(week, weekly)
                allocated_h.append(ah)
                available_h.append(vh)
        skills_out.append({
            "skillId": skill_id,
            "skillName": first.skill.name if first.skill else "",
            "category": first.skill.category if first.skill else None,
            "peopleCount": len(entries),
            "avgAllocatedPercent": float(r2(sum(allocated_p, Decimal("0")) / len(allocated_p))) if allocated_p else 0,
            "avgAvailablePercent": float(r2(sum(available_p, Decimal("0")) / len(available_p))) if available_p else 0,
            "avgAllocatedHours": float(r2(sum(allocated_h, Decimal("0")) / len(allocated_h))) if allocated_h else 0,
            "avgAvailableHours": float(r2(sum(available_h, Decimal("0")) / len(available_h))) if available_h else 0,
        })
    skills_out.sort(key=lambda s: s["skillName"])
    return {"from": from_, "to": to, "skills": skills_out}


@router.get("/api/v1/capacity/projects-understaffed")
def capacity_understaffed(db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    return {"items": understaffed_items(db, tenant_id)}


def _project_financials(project, allocations, from_date, to_date, threshold: Decimal):
    period_start, period_end = resolve_period(project, allocations, from_date, to_date)
    costs = [allocation_cost(a, a.person, period_start, period_end) for a in allocations if a.person]
    margin = project_margin(project, costs, threshold)
    return period_start, period_end, costs, margin


@router.get("/api/v1/projects/{item_id}/financials")
def project_financials(item_id: UUID, from_: date | None = Query(None, alias="from"), to: date | None = None, marginAlertThreshold: Decimal = Decimal("15"), db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    project = _load_project(db, tenant_id, item_id)
    allocations = (
        by_tenant(db.query(Allocation).filter(Allocation.project_id == project.id), Allocation, tenant_id)
        .options(joinedload(Allocation.person))
        .all()
    )
    period_start, period_end, costs, margin = _project_financials(project, allocations, from_, to, marginAlertThreshold)
    return {
        "projectId": project.id,
        "projectName": project.name,
        "clientId": project.client_id,
        "clientName": project.client.name if project.client else "",
        "status": project.status,
        "periodStart": period_start,
        "periodEnd": period_end,
        "estimatedRevenue": margin["estimatedRevenue"],
        "budget": margin["budget"],
        "totalCost": margin["totalCost"],
        "marginAmount": margin["marginAmount"],
        "marginPercent": margin["marginPercent"],
        "hasRevenueData": margin["hasRevenueData"],
        "hasCostData": margin["hasCostData"],
        "isLowMarginAlert": margin["isLowMarginAlert"],
        "marginAlertThresholdPercent": float(marginAlertThreshold),
        "allocations": costs,
    }


def _financial_summaries(db, tenant_id, from_date, to_date, threshold: Decimal):
    projects = (
        by_tenant(db.query(Project).filter(Project.status.in_(list(ACTIVE_PROJECTS))), Project, tenant_id)
        .options(joinedload(Project.client))
        .order_by(Project.name)
        .all()
    )
    ids = [p.id for p in projects]
    allocations = []
    if ids:
        allocations = (
            by_tenant(db.query(Allocation).filter(Allocation.project_id.in_(ids)), Allocation, tenant_id)
            .options(joinedload(Allocation.person))
            .all()
        )
    alloc_by = _grouped(allocations, lambda a: a.project_id)
    global_from, global_to = from_date, to_date
    if global_from is None or global_to is None:
        default_from = global_from or (min(a.start_date for a in allocations) if allocations else date.today())
        default_to = global_to or (max(a.end_date for a in allocations) if allocations else add_months(default_from, 3))
        if default_to < default_from:
            default_to = add_months(default_from, 3)
        global_from, global_to = default_from, default_to
    summaries = []
    for project in projects:
        project_alloc = alloc_by.get(project.id, [])
        period_start, period_end, costs, margin = _project_financials(project, project_alloc, global_from, global_to, threshold)
        summaries.append({
            "project": project,
            "periodStart": period_start,
            "periodEnd": period_end,
            "margin": margin,
            "projectType": project.project_type,
        })
    return global_from, global_to, summaries


@router.get("/api/v1/financials/overview")
def financial_overview(from_: date | None = Query(None, alias="from"), to: date | None = None, marginAlertThreshold: Decimal = Decimal("15"), db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    period_start, period_end, summaries = _financial_summaries(db, tenant_id, from_, to, marginAlertThreshold)
    projects = []
    for item in summaries:
        project = item["project"]
        margin = item["margin"]
        projects.append({
            "projectId": project.id,
            "projectName": project.name,
            "clientName": project.client.name if project.client else "",
            "status": project.status,
            "estimatedRevenue": margin["estimatedRevenue"],
            "totalCost": margin["totalCost"],
            "marginAmount": margin["marginAmount"],
            "marginPercent": margin["marginPercent"],
            "isLowMarginAlert": margin["isLowMarginAlert"],
        })
    projects.sort(key=lambda s: (-int(s["isLowMarginAlert"]), s["marginPercent"] if s["marginPercent"] is not None else 9999, s["projectName"]))
    alerts = [
        {
            "projectId": s["projectId"],
            "projectName": s["projectName"],
            "clientName": s["clientName"],
            "marginPercent": s["marginPercent"],
            "totalCost": s["totalCost"],
            "estimatedRevenue": s["estimatedRevenue"],
        }
        for s in projects if s["isLowMarginAlert"]
    ]
    alerts.sort(key=lambda a: (a["marginPercent"] if a["marginPercent"] is not None else 0, a["projectName"]))
    with_rev = [s for s in projects if s["estimatedRevenue"] is not None]
    total_cost = r2(sum((d(s["totalCost"]) for s in projects), Decimal("0")))
    total_revenue = sum((d(s["estimatedRevenue"]) for s in with_rev), Decimal("0")) if with_rev else None
    total_margin = r2(total_revenue - total_cost) if total_revenue is not None else None
    avg = r2(total_margin / total_revenue * Decimal("100")) if total_revenue and total_revenue > 0 and total_margin is not None else None
    return {
        "periodStart": period_start,
        "periodEnd": period_end,
        "marginAlertThresholdPercent": float(marginAlertThreshold),
        "totalCost": float(total_cost),
        "totalRevenue": float(total_revenue) if total_revenue is not None and with_rev else None,
        "totalMargin": float(total_margin) if total_margin is not None and with_rev else None,
        "avgMarginPercent": float(avg) if avg is not None else None,
        "projects": projects,
        "lowMarginAlerts": alerts,
    }


@router.get("/api/v1/financials/profitability")
def profitability(from_: date | None = Query(None, alias="from"), to: date | None = None, groupBy: str = "Client", marginAlertThreshold: Decimal = Decimal("15"), db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    period_start, period_end, summaries = _financial_summaries(db, tenant_id, from_, to, marginAlertThreshold)
    groups_map: dict = defaultdict(list)
    for item in summaries:
        project = item["project"]
        if groupBy == "ProjectType":
            key = (project.project_type.strip() if project.project_type and project.project_type.strip() else "Sem tipo", None)
        else:
            key = (project.client.name if project.client else "", project.client_id)
        groups_map[key].append(item)
    groups = []
    for (group_key, client_id), items in groups_map.items():
        total_cost = r2(sum((d(i["margin"]["totalCost"]) for i in items), Decimal("0")))
        with_rev = [i for i in items if i["margin"]["estimatedRevenue"] is not None]
        total_revenue = sum((d(i["margin"]["estimatedRevenue"]) for i in with_rev), Decimal("0")) if with_rev else None
        total_margin = r2(total_revenue - total_cost) if total_revenue is not None else None
        margin_percent = r2(total_margin / total_revenue * Decimal("100")) if total_revenue and total_revenue > 0 and total_margin is not None else None
        groups.append({
            "groupKey": group_key,
            "clientId": client_id,
            "projectCount": len(items),
            "totalCost": float(total_cost),
            "totalRevenue": float(total_revenue) if total_revenue is not None else None,
            "totalMargin": float(total_margin) if total_margin is not None else None,
            "marginPercent": float(margin_percent) if margin_percent is not None else None,
            "isLowMarginAlert": margin_percent is not None and margin_percent < marginAlertThreshold,
        })
    groups.sort(key=lambda g: (-int(g["isLowMarginAlert"]), g["marginPercent"] if g["marginPercent"] is not None else 9999, g["groupKey"]))
    return {
        "periodStart": period_start,
        "periodEnd": period_end,
        "groupBy": groupBy,
        "marginAlertThresholdPercent": float(marginAlertThreshold),
        "groups": groups,
    }


@router.get("/api/v1/financials/bench")
def financial_bench(from_: date = Query(..., alias="from"), to: date = Query(...), minAvailablePercent: Decimal = Decimal("50"), db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    from app.domain import hourly_rate
    people, allocations, unavailabilities = _period_data(db, tenant_id, from_, to)
    alloc_by = _grouped(allocations, lambda a: a.person_id)
    unav_by = _grouped(unavailabilities, lambda u: u.person_id)
    results = []
    for person in people:
        weeks = person_weeks(from_, to, alloc_by.get(person.id, []), unav_by.get(person.id, []))
        if not weeks:
            continue
        min_av = min(w.available_percent for w in weeks)
        if min_av < minAvailablePercent:
            continue
        rate = hourly_rate(person)
        bench_hours = Decimal("0")
        bench_cost = Decimal("0")
        for week in weeks:
            hours = d(person.weekly_capacity_hours) * (week.available_percent / Decimal("100"))
            bench_hours += hours
            if rate is not None:
                bench_cost += hours * rate
        results.append({
            "personId": person.id,
            "personName": person.name,
            "team": person.team,
            "minAvailablePercent": float(min_av),
            "avgAvailablePercent": float(r2(sum((w.available_percent for w in weeks), Decimal("0")) / len(weeks))),
            "benchHours": float(r2(bench_hours)),
            "benchCost": float(r2(bench_cost)),
            "hasCostData": rate is not None,
        })
    results.sort(key=lambda p: (-p["benchCost"], p["personName"]))
    return {
        "from": from_,
        "to": to,
        "minAvailablePercent": float(minAvailablePercent),
        "totalBenchHours": float(r2(sum((d(p["benchHours"]) for p in results), Decimal("0")))),
        "totalBenchCost": float(r2(sum((d(p["benchCost"]) for p in results), Decimal("0")))),
        "people": results,
    }


@router.post("/api/v1/simulations/project-feasibility")
def project_feasibility(body: FeasibilityIn, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    if body.duration_months < 1 or body.duration_months > 36:
        raise ValidationAppError("durationMonths deve estar entre 1 e 36")
    people, allocations, unavailabilities = _period_data(
        db,
        tenant_id,
        body.desired_start_date,
        add_months(body.desired_start_date, body.duration_months + 6),
        with_skills=True,
    )
    people = _active_people(db, tenant_id, with_skills=True)
    allocations = by_tenant(db.query(Allocation), Allocation, tenant_id).all()
    unavailabilities = by_tenant(db.query(Unavailability), Unavailability, tenant_id).all()
    return simulate_feasibility(body.desired_start_date, body.duration_months, body.needs, people, allocations, unavailabilities)


@router.post("/api/v1/simulations/allocation-margin")
def allocation_margin(body: MarginSimIn, db: Session = Depends(get_db, scope="function"), tenant_id: str = Depends(require_tenant)):
    project = _load_project(db, tenant_id, body.project_id)
    person = get_or_404(db, Person, body.person_id, tenant_id, "Pessoa")
    allocations = (
        by_tenant(db.query(Allocation).filter(Allocation.project_id == project.id), Allocation, tenant_id)
        .options(joinedload(Allocation.person))
        .all()
    )
    period_start, period_end = resolve_period(project, allocations, body.start_date, body.end_date)
    existing_costs = [allocation_cost(a, a.person, period_start, period_end) for a in allocations if a.person]
    simulated = type("Alloc", (), {
        "id": "00000000-0000-0000-0000-000000000000",
        "person_id": person.id,
        "project_id": project.id,
        "role": body.role,
        "dedication_percent": body.dedication_percent,
        "start_date": body.start_date,
        "end_date": body.end_date,
        "status": "Planned",
    })()
    additional = allocation_cost(simulated, person, period_start, period_end)
    current = project_margin(project, existing_costs, body.margin_alert_threshold_percent)
    projected = project_margin(project, existing_costs + [additional], body.margin_alert_threshold_percent)
    current_margin = d(current["marginAmount"] or 0)
    projected_margin = d(projected["marginAmount"] or 0)
    delta_amount = r2(projected_margin - current_margin)
    delta_percent = None
    if current["marginPercent"] is not None and projected["marginPercent"] is not None:
        delta_percent = float(r2(d(projected["marginPercent"]) - d(current["marginPercent"])))
    return {
        "projectId": project.id,
        "projectName": project.name,
        "periodStart": period_start,
        "periodEnd": period_end,
        "currentTotalCost": current["totalCost"],
        "currentMarginAmount": current["marginAmount"],
        "currentMarginPercent": current["marginPercent"],
        "simulatedAdditionalCost": additional["totalCost"],
        "projectedTotalCost": projected["totalCost"],
        "projectedMarginAmount": projected["marginAmount"],
        "projectedMarginPercent": projected["marginPercent"],
        "marginDeltaAmount": float(delta_amount),
        "marginDeltaPercent": delta_percent,
        "hasRevenueData": current["hasRevenueData"],
        "currentIsLowMarginAlert": current["isLowMarginAlert"],
        "projectedIsLowMarginAlert": projected["isLowMarginAlert"],
        "marginAlertThresholdPercent": float(body.margin_alert_threshold_percent),
    }


@router.get("/api/v1/audit-logs")
def audit_logs(
    page: int = 1,
    pageSize: int = 20,
    entityType: str | None = None,
    entityId: UUID | None = None,
    action: str | None = None,
    from_: date | None = Query(None, alias="from"),
    to: date | None = None,
    db: Session = Depends(get_db, scope="function"),
    tenant_id: str = Depends(require_tenant),
):
    page, size = parse_page(page, pageSize)
    query = db.query(AuditLog).filter(AuditLog.tenant_id == tenant_id)
    if entityType:
        query = query.filter(AuditLog.entity_type == entityType)
    if entityId:
        query = query.filter(AuditLog.entity_id == str(entityId))
    if action:
        query = query.filter(AuditLog.action == action)
    if from_:
        query = query.filter(AuditLog.occurred_at >= from_)
    if to:
        from datetime import datetime, time
        query = query.filter(AuditLog.occurred_at <= datetime.combine(to, time.max))
    query = query.order_by(AuditLog.occurred_at.desc())
    items, total = paginate(query, page, size)
    import json
    mapped = []
    for i in items:
        changes = i.changes_json
        if changes is not None and not isinstance(changes, str):
            changes = json.dumps(changes)
        mapped.append({
            "id": i.id,
            "entityType": i.entity_type,
            "entityId": i.entity_id,
            "action": i.action,
            "actorId": i.actor_id,
            "summary": i.summary,
            "changesJson": changes,
            "occurredAt": i.occurred_at,
        })
    return paged(mapped, page, size, total)
