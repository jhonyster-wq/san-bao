import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Agregar backend al PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.core.database import Base
# Importar todos los modelos para que Base.metadata los reconozca
from app.modules.institutional.models import *
from app.modules.academic.models import *
from app.modules.finance.models import *
from app.modules.clinical.models import *
from app.modules.lms.models import *
from app.modules.ecommerce.models import *
from app.modules.hr.models import *
from app.modules.integrations.models import *

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url():
    return settings.DATABASE_URL


def run_migrations_offline() -> None:
    """Ejecuta migraciones en modo 'offline'."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Ejecuta migraciones en modo 'online' conectándose al motor de BD."""
    configuration = config.get_section(config.config_ini_section, {})
    url = get_url()
    configuration["sqlalchemy.url"] = url

    execution_options = {}
    if url.startswith("sqlite"):
        execution_options = {
            "schema_translate_map": {
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
        }

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        execution_options=execution_options,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=not url.startswith("sqlite"),
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
