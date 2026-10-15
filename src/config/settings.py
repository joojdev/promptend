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
    personality: str = "default"
    personality_path: str = ""
    agent_verbose: bool = False
    rate_limit_per_minute: int = 20
    agent_timeout_seconds: float = 30
    sensitive_header_names: str = "authorization,proxy-authorization,cookie,set-cookie,x-api-key"
    sensitive_header_fragments: str = "token,secret,key"
    state_file: str = ""
    kv_max_value_bytes: int = 65536
    kv_max_keys: int = 1000
    llm_price_input_per_mtok: float | None = None
    llm_price_output_per_mtok: float | None = None
    admin_username: str = ""
    admin_password_hash: str = ""
    admin_token_ttl_minutes: int = 60
    login_rate_limit_per_minute: int = 5
    tokens_db_path: str = "data/tokens.db"
    auth_enabled: bool = True

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

    @field_validator(
        "rate_limit_per_minute",
        "agent_timeout_seconds",
        "kv_max_value_bytes",
        "kv_max_keys",
        "admin_token_ttl_minutes",
        "login_rate_limit_per_minute",
    )
    @classmethod
    def must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("must be > 0")
        return v

    @model_validator(mode="after")
    def prices_set_together(self) -> "Settings":
        price_in = self.llm_price_input_per_mtok
        price_out = self.llm_price_output_per_mtok
        if (price_in is None) != (price_out is None):
            raise ValueError(
                "LLM_PRICE_INPUT_PER_MTOK and LLM_PRICE_OUTPUT_PER_MTOK must be set together"
            )
        if price_in is not None and price_in < 0:
            raise ValueError("LLM_PRICE_INPUT_PER_MTOK must be >= 0")
        if price_out is not None and price_out < 0:
            raise ValueError("LLM_PRICE_OUTPUT_PER_MTOK must be >= 0")
        return self

    @field_validator("admin_username", "admin_password_hash")
    @classmethod
    def strip_admin_fields(cls, v: str) -> str:
        return v.strip()

    @field_validator("tokens_db_path")
    @classmethod
    def path_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be empty")
        return v.strip()

    @property
    def admin_enabled(self) -> bool:
        return bool(self.admin_username and self.admin_password_hash)

    @property
    def sensitive_header_rule(self) -> tuple[frozenset[str], tuple[str, ...]]:
        def split(raw: str) -> list[str]:
            return [item.strip().lower() for item in raw.split(",") if item.strip()]

        return (
            frozenset(split(self.sensitive_header_names)),
            tuple(split(self.sensitive_header_fragments)),
        )


def load_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)
