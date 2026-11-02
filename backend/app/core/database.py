import logging
import os
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.core.config import settings

logger = logging.getLogger("sanbao.database")

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
_FALLBACK_SQLITE_URL = f"sqlite:///{os.path.join(_PROJECT_ROOT, 'sanbao_dev.db')}"

SCHEMA_TRANSLATE_MAP = {
    "core": None,
    "academic": None,
    "clinical": None,
    "finance": None,
    "hr": None,
    "ecommerce": None,
    "lms": None,
    "integrations": None,
    "bi": None,
    "audit": None,
}


def _build_engine(db_url: str):
    connect_args = {}
    execution_options = {}

    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        execution_options = {"schema_translate_map": SCHEMA_TRANSLATE_MAP}
    elif db_url.startswith("mysql") or db_url.startswith("mariadb"):
        # En GoDaddy cPanel con MySQL/MariaDB se traducen los esquemas lógicos al esquema de la BD
        execution_options = {"schema_translate_map": SCHEMA_TRANSLATE_MAP}

    engine_kwargs = {
        "connect_args": connect_args,
        "execution_options": execution_options,
        "echo": False,
        "future": True,
        "pool_pre_ping": True,
    }

    if not db_url.startswith("sqlite"):
        engine_kwargs.update(
            {
                "pool_size": 20,
                "max_overflow": 40,
                "pool_recycle": 1800,
            }
        )

    return create_engine(db_url, **engine_kwargs)


def _create_resilient_engine():
    target_url = (settings.DATABASE_URL or "").strip()
    if not target_url or target_url == "sqlite:///./sanbao_dev.db":
        target_url = _FALLBACK_SQLITE_URL
    elif target_url.startswith("postgres://"):
        # Compatibilidad directa con Render PostgreSQL (postgres:// -> postgresql+psycopg2://)
        target_url = target_url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif target_url.startswith("postgresql://"):
        target_url = target_url.replace("postgresql://", "postgresql+psycopg2://", 1)

    eng = _build_engine(target_url)
    if not target_url.startswith("sqlite"):
        try:
            with eng.connect() as conn:
                conn.exec_driver_sql("SELECT 1")
            return eng
        except Exception as exc:
            logger.warning(
                f"No se pudo conectar a {target_url} ({exc}). "
                f"Activando fallback automático a BD embebida SQLite ({_FALLBACK_SQLITE_URL})."
            )
            return _build_engine(_FALLBACK_SQLITE_URL)
    return eng


engine = _create_resilient_engine()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
Base = declarative_base()

if engine.url.drivername.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def configure_sqlite(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-64000")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA mmap_size=268435456")
        cursor.close()


def get_db() -> Generator[Session, None, None]:
    """Inyector de dependencia FastAPI para obtener una sesión de base de datos."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
