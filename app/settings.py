from functools import lru_cache
from typing import List, Optional

from pydantic import BaseSettings, Field, validator


class Settings(BaseSettings):
    database_url: str = "sqlite:///./database.db"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    upload_dir: str = "./uploaded_files"
    cors_allow_origins: List[str] = Field(default_factory=lambda: ["*"])
    auto_create_schema: bool = True
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-5.4"
    openai_analysis_model: Optional[str] = None
    openai_ingest_model: Optional[str] = None
    econ_ai_model_routing_enabled: bool = True
    econ_ai_default_model: Optional[str] = None
    econ_ai_structured_model: Optional[str] = None
    econ_ai_deep_analysis_model: Optional[str] = None
    econ_ai_fallback_model: Optional[str] = None
    openai_base_url: Optional[str] = None
    openai_timeout_seconds: float = 45.0

    @validator("cors_allow_origins", pre=True)
    def parse_cors_allow_origins(cls, value):
        if value is None or value == "":
            return ["*"]
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    class Config:
        env_prefix = ""
        case_sensitive = False
        env_file = ".env"
        env_file_encoding = "utf-8"

        @classmethod
        def parse_env_var(cls, field_name, raw_value):
            if field_name == "cors_allow_origins":
                return raw_value
            return BaseSettings.Config.parse_env_var(field_name, raw_value)

        fields = {
            "database_url": {"env": "DATABASE_URL"},
            "app_host": {"env": "APP_HOST"},
            "app_port": {"env": "APP_PORT"},
            "upload_dir": {"env": "UPLOAD_DIR"},
            "cors_allow_origins": {"env": "CORS_ALLOW_ORIGINS"},
            "auto_create_schema": {"env": "AUTO_CREATE_SCHEMA"},
            "openai_api_key": {"env": "OPENAI_API_KEY"},
            "openai_model": {"env": "OPENAI_MODEL"},
            "openai_analysis_model": {"env": "OPENAI_ANALYSIS_MODEL"},
            "openai_ingest_model": {"env": "OPENAI_INGEST_MODEL"},
            "econ_ai_model_routing_enabled": {"env": "ECON_AI_MODEL_ROUTING_ENABLED"},
            "econ_ai_default_model": {"env": "ECON_AI_DEFAULT_MODEL"},
            "econ_ai_structured_model": {"env": "ECON_AI_STRUCTURED_MODEL"},
            "econ_ai_deep_analysis_model": {"env": "ECON_AI_DEEP_ANALYSIS_MODEL"},
            "econ_ai_fallback_model": {"env": "ECON_AI_FALLBACK_MODEL"},
            "openai_base_url": {"env": "OPENAI_BASE_URL"},
            "openai_timeout_seconds": {"env": "OPENAI_TIMEOUT_SECONDS"},
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
