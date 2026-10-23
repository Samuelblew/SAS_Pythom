import time

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.database import engine

STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS tenants (
      `Id` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
      `Name` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
      `IsActive` tinyint(1) NOT NULL,
      `CreatedAt` datetime(6) NOT NULL,
      `UpdatedAt` datetime(6) NULL,
      `DeletedAt` datetime(6) NULL,
      PRIMARY KEY (`Id`),
      UNIQUE KEY `IX_tenants_Name` (`Name`)
    ) CHARACTER SET utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS users (
      `Id` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
      `Email` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
      `DisplayName` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
      `Role` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
      `IsActive` tinyint(1) NOT NULL,
      `TenantId` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
      `CreatedAt` datetime(6) NOT NULL,
      `UpdatedAt` datetime(6) NULL,
      `DeletedAt` datetime(6) NULL,
      PRIMARY KEY (`Id`),
      UNIQUE KEY `IX_users_TenantId_Email` (`TenantId`, `Email`)
    ) CHARACTER SET utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS matching_suggestions (
      `id` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
      `allocation_need_id` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
      `person_id` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
      `decision` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
      `score` decimal(8,2) NOT NULL,
      `notes` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
      `decided_by_user_id` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NULL,
      `tenant_id` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
      `created_at` datetime(6) NOT NULL,
      `updated_at` datetime(6) NULL,
      `deleted_at` datetime(6) NULL,
      PRIMARY KEY (`id`),
      KEY `ix_matching_suggestions_allocation_need_id` (`allocation_need_id`),
      KEY `IX_matching_suggestions_person_id` (`person_id`),
      KEY `ix_matching_suggestions_tenant_created` (`tenant_id`, `created_at`)
    ) CHARACTER SET utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS clients (
      `id` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
      `tenant_id` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
      `name` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
      `notes` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
      `created_at` datetime(6) NOT NULL,
      `updated_at` datetime(6) NULL,
      `deleted_at` datetime(6) NULL,
      PRIMARY KEY (`id`),
      KEY `ix_clients_tenant_id` (`tenant_id`)
    ) CHARACTER SET utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS skills (
      `id` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
      `tenant_id` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
      `name` varchar(120) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
      `category` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
      `created_at` datetime(6) NOT NULL,
      `updated_at` datetime(6) NULL,
      `deleted_at` datetime(6) NULL,
      PRIMARY KEY (`id`),
      KEY `ix_skills_tenant_id` (`tenant_id`)
    ) CHARACTER SET utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS people (
      `id` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
      `tenant_id` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
      `name` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
      `job_title` varchar(120) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
      `seniority` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
      `hourly_cost` decimal(18,2) NULL,
      `monthly_cost` decimal(18,2) NULL,
      `weekly_capacity_hours` decimal(5,2) NOT NULL,
      `location` varchar(120) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
      `team` varchar(120) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
      `status` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
      `created_at` datetime(6) NOT NULL,
      `updated_at` datetime(6) NULL,
      `deleted_at` datetime(6) NULL,
      PRIMARY KEY (`id`),
      KEY `ix_people_tenant_id` (`tenant_id`)
    ) CHARACTER SET utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS person_skills (
      `id` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
      `tenant_id` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
      `person_id` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
      `skill_id` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
      `level` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
      `last_used_at` datetime(6) NULL,
      `notes` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
      `created_at` datetime(6) NOT NULL,
      `updated_at` datetime(6) NULL,
      `deleted_at` datetime(6) NULL,
      PRIMARY KEY (`id`),
      KEY `ix_person_skills_person_id` (`person_id`),
      KEY `ix_person_skills_skill_id` (`skill_id`)
    ) CHARACTER SET utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS unavailabilities (
      `id` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
      `tenant_id` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
      `person_id` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
      `start_date` date NOT NULL,
      `end_date` date NOT NULL,
      `type` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
      `notes` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
      `created_at` datetime(6) NOT NULL,
      `updated_at` datetime(6) NULL,
      `deleted_at` datetime(6) NULL,
      PRIMARY KEY (`id`),
      KEY `ix_unavailabilities_person_id` (`person_id`)
    ) CHARACTER SET utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS projects (
      `id` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
      `tenant_id` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
      `client_id` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
      `name` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
      `status` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
      `start_date` date NULL,
      `end_date` date NULL,
      `priority` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
      `budget` decimal(18,2) NULL,
      `estimated_revenue` decimal(18,2) NULL,
      `project_type` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
      `commercial_owner` varchar(120) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
      `delivery_owner` varchar(120) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
      `created_at` datetime(6) NOT NULL,
      `updated_at` datetime(6) NULL,
      `deleted_at` datetime(6) NULL,
      PRIMARY KEY (`id`),
      KEY `ix_projects_tenant_id` (`tenant_id`),
      KEY `ix_projects_client_id` (`client_id`)
    ) CHARACTER SET utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS allocation_needs (
      `id` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
      `tenant_id` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
      `project_id` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
      `role` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
      `expected_seniority` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
      `required_skill_ids` json NOT NULL,
      `desired_skill_ids` json NOT NULL,
      `dedication_percent` decimal(5,2) NOT NULL,
      `start_date` date NULL,
      `end_date` date NULL,
      `urgency` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
      `criticality` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
      `status` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
      `created_at` datetime(6) NOT NULL,
      `updated_at` datetime(6) NULL,
      `deleted_at` datetime(6) NULL,
      PRIMARY KEY (`id`),
      KEY `ix_allocation_needs_project_id` (`project_id`)
    ) CHARACTER SET utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS allocations (
      `id` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
      `tenant_id` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
      `person_id` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
      `project_id` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
      `role` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
      `dedication_percent` decimal(5,2) NOT NULL,
      `start_date` date NOT NULL,
      `end_date` date NOT NULL,
      `status` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
      `notes` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
      `created_at` datetime(6) NOT NULL,
      `updated_at` datetime(6) NULL,
      `deleted_at` datetime(6) NULL,
      PRIMARY KEY (`id`),
      KEY `ix_allocations_person_id` (`person_id`),
      KEY `ix_allocations_project_id` (`project_id`)
    ) CHARACTER SET utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_logs (
      `id` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
      `tenant_id` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
      `entity_type` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
      `entity_id` char(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
      `action` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
      `actor_id` varchar(120) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
      `summary` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
      `changes_json` json NULL,
      `occurred_at` datetime(6) NOT NULL,
      PRIMARY KEY (`id`),
      KEY `ix_audit_logs_tenant_id` (`tenant_id`)
    ) CHARACTER SET utf8mb4
    """,
]


def ensure_schema() -> None:
    last_error: Exception | None = None
    for attempt in range(1, 16):
        try:
            with engine.begin() as conn:
                for statement in STATEMENTS:
                    conn.execute(text(statement))
            return
        except OperationalError as exc:
            last_error = exc
            time.sleep(min(2 * attempt, 10))
    raise last_error or RuntimeError("Não foi possível conectar ao MySQL.")
