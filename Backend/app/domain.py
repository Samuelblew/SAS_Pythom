from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

CLOSED = "Closed"
FILLED = "Filled"
PARTIALLY = "PartiallyFilled"
OPEN = "Open"
INACTIVE = {"Offboarded", "NoticePeriod"}
ACTIVE_PEOPLE = {"Active", "Contractor"}
ACTIVE_PROJECTS = {"Proposal", "Approved", "InProgress", "Paused"}

MAX_AVAILABILITY = Decimal("25")
MAX_REQUIRED = Decimal("25")
MAX_DESIRED = Decimal("10")
MAX_SENIORITY = Decimal("15")
MAX_HISTORY = Decimal("10")
MAX_COST = Decimal("10")
MAX_OVERLOAD = Decimal("20")
MAX_SWITCHING = Decimal("10")
MONTHLY_HOURS = Decimal("160")


def d(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def r2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def start_of_week(day: date) -> date:
    return day - timedelta(days=day.weekday())  # Monday=0


def enumerate_weeks(start: date, end: date) -> list[tuple[date, date]]:
    cursor = start_of_week(start)
    last = start_of_week(end)
    weeks: list[tuple[date, date]] = []
    while cursor <= last:
        weeks.append((cursor, cursor + timedelta(days=6)))
        cursor += timedelta(days=7)
    return weeks


def overlaps(a_start: date, a_end: date, b_start: date, b_end: date) -> bool:
    return a_start <= b_end and a_end >= b_start


def overlaps_optional(a_start: date, a_end: date, n_start: date | None, n_end: date | None) -> bool:
    if n_start is None and n_end is None:
        return True
    range_start = n_start or date.min
    range_end = n_end or date.max
    return a_start <= range_end and a_end >= range_start


def roles_match(a: str, b: str) -> bool:
    return a.strip().lower() == b.strip().lower()


def covered_percent(need, allocations) -> Decimal:
    total = Decimal("0")
    for alloc in allocations:
        if alloc.project_id != need.project_id:
            continue
        if alloc.status == CLOSED:
            continue
        if not roles_match(alloc.role, need.role):
            continue
        if not overlaps_optional(alloc.start_date, alloc.end_date, need.start_date, need.end_date):
            continue
        total += d(alloc.dedication_percent)
    return total


def resolve_need_status(covered: Decimal, required: Decimal) -> str:
    if covered >= required:
        return FILLED
    if covered > 0:
        return PARTIALLY
    return OPEN


@dataclass
class WeekAvailability:
    week_start: date
    week_end: date
    allocated_percent: Decimal
    available_percent: Decimal
    is_unavailable: bool


def person_weeks(from_date: date, to_date: date, allocations, unavailabilities) -> list[WeekAvailability]:
    active = [a for a in allocations if a.status != CLOSED]
    result: list[WeekAvailability] = []
    for week_start, week_end in enumerate_weeks(from_date, to_date):
        allocated = sum(
            (d(a.dedication_percent) for a in active if a.start_date <= week_end and a.end_date >= week_start),
            Decimal("0"),
        )
        unavailable = any(u.start_date <= week_end and u.end_date >= week_start for u in unavailabilities)
        available = Decimal("0") if unavailable else max(Decimal("0"), Decimal("100") - allocated)
        result.append(WeekAvailability(week_start, week_end, allocated, available, unavailable))
    return result


def week_hours(week: WeekAvailability, weekly_capacity: Decimal) -> tuple[Decimal, Decimal]:
    allocated_hours = r2(weekly_capacity * week.allocated_percent / Decimal("100"))
    available_hours = Decimal("0") if week.is_unavailable else r2(weekly_capacity * week.available_percent / Decimal("100"))
    return allocated_hours, available_hours


def find_first_overload(start: date, end: date, dedication: Decimal, existing, exclude_id: str | None = None):
    for week_start, week_end in enumerate_weeks(start, end):
        in_week = []
        for allocation in existing:
            if exclude_id and allocation.id == exclude_id:
                continue
            if allocation.status == CLOSED:
                continue
            if overlaps(allocation.start_date, allocation.end_date, week_start, week_end):
                in_week.append(allocation)
        existing_total = sum((d(a.dedication_percent) for a in in_week), Decimal("0"))
        total = dedication + existing_total
        if total <= 100:
            continue
        return {
            "week_start": week_start,
            "week_end": week_end,
            "requested": dedication,
            "existing": existing_total,
            "total": total,
            "items": in_week,
        }
    return None


def hourly_rate(person) -> Decimal | None:
    if person.hourly_cost is not None:
        return d(person.hourly_cost)
    if person.monthly_cost is not None:
        return d(person.monthly_cost) / MONTHLY_HOURS
    return None


def allocation_cost(allocation, person, from_date: date, to_date: date) -> dict:
    rate = hourly_rate(person)
    empty = {
        "allocationId": allocation.id,
        "personId": person.id,
        "personName": person.name,
        "role": allocation.role,
        "dedicationPercent": float(d(allocation.dedication_percent)),
        "allocationStart": allocation.start_date,
        "allocationEnd": allocation.end_date,
        "hourlyRate": float(rate) if rate is not None else None,
        "weeksInPeriod": 0,
        "totalHours": 0.0,
        "totalCost": 0.0,
        "hasCostData": rate is not None,
    }
    if allocation.status == CLOSED:
        return empty
    period_start = max(allocation.start_date, from_date)
    period_end = min(allocation.end_date, to_date)
    if period_end < period_start:
        return empty
    total_hours = Decimal("0")
    total_cost = Decimal("0")
    weeks = 0
    for week_start, week_end in enumerate_weeks(period_start, period_end):
        if not overlaps(allocation.start_date, allocation.end_date, week_start, week_end):
            continue
        weeks += 1
        hours = d(person.weekly_capacity_hours) * (d(allocation.dedication_percent) / Decimal("100"))
        total_hours += hours
        if rate is not None:
            total_cost += hours * rate
    empty["weeksInPeriod"] = weeks
    empty["totalHours"] = float(r2(total_hours))
    empty["totalCost"] = float(r2(total_cost))
    return empty


def project_margin(project, costs: list[dict], threshold: Decimal) -> dict:
    revenue = project.estimated_revenue if project.estimated_revenue is not None else project.budget
    total_cost = r2(sum((d(c["totalCost"]) for c in costs), Decimal("0")))
    has_cost = any(c["hasCostData"] for c in costs)
    has_revenue = revenue is not None and d(revenue) > 0
    margin_amount = r2(d(revenue) - total_cost) if has_revenue else None
    margin_percent = r2(margin_amount / d(revenue) * Decimal("100")) if has_revenue and margin_amount is not None else None
    return {
        "estimatedRevenue": float(d(project.estimated_revenue)) if project.estimated_revenue is not None else None,
        "budget": float(d(project.budget)) if project.budget is not None else None,
        "totalCost": float(total_cost),
        "marginAmount": float(margin_amount) if margin_amount is not None else None,
        "marginPercent": float(margin_percent) if margin_percent is not None else None,
        "hasRevenueData": has_revenue,
        "hasCostData": has_cost,
        "isLowMarginAlert": margin_percent is not None and margin_percent < threshold,
    }


def resolve_period(project, allocations, from_date: date | None, to_date: date | None) -> tuple[date, date]:
    if from_date and to_date:
        return from_date, to_date
    start = from_date or project.start_date or (
        min(a.start_date for a in allocations) if allocations else datetime.now(timezone.utc).date()
    )
    end = to_date or project.end_date or (
        max(a.end_date for a in allocations) if allocations else add_months(start, 3)
    )
    if end < start:
        end = add_months(start, 3)
    return start, end


def add_months(day: date, months: int) -> date:
    month = day.month - 1 + months
    year = day.year + month // 12
    month = month % 12 + 1
    day_num = min(day.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                            31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day_num)


def resolve_need_period(need) -> tuple[date, date]:
    start = need.start_date or datetime.now(timezone.utc).date()
    end = need.end_date or add_months(start, 3)
    if end < start:
        end = add_months(start, 3)
    return start, end


def as_guid_list(raw) -> list[str]:
    if not raw:
        return []
    result = []
    for item in raw:
        result.append(str(item).lower())
    return result


def score_availability(min_available: Decimal, required: Decimal) -> Decimal:
    if required <= 0:
        return Decimal("0")
    ratio = min(Decimal("1"), min_available / required)
    return r2(ratio * MAX_AVAILABILITY)


def score_required(person, required_ids: list[str]) -> Decimal:
    if not required_ids:
        return MAX_REQUIRED
    person_skills = {ps.skill_id.lower() for ps in person.skills if ps.deleted_at is None}
    matched = sum(1 for sid in required_ids if sid.lower() in person_skills)
    return r2(Decimal(matched) / Decimal(len(required_ids)) * MAX_REQUIRED)


def score_desired(person, desired_ids: list[str]) -> Decimal:
    if not desired_ids:
        return Decimal("0")
    person_skills = {ps.skill_id.lower() for ps in person.skills if ps.deleted_at is None}
    matched = sum(1 for sid in desired_ids if sid.lower() in person_skills)
    return r2(Decimal(matched) / Decimal(len(desired_ids)) * MAX_DESIRED)


def score_seniority(person_seniority: str | None, expected: str | None) -> Decimal:
    if not expected or not expected.strip():
        return MAX_SENIORITY
    if not person_seniority or not person_seniority.strip():
        return Decimal("0")
    if person_seniority.lower() == expected.lower():
        return MAX_SENIORITY
    if expected.lower() in person_seniority.lower() or person_seniority.lower() in expected.lower():
        return r2(MAX_SENIORITY * Decimal("0.6"))
    return Decimal("0")


def score_history(allocations, need_role: str, project_type: str | None) -> Decimal:
    score = Decimal("0")
    active = [a for a in allocations if a.status != CLOSED]
    if any(roles_match(a.role, need_role) for a in active):
        score += MAX_HISTORY * Decimal("0.5")
    if project_type and any(
        a.project and a.project.project_type and a.project.project_type.lower() == project_type.lower()
        for a in active
    ):
        score += MAX_HISTORY * Decimal("0.5")
    return r2(score)


def score_cost(person, baselines: list[Decimal]) -> Decimal:
    if not baselines:
        return r2(MAX_COST * Decimal("0.5"))
    person_cost = hourly_rate(person)
    if person_cost is None:
        return r2(MAX_COST * Decimal("0.5"))
    minimum = min(baselines)
    maximum = max(baselines)
    if maximum <= minimum:
        return MAX_COST
    normalized = Decimal("1") - (person_cost - minimum) / (maximum - minimum)
    normalized = min(Decimal("1"), max(Decimal("0"), normalized))
    return r2(normalized * MAX_COST)


def score_overload(need, allocations, period: tuple[date, date]) -> Decimal:
    if find_first_overload(period[0], period[1], d(need.dedication_percent), allocations):
        return MAX_OVERLOAD
    weeks = person_weeks(period[0], period[1], allocations, [])
    max_allocated = max((w.allocated_percent for w in weeks), default=Decimal("0"))
    if max_allocated + d(need.dedication_percent) > 100:
        return r2(MAX_OVERLOAD * Decimal("0.5"))
    return Decimal("0")


def score_switching(allocations) -> Decimal:
    cutoff = add_months(datetime.now(timezone.utc).date(), -12)
    projects = {
        a.project_id
        for a in allocations
        if a.end_date >= cutoff and a.status != CLOSED
    }
    count = len(projects)
    if count <= 2:
        return Decimal("0")
    if count == 3:
        return r2(MAX_SWITCHING * Decimal("0.5"))
    return MAX_SWITCHING


def rank_candidates(need, project_type: str | None, people, allocations, unavailabilities, max_results: int, min_available=None, exclude_on_project=False):
    period = resolve_need_period(need)
    alloc_by_person: dict[str, list] = {}
    unav_by_person: dict[str, list] = {}
    for a in allocations:
        alloc_by_person.setdefault(a.person_id, []).append(a)
    for u in unavailabilities:
        unav_by_person.setdefault(u.person_id, []).append(u)
    baselines = []
    for p in people:
        rate = hourly_rate(p)
        if rate is not None:
            baselines.append(rate)
    required = as_guid_list(need.required_skill_ids)
    desired = as_guid_list(need.desired_skill_ids)
    candidates = []
    for person in people:
        person_alloc = alloc_by_person.get(person.id, [])
        weeks = person_weeks(period[0], period[1], person_alloc, unav_by_person.get(person.id, []))
        min_av = min((w.available_percent for w in weeks), default=Decimal("0"))
        if min_available is not None and min_av < d(min_available):
            continue
        on_project = next(
            (
                a
                for a in person_alloc
                if a.project_id == need.project_id
                and a.status != CLOSED
                and a.start_date <= period[1]
                and a.end_date >= period[0]
            ),
            None,
        )
        if exclude_on_project and on_project is not None:
            continue
        availability = score_availability(min_av, d(need.dedication_percent))
        required_s = score_required(person, required)
        desired_s = score_desired(person, desired)
        seniority = score_seniority(person.seniority, need.expected_seniority)
        history = score_history(person_alloc, need.role, project_type)
        cost = score_cost(person, baselines)
        overload = score_overload(need, person_alloc, period)
        switching = score_switching(person_alloc)
        total = max(
            Decimal("0"),
            availability + required_s + desired_s + seniority + history + cost - overload - switching,
        )
        total = r2(total)
        candidates.append({
            "personId": person.id,
            "personName": person.name,
            "jobTitle": person.job_title,
            "seniority": person.seniority,
            "minAvailablePercent": float(min_av),
            "alreadyOnProject": on_project is not None,
            "projectDedicationPercent": float(d(on_project.dedication_percent)) if on_project else None,
            "totalScore": float(total),
            "breakdown": {
                "availabilityScore": float(availability),
                "requiredSkillsScore": float(required_s),
                "desiredSkillsScore": float(desired_s),
                "seniorityScore": float(seniority),
                "historyScore": float(history),
                "costScore": float(cost),
                "overloadPenalty": float(overload),
                "switchingPenalty": float(switching),
                "totalScore": float(total),
            },
        })
    candidates.sort(key=lambda c: (-c["totalScore"], -c["minAvailablePercent"]))
    return period, candidates[:max_results]


def normalize_seniority(value: str) -> str:
    normalized = value.strip().lower()
    mapping = {
        "estagiario": "estagiario",
        "estagiário": "estagiario",
        "junior": "junior",
        "júnior": "junior",
        "pleno": "pleno",
        "senior": "senior",
        "sênior": "senior",
    }
    return mapping.get(normalized, normalized)


def matches_simulated_need(person, need) -> bool:
    required = [str(x) for x in need.required_skill_ids]
    if required:
        person_skills = {ps.skill_id.lower() for ps in person.skills if ps.deleted_at is None}
        if not all(sid.lower() in person_skills for sid in required):
            return False
    if need.expected_seniority and need.expected_seniority.strip():
        if not person.seniority:
            return False
        if normalize_seniority(person.seniority) != normalize_seniority(need.expected_seniority):
            return False
    return True


def simulate_feasibility(desired_start: date, duration_months: int, needs, people, allocations, unavailabilities, max_weeks=26):
    end_date = add_months(desired_start, duration_months)
    alloc_by = {}
    unav_by = {}
    for a in allocations:
        alloc_by.setdefault(a.person_id, []).append(a)
    for u in unavailabilities:
        unav_by.setdefault(u.person_id, []).append(u)

    def evaluate(start: date, end: date):
        roles = []
        for need in needs:
            eligible = []
            for person in people:
                if not matches_simulated_need(person, need):
                    continue
                weeks = person_weeks(start, end, alloc_by.get(person.id, []), unav_by.get(person.id, []))
                if not weeks:
                    continue
                min_av = min(w.available_percent for w in weeks)
                if min_av >= d(need.dedication_percent):
                    eligible.append({
                        "personId": person.id,
                        "personName": person.name,
                        "seniority": person.seniority,
                        "minAvailablePercent": float(min_av),
                    })
            eligible.sort(key=lambda c: -c["minAvailablePercent"])
            roles.append({
                "role": need.role,
                "expectedSeniority": need.expected_seniority,
                "dedicationPercent": float(d(need.dedication_percent)),
                "quantityRequired": need.quantity,
                "candidatesAtDesiredStart": len(eligible),
                "satisfiedAtDesiredStart": len(eligible) >= need.quantity,
                "eligibleCandidates": eligible,
            })
        return roles

    def bench_count(start: date, end: date) -> int:
        count = 0
        for person in people:
            weeks = person_weeks(start, end, alloc_by.get(person.id, []), unav_by.get(person.id, []))
            if weeks and min(w.available_percent for w in weeks) >= 50:
                count += 1
        return count

    roles = evaluate(desired_start, end_date)
    feasible = all(r["satisfiedAtDesiredStart"] for r in roles)
    bench = bench_count(desired_start, end_date)
    earliest = desired_start if feasible else None
    weeks_scanned = 1
    if not feasible:
        for week in range(1, max_weeks):
            candidate_start = desired_start + timedelta(days=week * 7)
            candidate_end = add_months(candidate_start, duration_months)
            scanned = evaluate(candidate_start, candidate_end)
            weeks_scanned = week + 1
            if all(r["satisfiedAtDesiredStart"] for r in scanned):
                earliest = candidate_start
                roles = scanned
                break
    return {
        "desiredStartDate": desired_start,
        "simulatedEndDate": end_date,
        "feasibleAtDesiredStart": feasible,
        "earliestFeasibleStart": earliest,
        "weeksScanned": weeks_scanned,
        "activePeopleCount": len(people),
        "benchAtDesiredStart": bench,
        "totalHeadcountRequired": sum(n.quantity for n in needs),
        "roles": roles,
    }
