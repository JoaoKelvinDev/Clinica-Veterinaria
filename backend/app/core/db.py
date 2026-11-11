from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, create_engine, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.core.errors import ServiceUnavailable


class Base(DeclarativeBase):
    pass


class TenantModel(Base):
    __abstract__ = True

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class Database:
    def __init__(self, url: str, *, serverless: bool = False) -> None:
        if serverless:
            # Cada instância deve limitar conexões ao pooler; prepared statements não
            # sobrevivem à troca de conexão do Supavisor em modo transação.
            self.engine = create_engine(
                url,
                pool_pre_ping=True,
                hide_parameters=True,
                pool_size=1,
                max_overflow=0,
                connect_args={"sslmode": "require", "prepare_threshold": None},
            )
        else:
            self.engine = create_engine(url, pool_pre_ping=True, hide_parameters=True)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)


def set_context(session: Session, name: str, value: str) -> None:
    session.execute(text("SELECT set_config(:name, :value, true)"), {"name": name, "value": value})


def verify_runtime_role(session: Session) -> None:
    privileged = session.scalar(
        text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")
    )
    if privileged is not False:
        raise ServiceUnavailable("A conexão da aplicação precisa de um usuário restrito do banco.")
