"""Permite reagendar o envio de um lembrete existente sem ampliar outras permissões."""

from alembic import op

revision: str = "421d5c158269"
down_revision: str | None = "d4a81f6c9e27"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("GRANT UPDATE (due_at) ON vetsys.reminder_jobs TO vetsys_app")


def downgrade() -> None:
    op.execute("REVOKE UPDATE (due_at) ON vetsys.reminder_jobs FROM vetsys_app")
