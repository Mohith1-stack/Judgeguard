from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(alias="DATABASE_URL")
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")

    session_cookie_name: str = Field(default="judgeguard_session", alias="SESSION_COOKIE_NAME")
    session_ttl_hours: int = Field(default=168, alias="SESSION_TTL_HOURS", ge=1, le=24 * 30)
    cookie_secure: bool = Field(default=False, alias="COOKIE_SECURE")

    bootstrap_admin_email: str | None = Field(default=None, alias="BOOTSTRAP_ADMIN_EMAIL")
    bootstrap_admin_password: str | None = Field(default=None, alias="BOOTSTRAP_ADMIN_PASSWORD")

    signing_secret: str = Field(alias="SIGNING_SECRET", min_length=32)

    vote_rate_limit: int = Field(default=30, alias="VOTE_RATE_LIMIT", ge=1, le=10000)
    vote_rate_window_seconds: float = Field(default=60.0, alias="VOTE_RATE_WINDOW_SECONDS", gt=0, le=3600)
    comment_rate_limit: int = Field(default=10, alias="COMMENT_RATE_LIMIT", ge=1, le=10000)
    comment_rate_window_seconds: float = Field(default=60.0, alias="COMMENT_RATE_WINDOW_SECONDS", gt=0, le=3600)
    login_rate_limit: int = Field(default=10, alias="LOGIN_RATE_LIMIT", ge=1, le=1000)
    login_rate_window_seconds: float = Field(default=60.0, alias="LOGIN_RATE_WINDOW_SECONDS", gt=0, le=3600)
    public_voter_cookie_name: str = Field(default="judgeguard_voter", alias="PUBLIC_VOTER_COOKIE_NAME", min_length=1, max_length=80)

    webhook_timeout_seconds: float = Field(default=5.0, alias="WEBHOOK_TIMEOUT_SECONDS", gt=0, le=30)
    webhook_allow_private_networks: bool = Field(default=False, alias="WEBHOOK_ALLOW_PRIVATE_NETWORKS")

    public_app_url: str = Field(default="http://localhost:3000", alias="PUBLIC_APP_URL")
    public_api_url: str = Field(default="http://localhost:8000/api/v1", alias="PUBLIC_API_URL")

    @property
    def cors_origin_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
