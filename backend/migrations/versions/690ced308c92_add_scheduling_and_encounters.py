"""Agenda sem sobreposição e identificação dos atendimentos."""

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = "690ced308c92"
down_revision: str | None = "f62c813aa353"
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
    op.execute("CREATE SCHEMA IF NOT EXISTS extensions")
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA extensions")
    op.execute("GRANT USAGE ON SCHEMA extensions TO vetsys_app")
    op.create_unique_constraint("uq_user_clinic_id", "users", ["clinic_id", "id"], schema="vetsys")
    op.create_table(
        "appointments",
        *common(),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("veterinarian_id", sa.Uuid(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kind", sa.String(80), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="scheduled"),
        sa.UniqueConstraint("clinic_id", "id", name="uq_appointment_clinic_id"),
        sa.UniqueConstraint(
            "clinic_id", "id", "patient_id", "veterinarian_id", name="uq_appointment_identity"
        ),
        sa.ForeignKeyConstraint(
            ["clinic_id", "patient_id"], ["vetsys.patients.clinic_id", "vetsys.patients.id"]
        ),
        sa.ForeignKeyConstraint(
            ["clinic_id", "veterinarian_id"], ["vetsys.users.clinic_id", "vetsys.users.id"]
        ),
        sa.CheckConstraint("ends_at > starts_at", name="appointment_positive_duration"),
        sa.CheckConstraint(
            "status IN ('scheduled','confirmed','in_progress','completed','cancelled','no_show')",
            name="appointment_status",
        ),
        schema="vetsys",
    )
    op.execute("""ALTER TABLE vetsys.appointments ADD CONSTRAINT no_veterinarian_overlap
        EXCLUDE USING gist (clinic_id extensions.gist_uuid_ops WITH =,
        veterinarian_id extensions.gist_uuid_ops WITH =,
        tstzrange(starts_at, ends_at, '[)') WITH &&)
        WHERE (status NOT IN ('cancelled','no_show'))""")
    op.create_table(
        "encounters",
        *common(),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("veterinarian_id", sa.Uuid(), nullable=False),
        sa.Column("appointment_id", sa.Uuid()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("clinic_id", "id", name="uq_encounter_clinic_id"),
        sa.UniqueConstraint("clinic_id", "appointment_id", name="uq_encounter_appointment"),
        sa.ForeignKeyConstraint(
            ["clinic_id", "patient_id"], ["vetsys.patients.clinic_id", "vetsys.patients.id"]
        ),
        sa.ForeignKeyConstraint(
            ["clinic_id", "veterinarian_id"], ["vetsys.users.clinic_id", "vetsys.users.id"]
        ),
        sa.ForeignKeyConstraint(
            ["clinic_id", "appointment_id", "patient_id", "veterinarian_id"],
            [
                "vetsys.appointments.clinic_id",
                "vetsys.appointments.id",
                "vetsys.appointments.patient_id",
                "vetsys.appointments.veterinarian_id",
            ],
        ),
        sa.CheckConstraint(
            "completed_at IS NULL OR completed_at >= started_at", name="encounter_completion_order"
        ),
        schema="vetsys",
    )
    for table, prefix, date_field in (
        ("appointments", "appointment", "starts_at"),
        ("encounters", "encounter", "started_at"),
    ):
        op.create_index(f"ix_vetsys_{table}_clinic_id", table, ["clinic_id"], schema="vetsys")
        op.create_index(f"ix_{prefix}_day", table, ["clinic_id", date_field], schema="vetsys")
        op.create_index(
            f"ix_{prefix}_veterinarian",
            table,
            ["clinic_id", "veterinarian_id", date_field],
            schema="vetsys",
        )
        op.create_index(f"ix_{prefix}_patient", table, ["clinic_id", "patient_id"], schema="vetsys")
        op.execute(f"ALTER TABLE vetsys.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE vetsys.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"GRANT SELECT, INSERT ON vetsys.{table} TO vetsys_app")
    tenant = "clinic_id = nullif((SELECT current_setting('vetsys.clinic_id', true)), '')::uuid"
    writer = "(SELECT current_setting('vetsys.role', true)) IN ('admin','reception')"
    vet = (
        "(SELECT current_setting('vetsys.role', true)) = 'veterinarian' "
        "AND veterinarian_id = nullif((SELECT current_setting('vetsys.user_id', true)), '')::uuid"
    )
    for table in ("appointments", "encounters"):
        op.execute(
            f"CREATE POLICY tenant_read ON vetsys.{table} FOR SELECT TO vetsys_app USING ({tenant})"
        )
    op.execute(
        "CREATE POLICY tenant_insert ON vetsys.appointments FOR INSERT TO vetsys_app "
        f"WITH CHECK ({tenant} AND {writer} AND status = 'scheduled' AND deleted_at IS NULL)"
    )
    op.execute(
        "CREATE POLICY tenant_update ON vetsys.appointments FOR UPDATE TO vetsys_app "
        f"USING ({tenant} AND (({writer} AND status IN ('scheduled','confirmed')) "
        f"OR ({vet} AND status IN ('scheduled','confirmed','in_progress')))) "
        f"WITH CHECK ({tenant} AND "
        f"(({writer} AND status IN ('scheduled','confirmed','cancelled','no_show')) "
        f"OR ({vet} AND status IN ('in_progress','completed'))))"
    )
    op.execute(
        "CREATE POLICY tenant_insert ON vetsys.encounters FOR INSERT TO vetsys_app "
        f"WITH CHECK ({tenant} AND {vet} AND completed_at IS NULL AND deleted_at IS NULL)"
    )
    op.execute(
        "CREATE POLICY tenant_update ON vetsys.encounters FOR UPDATE TO vetsys_app "
        f"USING ({tenant} AND {vet} AND completed_at IS NULL) WITH CHECK ({tenant} AND {vet})"
    )
    op.execute(
        "GRANT UPDATE (patient_id,veterinarian_id,starts_at,ends_at,kind,status,updated_at) "
        "ON vetsys.appointments TO vetsys_app"
    )
    op.execute("GRANT UPDATE (completed_at,updated_at) ON vetsys.encounters TO vetsys_app")
    # Mantém os identificadores e horários da agenda após começar o atendimento.
    op.execute("""CREATE FUNCTION vetsys.preserve_started_appointment() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
        BEGIN
            IF OLD.status IN ('in_progress','completed','cancelled','no_show') AND
                ROW(OLD.patient_id,OLD.veterinarian_id,OLD.starts_at,OLD.ends_at,OLD.kind)
                IS DISTINCT FROM ROW(NEW.patient_id,NEW.veterinarian_id,
                NEW.starts_at,NEW.ends_at,NEW.kind)
            THEN RAISE EXCEPTION 'Appointment identity is frozen' USING ERRCODE = '23514'; END IF;
            RETURN NEW;
        END $$""")
    op.execute("REVOKE ALL ON FUNCTION vetsys.preserve_started_appointment() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER preserve_started_appointment BEFORE UPDATE ON vetsys.appointments "
        "FOR EACH ROW EXECUTE FUNCTION vetsys.preserve_started_appointment()"
    )


def downgrade() -> None:
    op.drop_table("encounters", schema="vetsys")
    op.drop_table("appointments", schema="vetsys")
    op.execute("DROP FUNCTION vetsys.preserve_started_appointment()")
    op.drop_constraint("uq_user_clinic_id", "users", type_="unique", schema="vetsys")
    # A extensão pode ser compartilhada por outras tabelas locais; não removê-la.
