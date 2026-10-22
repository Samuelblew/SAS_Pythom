from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

T = TypeVar("T")
Num = Annotated[Decimal | float | int | None, Field(default=None)]


def _num(value: Decimal | float | int | None) -> float | None:
    if value is None:
        return None
    return float(value)


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        ser_json_bytes="utf8",
    )


class Paged(CamelModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total_count: int
    total_pages: int


def paged(items: list[T], page: int, page_size: int, total: int) -> dict[str, Any]:
    total_pages = (total + page_size - 1) // page_size if page_size else 0
    return {
        "items": items,
        "page": page,
        "pageSize": page_size,
        "totalCount": total,
        "totalPages": total_pages,
    }


class TenantCreate(CamelModel):
    name: str = Field(min_length=1, max_length=200)


class TenantOut(CamelModel):
    id: UUID
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None


class DevTokenIn(CamelModel):
    tenant_id: UUID
    user_id: UUID


class DevTokenOut(CamelModel):
    access_token: str
    token_type: str
    expires_in_hours: int


class UserCreate(CamelModel):
    email: str
    display_name: str
    role: str


class UserUpdate(CamelModel):
    email: str
    display_name: str
    role: str
    is_active: bool


class UserOut(CamelModel):
    id: UUID
    email: str
    display_name: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None


class ClientCreate(CamelModel):
    name: str = Field(min_length=1, max_length=200)
    notes: str | None = None


class ClientUpdate(ClientCreate):
    pass


class ClientListItem(CamelModel):
    id: UUID
    name: str
    project_count: int
    created_at: datetime


class ClientOut(CamelModel):
    id: UUID
    name: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class SkillCreate(CamelModel):
    name: str = Field(min_length=1, max_length=120)
    category: str | None = None


class SkillOut(CamelModel):
    id: UUID
    name: str
    category: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class PersonWrite(CamelModel):
    name: str = Field(min_length=1, max_length=200)
    job_title: str | None = None
    seniority: str | None = None
    hourly_cost: Decimal | None = None
    monthly_cost: Decimal | None = None
    weekly_capacity_hours: Decimal
    location: str | None = None
    team: str | None = None
    status: str


class PersonSkillOut(CamelModel):
    id: UUID
    skill_id: UUID
    skill_name: str | None = None
    skill_category: str | None = None
    level: str
    last_used_at: datetime | None = None
    notes: str | None = None


class PersonListItem(CamelModel):
    id: UUID
    name: str
    job_title: str | None = None
    seniority: str | None = None
    weekly_capacity_hours: float
    status: str
    skill_count: int
    created_at: datetime


class PersonOut(CamelModel):
    id: UUID
    name: str
    job_title: str | None = None
    seniority: str | None = None
    hourly_cost: float | None = None
    monthly_cost: float | None = None
    weekly_capacity_hours: float
    location: str | None = None
    team: str | None = None
    status: str
    skills: list[PersonSkillOut] = []
    created_at: datetime
    updated_at: datetime | None = None


class PersonSkillCreate(CamelModel):
    skill_id: UUID
    level: str
    last_used_at: datetime | None = None
    notes: str | None = None


class PersonSkillUpdate(CamelModel):
    level: str
    last_used_at: datetime | None = None
    notes: str | None = None


class UnavailabilityWrite(CamelModel):
    start_date: date
    end_date: date
    type: str
    notes: str | None = None


class UnavailabilityOut(CamelModel):
    id: UUID
    person_id: UUID
    start_date: date
    end_date: date
    type: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class ProjectWrite(CamelModel):
    client_id: UUID
    name: str
    status: str
    start_date: date | None = None
    end_date: date | None = None
    priority: str
    budget: Decimal | None = None
    estimated_revenue: Decimal | None = None
    project_type: str | None = None
    commercial_owner: str | None = None
    delivery_owner: str | None = None


class ProjectListItem(CamelModel):
    id: UUID
    client_id: UUID
    client_name: str
    name: str
    status: str
    priority: str
    start_date: date | None = None
    end_date: date | None = None
    created_at: datetime


class ProjectOut(ProjectListItem):
    budget: float | None = None
    estimated_revenue: float | None = None
    project_type: str | None = None
    commercial_owner: str | None = None
    delivery_owner: str | None = None
    updated_at: datetime | None = None


class NeedWrite(CamelModel):
    project_id: UUID
    role: str
    expected_seniority: str | None = None
    required_skill_ids: list[UUID] = []
    desired_skill_ids: list[UUID] = []
    dedication_percent: Decimal
    start_date: date | None = None
    end_date: date | None = None
    urgency: str
    criticality: str
    status: str


class NeedListItem(CamelModel):
    id: UUID
    project_id: UUID
    project_name: str
    role: str
    expected_seniority: str | None = None
    required_skill_ids: list[UUID]
    status: str
    urgency: str
    criticality: str
    dedication_percent: float
    start_date: date | None = None
    end_date: date | None = None
    created_at: datetime


class NeedOut(NeedListItem):
    desired_skill_ids: list[UUID]
    updated_at: datetime | None = None


class SuggestionWrite(CamelModel):
    person_id: UUID
    decision: str
    score: Decimal
    notes: str | None = None


class SuggestionOut(CamelModel):
    id: UUID
    allocation_need_id: UUID
    project_name: str | None = None
    need_role: str | None = None
    person_id: UUID
    person_name: str | None = None
    decision: str
    score: float
    notes: str | None = None
    decided_by_user_id: UUID | None = None
    created_at: datetime


class AllocationWrite(CamelModel):
    person_id: UUID
    project_id: UUID
    role: str
    dedication_percent: Decimal
    start_date: date
    end_date: date
    status: str
    notes: str | None = None


class AllocationListItem(CamelModel):
    id: UUID
    person_id: UUID
    person_name: str
    project_id: UUID
    project_name: str
    role: str
    dedication_percent: float
    status: str
    start_date: date
    end_date: date
    created_at: datetime


class AllocationOut(AllocationListItem):
    notes: str | None = None
    updated_at: datetime | None = None


class FeasibilityNeedIn(CamelModel):
    role: str
    expected_seniority: str | None = None
    required_skill_ids: list[UUID] = []
    dedication_percent: Decimal
    quantity: int


class FeasibilityIn(CamelModel):
    desired_start_date: date
    duration_months: int
    needs: list[FeasibilityNeedIn]


class MarginSimIn(CamelModel):
    project_id: UUID
    person_id: UUID
    role: str
    dedication_percent: Decimal
    start_date: date
    end_date: date
    margin_alert_threshold_percent: Decimal = Decimal("15")
