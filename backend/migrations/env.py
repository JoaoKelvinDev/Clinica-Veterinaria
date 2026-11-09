import os

from alembic import context
from sqlalchemy import create_engine, pool, text

from app.core.db import Base
from app.modules.ai_scribe import models as scribe_models  # noqa: F401
from app.modules.clinics import models  # noqa: F401
from app.modules.messaging import models as messaging_models  # noqa: F401
from app.modules.patients import models as patient_models  # noqa: F401
from app.modules.quotes import models as quote_models  # noqa: F401
from app.modules.records import models as record_models  # noqa: F401
from app.modules.scheduling import models as scheduling_models  # noqa: F401
from app.modules.tutors import models as tutor_models  # noqa: F401

config = context.config
url = os.environ.get("MIGRATION_DATABASE_URL") or config.get_main_option("sqlalchemy.url")
if not url or url.startswith("driver:"):
    raise RuntimeError("Configure MIGRATION_DATABASE_URL para executar as migrações.")

if context.is_offline_mode():
    context.configure(
        url=url,
        target_metadata=Base.metadata,
        literal_binds=True,
        version_table_schema="vetsys",
        include_schemas=True,
    )
    with context.begin_transaction():
        context.execute("CREATE SCHEMA IF NOT EXISTS vetsys")
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool, hide_parameters=True)
    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS vetsys"))
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            version_table_schema="vetsys",
            include_schemas=True,
        )
        with context.begin_transaction():
            context.run_migrations()
