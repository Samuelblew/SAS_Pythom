from uuid import UUID

from app.domain import d
from app.helpers import as_uuid_list, money
from app.models import (
    Allocation,
    AllocationNeed,
    Client,
    MatchingSuggestion,
    Person,
    PersonSkill,
    Project,
    Skill,
    Tenant,
    Unavailability,
    User,
)


def tenant_out(item: Tenant) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "isActive": item.is_active,
        "createdAt": item.created_at,
        "updatedAt": item.updated_at,
    }


def user_out(item: User) -> dict:
    return {
        "id": item.id,
        "email": item.email,
        "displayName": item.display_name,
        "role": item.role,
        "isActive": item.is_active,
        "createdAt": item.created_at,
        "updatedAt": item.updated_at,
    }


def skill_out(item: Skill) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "category": item.category,
        "createdAt": item.created_at,
        "updatedAt": item.updated_at,
    }


def client_out(item: Client) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "notes": item.notes,
        "createdAt": item.created_at,
        "updatedAt": item.updated_at,
    }


def person_skill_out(item: PersonSkill) -> dict:
    return {
        "id": item.id,
        "skillId": item.skill_id,
        "skillName": item.skill.name if item.skill else None,
        "skillCategory": item.skill.category if item.skill else None,
        "level": item.level,
        "lastUsedAt": item.last_used_at,
        "notes": item.notes,
    }


def person_list(item: Person) -> dict:
    skills = [s for s in item.skills if s.deleted_at is None]
    return {
        "id": item.id,
        "name": item.name,
        "jobTitle": item.job_title,
        "seniority": item.seniority,
        "weeklyCapacityHours": float(d(item.weekly_capacity_hours)),
        "status": item.status,
        "skillCount": len(skills),
        "createdAt": item.created_at,
    }


def person_out(item: Person) -> dict:
    skills = [person_skill_out(s) for s in item.skills if s.deleted_at is None]
    return {
        "id": item.id,
        "name": item.name,
        "jobTitle": item.job_title,
        "seniority": item.seniority,
        "hourlyCost": money(item.hourly_cost),
        "monthlyCost": money(item.monthly_cost),
        "weeklyCapacityHours": float(d(item.weekly_capacity_hours)),
        "location": item.location,
        "team": item.team,
        "status": item.status,
        "skills": skills,
        "createdAt": item.created_at,
        "updatedAt": item.updated_at,
    }


def unavailability_out(item: Unavailability) -> dict:
    return {
        "id": item.id,
        "personId": item.person_id,
        "startDate": item.start_date,
        "endDate": item.end_date,
        "type": item.type,
        "notes": item.notes,
        "createdAt": item.created_at,
        "updatedAt": item.updated_at,
    }


def project_list(item: Project) -> dict:
    return {
        "id": item.id,
        "clientId": item.client_id,
        "clientName": item.client.name if item.client else "",
        "name": item.name,
        "status": item.status,
        "priority": item.priority,
        "startDate": item.start_date,
        "endDate": item.end_date,
        "createdAt": item.created_at,
    }


def project_out(item: Project) -> dict:
    data = project_list(item)
    data.update({
        "budget": money(item.budget),
        "estimatedRevenue": money(item.estimated_revenue),
        "projectType": item.project_type,
        "commercialOwner": item.commercial_owner,
        "deliveryOwner": item.delivery_owner,
        "updatedAt": item.updated_at,
    })
    return data


def need_list(item: AllocationNeed) -> dict:
    return {
        "id": item.id,
        "projectId": item.project_id,
        "projectName": item.project.name if item.project else "",
        "role": item.role,
        "expectedSeniority": item.expected_seniority,
        "requiredSkillIds": as_uuid_list(item.required_skill_ids),
        "status": item.status,
        "urgency": item.urgency,
        "criticality": item.criticality,
        "dedicationPercent": float(d(item.dedication_percent)),
        "startDate": item.start_date,
        "endDate": item.end_date,
        "createdAt": item.created_at,
    }


def need_out(item: AllocationNeed) -> dict:
    data = need_list(item)
    data.update({
        "desiredSkillIds": as_uuid_list(item.desired_skill_ids),
        "updatedAt": item.updated_at,
    })
    return data


def allocation_list(item: Allocation) -> dict:
    return {
        "id": item.id,
        "personId": item.person_id,
        "personName": item.person.name if item.person else "",
        "projectId": item.project_id,
        "projectName": item.project.name if item.project else "",
        "role": item.role,
        "dedicationPercent": float(d(item.dedication_percent)),
        "status": item.status,
        "startDate": item.start_date,
        "endDate": item.end_date,
        "createdAt": item.created_at,
    }


def allocation_out(item: Allocation) -> dict:
    data = allocation_list(item)
    data.update({"notes": item.notes, "updatedAt": item.updated_at})
    return data


def suggestion_out(item: MatchingSuggestion) -> dict:
    return {
        "id": item.id,
        "allocationNeedId": item.allocation_need_id,
        "projectName": item.need.project.name if item.need and item.need.project else None,
        "needRole": item.need.role if item.need else None,
        "personId": item.person_id,
        "personName": item.person.name if item.person else None,
        "decision": item.decision,
        "score": float(d(item.score)),
        "notes": item.notes,
        "decidedByUserId": item.decided_by_user_id,
        "createdAt": item.created_at,
    }
