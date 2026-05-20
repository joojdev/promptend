import sys

from pydantic import ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    llm_api_key: str
    llm_model: str
    host: str = "0.0.0.0"
    port: int = 8000
    max_request_body_size: int = 1048576
    personality_path: str = "config/personality.md"

    @field_validator("llm_api_key", "llm_model")
    @classmethod
    def must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be empty")
        return v

    @field_validator("port")
    @classmethod
    def port_in_range(cls, v: int) -> int:
        if not 1 <= v <= 65535:
            raise ValueError("must be between 1 and 65535")
        return v

    @field_validator("max_request_body_size")
    @classmethod
    def size_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("must be > 0")
        return v


def load_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)
