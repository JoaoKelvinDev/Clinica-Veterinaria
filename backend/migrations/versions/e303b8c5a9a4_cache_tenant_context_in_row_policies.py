"""Avaliar o contexto de RLS uma vez por instrução SQL."""

from alembic import op

revision: str = "e303b8c5a9a4"
down_revision: str | None = "cbe8339a86dd"
branch_labels: str | None = None
depends_on: str | None = None


def update_policies(*, cached: bool) -> None:
    def setting(name: str) -> str:
        value = f"current_setting('vetsys.{name}', true)"
        return f"(SELECT {value})" if cached else value

    clinic = f"nullif({setting('clinic_id')}, '')::uuid"
    identity = f"nullif({setting('auth_id')}, '')::uuid"
    role = setting("role")
    tenant = f"clinic_id = {clinic}"
    admin = f"{role} = 'admin'"
    op.execute(f"ALTER POLICY clinic_read ON vetsys.clinics USING ({tenant})")
    op.execute(f"ALTER POLICY user_read ON vetsys.users USING ({tenant} OR auth_id = {identity})")
    for table in ("clinics", "users"):
        op.execute(
            f"ALTER POLICY tenant_update ON vetsys.{table} "
            f"USING ({tenant} AND {admin}) WITH CHECK ({tenant} AND {admin})"
        )


def upgrade() -> None:
    update_policies(cached=True)


def downgrade() -> None:
    update_policies(cached=False)
