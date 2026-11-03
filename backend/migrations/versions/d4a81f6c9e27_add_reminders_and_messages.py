"""Lembretes agendados, mensagens com tutores e data de retorno no registro clínico."""

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = "d4a81f6c9e27"
down_revision: str | None = "c91f3a7d2b04"
branch_labels: str | None = None
depends_on: str | None = None


def common() -> list[sa.Column[UUID] | sa.Column[datetime]]:
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
    # Coluna nova numa tabela somente-inclusão: o gatilho bloqueia UPDATE de linhas, não DDL.
    op.add_column("record_entries", sa.Column("follow_up_on", sa.Date()), schema="vetsys")
    op.create_table(
        "reminder_jobs",
        *common(),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="pending"),
        sa.Column("dedupe_key", sa.String(200), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("appointment_id", sa.Uuid()),
        sa.Column("vaccine_record_id", sa.Uuid()),
        sa.Column("record_entry_id", sa.Uuid()),
        sa.Column("outcome", sa.String(200)),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("clinic_id", "dedupe_key", name="uq_reminder_dedupe"),
        sa.ForeignKeyConstraint(
            ["clinic_id", "patient_id"], ["vetsys.patients.clinic_id", "vetsys.patients.id"]
        ),
        sa.ForeignKeyConstraint(
            ["clinic_id", "appointment_id"],
            ["vetsys.appointments.clinic_id", "vetsys.appointments.id"],
        ),
        sa.ForeignKeyConstraint(
            ["clinic_id", "vaccine_record_id"],
            ["vetsys.vaccine_records.clinic_id", "vetsys.vaccine_records.id"],
        ),
        sa.ForeignKeyConstraint(
            ["clinic_id", "record_entry_id"],
            ["vetsys.record_entries.clinic_id", "vetsys.record_entries.id"],
        ),
        sa.CheckConstraint(
            "kind IN ('appointment_confirmation','appointment_reminder','vaccine','follow_up')",
            name="reminder_kind",
        ),
        sa.CheckConstraint(
            "status IN ('pending','sent','skipped','cancelled','failed')", name="reminder_status"
        ),
        sa.CheckConstraint(
            "num_nonnulls(appointment_id, vaccine_record_id, record_entry_id) = 1",
            name="reminder_single_source",
        ),
        schema="vetsys",
    )
    op.create_table(
        "messages",
        *common(),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_message_id", sa.String(200), nullable=False),
        sa.Column("phone", sa.String(16), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("tutor_id", sa.Uuid()),
        sa.Column("patient_id", sa.Uuid()),
        sa.Column("appointment_id", sa.Uuid()),
        sa.Column("reminder_job_id", sa.Uuid()),
        sa.Column("intent", sa.String(10)),
        sa.Column("needs_attention", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("handled_at", sa.DateTime(timezone=True)),
        sa.Column("handled_by", sa.Uuid()),
        sa.UniqueConstraint("provider", "provider_message_id", name="uq_message_provider_id"),
        sa.ForeignKeyConstraint(
            ["clinic_id", "tutor_id"], ["vetsys.tutors.clinic_id", "vetsys.tutors.id"]
        ),
        sa.ForeignKeyConstraint(
            ["clinic_id", "patient_id"], ["vetsys.patients.clinic_id", "vetsys.patients.id"]
        ),
        sa.ForeignKeyConstraint(
            ["clinic_id", "appointment_id"],
            ["vetsys.appointments.clinic_id", "vetsys.appointments.id"],
        ),
        sa.ForeignKeyConstraint(
            ["clinic_id", "handled_by"], ["vetsys.users.clinic_id", "vetsys.users.id"]
        ),
        sa.CheckConstraint("direction IN ('outbound','inbound')", name="message_direction"),
        sa.CheckConstraint("status IN ('sent','failed','received')", name="message_status"),
        sa.CheckConstraint(
            "intent IS NULL OR intent IN ('confirm','cancel','opt_out','unknown')",
            name="message_intent",
        ),
        schema="vetsys",
    )
    for table in ("reminder_jobs", "messages"):
        op.create_index(f"ix_vetsys_{table}_clinic_id", table, ["clinic_id"], schema="vetsys")
    op.create_index("ix_reminder_due", "reminder_jobs", ["status", "due_at"], schema="vetsys")
    op.create_index(
        "ix_reminder_clinic_due",
        "reminder_jobs",
        ["clinic_id", "status", "due_at"],
        schema="vetsys",
    )
    op.create_index(
        "ix_message_clinic_created", "messages", ["clinic_id", "created_at"], schema="vetsys"
    )
    op.create_index(
        "ix_message_phone", "messages", ["clinic_id", "phone", "created_at"], schema="vetsys"
    )

    tenant = "clinic_id = nullif((SELECT current_setting('vetsys.clinic_id', true)), '')::uuid"
    updatable = {
        "reminder_jobs": "status,outcome,attempts,sent_at,updated_at",
        "messages": "needs_attention,handled_at,handled_by,updated_at",
    }
    for table, columns in updatable.items():
        op.execute(f"ALTER TABLE vetsys.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE vetsys.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"GRANT SELECT, INSERT ON vetsys.{table} TO vetsys_app")
        op.execute(f"GRANT UPDATE ({columns}) ON vetsys.{table} TO vetsys_app")
        op.execute(
            f"CREATE POLICY tenant_read ON vetsys.{table} FOR SELECT TO vetsys_app USING ({tenant})"
        )
        op.execute(
            f"CREATE POLICY tenant_insert ON vetsys.{table} FOR INSERT TO vetsys_app "
            f"WITH CHECK ({tenant} AND deleted_at IS NULL)"
        )
        op.execute(
            f"CREATE POLICY tenant_update ON vetsys.{table} FOR UPDATE TO vetsys_app "
            f"USING ({tenant}) WITH CHECK ({tenant})"
        )
    # O worker precisa saber quais clínicas têm lembretes vencidos antes de assumir o
    # contexto de cada uma; a função devolve só identificadores, nada de conteúdo.
    op.execute("""CREATE FUNCTION vetsys.clinics_with_due_reminders(at timestamptz)
        RETURNS SETOF uuid LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
            SELECT DISTINCT clinic_id FROM vetsys.reminder_jobs
            WHERE status = 'pending' AND due_at <= at
        $$""")
    op.execute("REVOKE ALL ON FUNCTION vetsys.clinics_with_due_reminders(timestamptz) FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION vetsys.clinics_with_due_reminders(timestamptz) TO vetsys_app"
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION vetsys.clinics_with_due_reminders(timestamptz)")
    op.drop_table("messages", schema="vetsys")
    op.drop_table("reminder_jobs", schema="vetsys")
    op.drop_column("record_entries", "follow_up_on", schema="vetsys")
