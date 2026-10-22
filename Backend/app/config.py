from functools import lru_cache
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "ias_dev"
    jwt_secret: str = "ias-dev-jwt-secret-change-in-production-32chars"
    jwt_issuer: str = "IAS.Dev"
    jwt_audience: str = "IAS.Api"
    jwt_expiration_hours: int = 8
    environment: str = "Development"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def database_url(self) -> str:
        password = quote_plus(self.mysql_password)
        return (
            f"mysql+pymysql://{self.mysql_user}:{password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            "?charset=utf8mb4"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def is_dev(self) -> bool:
        return self.environment.lower() in {"development", "testing", "dev"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
