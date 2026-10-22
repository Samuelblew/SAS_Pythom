from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import CHAR, JSON, Boolean, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def new_id() -> str:
    return str(uuid4())


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column("Id", CHAR(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column("Name", String(200))
    is_active: Mapped[bool] = mapped_column("IsActive", Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column("CreatedAt", DateTime(6))
    updated_at: Mapped[Optional[datetime]] = mapped_column("UpdatedAt", DateTime(6), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column("DeletedAt", DateTime(6), nullable=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column("Id", CHAR(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column("TenantId", CHAR(36))
    email: Mapped[str] = mapped_column("Email", String(200))
    display_name: Mapped[str] = mapped_column("DisplayName", String(200))
    role: Mapped[str] = mapped_column("Role", String(32))
    is_active: Mapped[bool] = mapped_column("IsActive", Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column("CreatedAt", DateTime(6))
    updated_at: Mapped[Optional[datetime]] = mapped_column("UpdatedAt", DateTime(6), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column("DeletedAt", DateTime(6), nullable=True)


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(CHAR(36))
    name: Mapped[str] = mapped_column(String(200))
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(6))
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(6), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(6), nullable=True)

    projects: Mapped[list["Project"]] = relationship(back_populates="client")


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(CHAR(36))
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(6))
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(6), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(6), nullable=True)


class Person(Base):
    __tablename__ = "people"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(CHAR(36))
    name: Mapped[str] = mapped_column(String(200))
    job_title: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    seniority: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    hourly_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    monthly_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    weekly_capacity_hours: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    location: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    team: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(6))
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(6), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(6), nullable=True)

    skills: Mapped[list["PersonSkill"]] = relationship(back_populates="person")
    allocations: Mapped[list["Allocation"]] = relationship(back_populates="person")
    unavailabilities: Mapped[list["Unavailability"]] = relationship(back_populates="person")


class PersonSkill(Base):
    __tablename__ = "person_skills"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(CHAR(36))
    person_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("people.id"))
    skill_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("skills.id"))
    level: Mapped[str] = mapped_column(String(32))
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(6), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(6))
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(6), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(6), nullable=True)

    person: Mapped[Person] = relationship(back_populates="skills", foreign_keys=[person_id])
    skill: Mapped[Optional[Skill]] = relationship(foreign_keys=[skill_id])


class Unavailability(Base):
    __tablename__ = "unavailabilities"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(CHAR(36))
    person_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("people.id"))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    type: Mapped[str] = mapped_column(String(32))
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(6))
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(6), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(6), nullable=True)

    person: Mapped[Person] = relationship(back_populates="unavailabilities", foreign_keys=[person_id])


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(CHAR(36))
    client_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("clients.id"))
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(32))
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    priority: Mapped[str] = mapped_column(String(32))
    budget: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    estimated_revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    project_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    commercial_owner: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    delivery_owner: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(6))
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(6), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(6), nullable=True)

    client: Mapped[Client] = relationship(back_populates="projects", foreign_keys=[client_id])
    allocations: Mapped[list["Allocation"]] = relationship(back_populates="project")
    needs: Mapped[list["AllocationNeed"]] = relationship(back_populates="project")


class AllocationNeed(Base):
    __tablename__ = "allocation_needs"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(CHAR(36))
    project_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("projects.id"))
    role: Mapped[str] = mapped_column(String(80))
    expected_seniority: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    required_skill_ids: Mapped[list] = mapped_column(JSON, default=list)
    desired_skill_ids: Mapped[list] = mapped_column(JSON, default=list)
    dedication_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    urgency: Mapped[str] = mapped_column(String(32))
    criticality: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(6))
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(6), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(6), nullable=True)

    project: Mapped[Project] = relationship(back_populates="needs", foreign_keys=[project_id])
    suggestions: Mapped[list["MatchingSuggestion"]] = relationship(back_populates="need")


class Allocation(Base):
    __tablename__ = "allocations"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(CHAR(36))
    person_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("people.id"))
    project_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("projects.id"))
    role: Mapped[str] = mapped_column(String(80))
    dedication_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32))
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(6))
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(6), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(6), nullable=True)

    person: Mapped[Person] = relationship(back_populates="allocations", foreign_keys=[person_id])
    project: Mapped[Project] = relationship(back_populates="allocations", foreign_keys=[project_id])


class MatchingSuggestion(Base):
    __tablename__ = "matching_suggestions"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(CHAR(36))
    allocation_need_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("allocation_needs.id"))
    person_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("people.id"))
    decision: Mapped[str] = mapped_column(String(32))
    score: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    decided_by_user_id: Mapped[Optional[str]] = mapped_column(CHAR(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(6))
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(6), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(6), nullable=True)

    need: Mapped[AllocationNeed] = relationship(back_populates="suggestions", foreign_keys=[allocation_need_id])
    person: Mapped[Optional[Person]] = relationship(foreign_keys=[person_id])


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(CHAR(36))
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str] = mapped_column(CHAR(36))
    action: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    changes_json: Mapped[Optional[object]] = mapped_column(JSON, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(6))
