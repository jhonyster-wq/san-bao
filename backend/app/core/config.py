import os
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
_DEFAULT_SQLITE_PATH = os.path.join(_PROJECT_ROOT, "sanbao_dev.db")


class Settings(BaseSettings):
    PROJECT_NAME: str = "Sistema Integral San Bao"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # Mantener habilitado el selector de ingreso rápido de desarrollo en el login
    ENABLE_DEV_LOGIN: bool = True

    # Seguridad JWT
    SECRET_KEY: str = "san_bao_super_secret_development_key_change_in_production_9988776655"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 horas
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Base de datos (soporta SQLite embebido, PostgreSQL o MySQL en GoDaddy)
    DATABASE_URL: str = f"sqlite:///{_DEFAULT_SQLITE_PATH}"
    TEST_DATABASE_URL: str = "sqlite:///./test_sanbao.db"

    # CORS (habilitado para cualquier dominio o subdominio en GoDaddy + localhost)
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # Identificadores de las dos Sociedades SpA San Bao
    INSTITUTO_RUT: str = "77123456-9"
    CLINICA_RUT: str = "76987654-5"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow",
    )


settings = Settings()
