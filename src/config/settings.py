import sys
from typing import Literal

from pydantic import ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    llm_provider: Literal["anthropic", "openai", "bedrock"] = "anthropic"
    llm_api_key: str = ""
    llm_model: str
    aws_profile: str = ""
    aws_region: str = ""
    host: str = "0.0.0.0"
    port: int = 8000
    max_request_body_size: int = 1048576
    personality_path: str = "config/personality.md"
    agent_verbose: bool = False

    @field_validator("llm_model")
    @classmethod
    def must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be empty")
        return v

    @model_validator(mode="after")
    def api_key_required_for_non_bedrock(self) -> "Settings":
        if self.llm_provider != "bedrock" and not self.llm_api_key.strip():
            raise ValueError(f"LLM_API_KEY is required for provider '{self.llm_provider}'")
        return self

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
