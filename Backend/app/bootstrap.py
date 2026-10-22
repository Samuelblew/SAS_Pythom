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
