"""Clínicas, usuários e políticas de isolamento."""

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = "cbe8339a86dd"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def common_columns() -> list[sa.Column[UUID] | sa.Column[datetime]]:
    return [
        sa.Column[UUID]("id", sa.Uuid(), primary_key=True),
        sa.Column[UUID]("clinic_id", sa.Uuid(), nullable=False),
        sa.Column[datetime](
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column[datetime](
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column[datetime]("deleted_at", sa.DateTime(timezone=True)),
    ]


def upgrade() -> None:
    op.execute("REVOKE ALL ON SCHEMA vetsys FROM PUBLIC")
    op.execute("""DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vetsys_app') THEN
            CREATE ROLE vetsys_app NOLOGIN NOSUPERUSER NOBYPASSRLS NOINHERIT;
        END IF;
    END $$""")
    op.create_table(
        "clinics",
        *common_columns(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.CheckConstraint("clinic_id = id", name="clinic_is_tenant"),
        schema="vetsys",
    )
    op.create_table(
        "users",
        *common_columns(),
        sa.Column("auth_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("role", sa.String(12), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("crmv", sa.String(30)),
        sa.Column("crmv_state", sa.String(2)),
        sa.ForeignKeyConstraint(["clinic_id"], ["vetsys.clinics.id"]),
        sa.CheckConstraint(
            "role IN ('admin','veterinarian','assistant','reception')", name="user_role"
        ),
        sa.CheckConstraint(
            "role <> 'veterinarian' OR (crmv IS NOT NULL AND crmv_state IS NOT NULL)",
            name="veterinarian_has_crmv",
        ),
        schema="vetsys",
    )
    for table in ("clinics", "users"):
        op.create_index(f"ix_vetsys_{table}_clinic_id", table, ["clinic_id"], schema="vetsys")
        op.execute(f"ALTER TABLE vetsys.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE vetsys.{table} FORCE ROW LEVEL SECURITY")
    tenant = "clinic_id = nullif(current_setting('vetsys.clinic_id', true), '')::uuid"
    identity = "auth_id = nullif(current_setting('vetsys.auth_id', true), '')::uuid"
    admin = "current_setting('vetsys.role', true) = 'admin'"
    op.execute(
        f"CREATE POLICY clinic_read ON vetsys.clinics FOR SELECT TO vetsys_app USING ({tenant})"
    )
    op.execute(
        "CREATE POLICY user_read ON vetsys.users FOR SELECT TO vetsys_app "
        f"USING ({tenant} OR {identity})"
    )
    for table in ("clinics", "users"):
        op.execute(
            f"CREATE POLICY tenant_update ON vetsys.{table} FOR UPDATE TO vetsys_app "
            f"USING ({tenant} AND {admin}) WITH CHECK ({tenant} AND {admin})"
        )
    op.execute("GRANT USAGE ON SCHEMA vetsys TO vetsys_app")
    op.execute("GRANT SELECT ON vetsys.clinics, vetsys.users TO vetsys_app")
    op.execute("GRANT UPDATE (name, updated_at) ON vetsys.clinics TO vetsys_app")
    op.execute(
        "GRANT UPDATE (name, role, active, crmv, crmv_state, updated_at) "
        "ON vetsys.users TO vetsys_app"
    )


def downgrade() -> None:
    op.drop_table("users", schema="vetsys")
    op.drop_table("clinics", schema="vetsys")
    # O papel pode ser usado por outro banco local; não removê-lo neste downgrade.
