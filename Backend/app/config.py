from functools import lru_cache
from urllib.parse import quote_plus, unquote, urlparse

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    mysql_host: str = Field(
        default="localhost",
        validation_alias=AliasChoices("MYSQL_HOST", "MYSQLHOST", "RDS_HOSTNAME", "DB_HOST"),
    )
    mysql_port: int = Field(
        default=3306,
        validation_alias=AliasChoices("MYSQL_PORT", "MYSQLPORT", "RDS_PORT", "DB_PORT"),
    )
    mysql_user: str = Field(
        default="root",
        validation_alias=AliasChoices("MYSQL_USER", "MYSQLUSER", "RDS_USERNAME", "DB_USER"),
    )
    mysql_password: str = Field(
        default="",
        validation_alias=AliasChoices("MYSQL_PASSWORD", "MYSQLPASSWORD", "RDS_PASSWORD", "DB_PASSWORD"),
    )
    mysql_database: str = Field(
        default="ias_dev",
        validation_alias=AliasChoices("MYSQL_DATABASE", "MYSQLDATABASE", "RDS_DB_NAME", "DB_NAME"),
    )
    mysql_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("MYSQL_URL", "MYSQL_PRIVATE_URL", "DATABASE_URL"),
    )
    mysql_ssl: bool | None = Field(default=None, validation_alias=AliasChoices("MYSQL_SSL"))
    jwt_secret: str = "ias-dev-jwt-secret-change-in-production-32chars"
    jwt_issuer: str = "IAS.Dev"
    jwt_audience: str = "IAS.Api"
    jwt_expiration_hours: int = 8
    environment: str = Field(
        default="Development",
        validation_alias=AliasChoices("ENVIRONMENT", "APP_ENV"),
    )
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    frontend_dist: str | None = Field(default=None, validation_alias=AliasChoices("FRONTEND_DIST"))

    def _mysql_from_url(self) -> tuple[str, int, str, str, str] | None:
        if not self.mysql_url:
            return None
        parsed = urlparse(self.mysql_url)
        if not parsed.hostname:
            return None
        database = (parsed.path or "/").lstrip("/") or self.mysql_database
        return (
            parsed.hostname,
            parsed.port or 3306,
            unquote(parsed.username or self.mysql_user),
            unquote(parsed.password or self.mysql_password),
            database,
        )

    @property
    def mysql_connection(self) -> tuple[str, int, str, str, str]:
        parsed = self._mysql_from_url()
        if parsed:
            return parsed
        return self.mysql_host, self.mysql_port, self.mysql_user, self.mysql_password, self.mysql_database

    @property
    def use_ssl(self) -> bool:
        if self.mysql_ssl is not None:
            return self.mysql_ssl
        host, *_ = self.mysql_connection
        return host not in {"localhost", "127.0.0.1"}

    @property
    def database_url(self) -> str:
        host, port, user, password, database = self.mysql_connection
        auth = quote_plus(user)
        if password:
            auth = f"{auth}:{quote_plus(password)}"
        return f"mysql+pymysql://{auth}@{host}:{port}/{database}?charset=utf8mb4"

    @property
    def cors_origin_list(self) -> list[str]:
        configured = [item.strip() for item in self.cors_origins.split(",") if item.strip()]
        if configured:
            return configured
        if self.is_dev:
            return ["http://localhost:5173", "http://127.0.0.1:5173"]
        return ["*"]

    @property
    def is_dev(self) -> bool:
        return self.environment.lower() in {"development", "testing", "dev"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
