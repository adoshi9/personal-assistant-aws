"""Application settings and configuration."""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="personal-assistant", description="Application name")
    app_env: str = Field(default="development", description="Environment (development/production)")
    log_level: str = Field(default="INFO", description="Logging level")

    # AWS
    aws_region: str = Field(default="us-east-1", description="AWS region")
    aws_secrets_prefix: str = Field(
        default="personal-assistant/", description="Prefix for AWS Secrets Manager"
    )

    # Telegram
    telegram_bot_token_secret: str = Field(
        default="telegram/bot-token", description="AWS Secret name for Telegram bot token"
    )

    # AI Provider
    anthropic_api_key_secret: str = Field(
        default="anthropic/api-key", description="AWS Secret name for Anthropic API key"
    )
    anthropic_model: str = Field(
        default="claude-3-5-sonnet-20241022", description="Anthropic model to use"
    )
    anthropic_max_tokens: int = Field(default=4096, description="Max tokens for AI responses")

    # Gateway
    gateway_host: str = Field(default="0.0.0.0", description="Gateway host")
    gateway_port: int = Field(default=8000, description="Gateway port")

    # Approval Workflow
    approval_timeout_seconds: int = Field(
        default=300, description="Timeout for approval requests in seconds"
    )
    approval_require_confirmation: bool = Field(
        default=True, description="Require explicit confirmation for all state-changing actions"
    )

    # Connectors
    github_token_secret: Optional[str] = Field(
        default="github/token", description="AWS Secret name for GitHub token"
    )
    openweather_api_key_secret: Optional[str] = Field(
        default="openweather/api-key", description="AWS Secret name for OpenWeather API key"
    )
    google_calendar_credentials_secret: Optional[str] = Field(
        default="google/calendar-credentials",
        description="AWS Secret name for Google Calendar credentials",
    )

    # Database (Optional)
    database_url: Optional[str] = Field(
        default=None, description="Database URL for approval history"
    )

    # Monitoring (Optional)
    sentry_dsn: Optional[str] = Field(default=None, description="Sentry DSN for error tracking")
    datadog_api_key: Optional[str] = Field(default=None, description="Datadog API key")

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.app_env.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.app_env.lower() == "development"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
