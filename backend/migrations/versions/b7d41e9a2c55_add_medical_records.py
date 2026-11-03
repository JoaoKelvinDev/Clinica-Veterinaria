"""Prontuário somente-inclusão: registros versionados, pesos, vacinas e auditoria."""

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = "b7d41e9a2c55"
down_revision: str | None = "690ced308c92"
branch_labels: str | None = None
depends_on: str | None = None

TABLES = ("record_entries", "weight_records", "vaccine_records", "audit_logs")


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


def links(table: str, prefix: str) -> list[sa.Constraint]:
    return [
        sa.UniqueConstraint("clinic_id", "id", name=f"uq_{prefix}_clinic_id"),
        sa.UniqueConstraint("clinic_id", "id", "patient_id", name=f"uq_{prefix}_patient"),
        sa.UniqueConstraint("clinic_id", "supersedes_id", name=f"uq_{prefix}_supersedes"),
        sa.ForeignKeyConstraint(
            ["clinic_id", "patient_id"], ["vetsys.patients.clinic_id", "vetsys.patients.id"]
        ),
        sa.ForeignKeyConstraint(
            ["clinic_id", "author_id"], ["vetsys.users.clinic_id", "vetsys.users.id"]
        ),
        sa.ForeignKeyConstraint(
            ["clinic_id", "supersedes_id", "patient_id"],
            [f"vetsys.{table}.clinic_id", f"vetsys.{table}.id", f"vetsys.{table}.patient_id"],
        ),
    ]


def encounter_link() -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["clinic_id", "encounter_id", "patient_id"],
        ["vetsys.encounters.clinic_id", "vetsys.encounters.id", "vetsys.encounters.patient_id"],
    )


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_encounter_patient", "encounters", ["clinic_id", "id", "patient_id"], schema="vetsys"
    )
    op.create_table(
        "record_entries",
        *common(),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("root_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("supersedes_id", sa.Uuid()),
        sa.Column("correction_reason", sa.String(500)),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("author_name", sa.String(200), nullable=False),
        sa.Column("author_crmv", sa.String(40), nullable=False),
        sa.Column("location", sa.String(200), nullable=False),
        sa.Column("complaint", sa.Text(), nullable=False),
        sa.Column("general_state", sa.Text(), nullable=False),
        sa.Column("findings", sa.Text()),
        sa.Column("presumptive_diagnosis", sa.Text(), nullable=False),
        sa.Column("conclusive_diagnosis", sa.Text()),
        sa.Column("procedures", sa.Text()),
        sa.Column("prescription", sa.Text()),
        sa.Column("follow_up", sa.String(500)),
        *links("record_entries", "record_entry"),
        encounter_link(),
        sa.UniqueConstraint("clinic_id", "root_id", "version", name="uq_record_entry_version"),
        sa.CheckConstraint("version >= 1", name="record_entry_version"),
        sa.CheckConstraint(
            "(version = 1 AND supersedes_id IS NULL AND correction_reason IS NULL) OR "
            "(version > 1 AND supersedes_id IS NOT NULL AND correction_reason IS NOT NULL)",
            name="record_entry_correction",
        ),
        schema="vetsys",
    )
    op.create_table(
        "weight_records",
        *common(),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("weight_grams", sa.Integer(), nullable=False),
        sa.Column("supersedes_id", sa.Uuid()),
        sa.Column("correction_reason", sa.String(500)),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("author_name", sa.String(200), nullable=False),
        *links("weight_records", "weight_record"),
        sa.CheckConstraint("weight_grams > 0 AND weight_grams <= 5000000", name="weight_range"),
        sa.CheckConstraint(
            "(supersedes_id IS NULL) = (correction_reason IS NULL)", name="weight_correction"
        ),
        schema="vetsys",
    )
    op.create_table(
        "vaccine_records",
        *common(),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("vaccine_name", sa.String(200), nullable=False),
        sa.Column("batch", sa.String(80), nullable=False),
        sa.Column("manufacturer", sa.String(200), nullable=False),
        sa.Column("dose", sa.String(80), nullable=False),
        sa.Column("manufactured_on", sa.Date(), nullable=False),
        sa.Column("expires_on", sa.Date(), nullable=False),
        sa.Column("next_dose_on", sa.Date()),
        sa.Column("supersedes_id", sa.Uuid()),
        sa.Column("correction_reason", sa.String(500)),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("author_name", sa.String(200), nullable=False),
        sa.Column("author_crmv", sa.String(40), nullable=False),
        *links("vaccine_records", "vaccine_record"),
        encounter_link(),
        sa.CheckConstraint("expires_on >= manufactured_on", name="vaccine_validity_order"),
        sa.CheckConstraint(
            "(supersedes_id IS NULL) = (correction_reason IS NULL)", name="vaccine_correction"
        ),
        schema="vetsys",
    )
    op.create_table(
        "audit_logs",
        *common(),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("entity", sa.String(30), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["clinic_id", "actor_id"], ["vetsys.users.clinic_id", "vetsys.users.id"]
        ),
        sa.CheckConstraint("action IN ('read','create','correct')", name="audit_action"),
        schema="vetsys",
    )
    for table, prefix in (
        ("record_entries", "record_entry"),
        ("weight_records", "weight_record"),
        ("vaccine_records", "vaccine_record"),
        ("audit_logs", "audit_log"),
    ):
        op.create_index(f"ix_vetsys_{table}_clinic_id", table, ["clinic_id"], schema="vetsys")
        op.create_index(
            f"ix_{prefix}_patient",
            table,
            ["clinic_id", "patient_id", "created_at"],
            schema="vetsys",
        )
    op.create_index(
        "ix_record_entry_encounter",
        "record_entries",
        ["clinic_id", "encounter_id"],
        schema="vetsys",
    )

    tenant = "clinic_id = nullif((SELECT current_setting('vetsys.clinic_id', true)), '')::uuid"
    role = "(SELECT current_setting('vetsys.role', true))"
    user = "nullif((SELECT current_setting('vetsys.user_id', true)), '')::uuid"
    clinical_reader = f"{role} IN ('admin','veterinarian','assistant')"
    for table in TABLES:
        op.execute(f"ALTER TABLE vetsys.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE vetsys.{table} FORCE ROW LEVEL SECURITY")
        # Somente leitura e inclusão: o papel da aplicação não altera nem apaga prontuário.
        op.execute(f"GRANT SELECT, INSERT ON vetsys.{table} TO vetsys_app")
    for table in ("record_entries", "weight_records", "vaccine_records"):
        op.execute(
            f"CREATE POLICY tenant_read ON vetsys.{table} FOR SELECT TO vetsys_app "
            f"USING ({tenant} AND {clinical_reader})"
        )
    for table in ("record_entries", "vaccine_records"):
        op.execute(
            f"CREATE POLICY tenant_insert ON vetsys.{table} FOR INSERT TO vetsys_app "
            f"WITH CHECK ({tenant} AND {role} = 'veterinarian' AND author_id = {user} "
            "AND deleted_at IS NULL)"
        )
    op.execute(
        "CREATE POLICY tenant_insert ON vetsys.weight_records FOR INSERT TO vetsys_app "
        f"WITH CHECK ({tenant} AND {role} IN ('veterinarian','assistant') "
        f"AND author_id = {user} AND deleted_at IS NULL)"
    )
    op.execute(
        "CREATE POLICY tenant_read ON vetsys.audit_logs FOR SELECT TO vetsys_app "
        f"USING ({tenant} AND {role} = 'admin')"
    )
    op.execute(
        "CREATE POLICY tenant_insert ON vetsys.audit_logs FOR INSERT TO vetsys_app "
        f"WITH CHECK ({tenant} AND actor_id = {user} AND deleted_at IS NULL)"
    )

    # Bloqueia alteração e exclusão inclusive por papéis administrativos do banco.
    op.execute("""CREATE FUNCTION vetsys.reject_record_change() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
        BEGIN
            RAISE EXCEPTION 'Medical records are append-only' USING ERRCODE = '42501';
        END $$""")
    op.execute("REVOKE ALL ON FUNCTION vetsys.reject_record_change() FROM PUBLIC")
    for table in TABLES:
        op.execute(
            f"CREATE TRIGGER reject_change BEFORE UPDATE OR DELETE ON vetsys.{table} "
            "FOR EACH ROW EXECUTE FUNCTION vetsys.reject_record_change()"
        )
    # Uma correção continua a mesma cadeia: mesmo atendimento, mesmo autor, versão seguinte.
    op.execute("""CREATE FUNCTION vetsys.check_record_version() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
        DECLARE previous vetsys.record_entries;
        BEGIN
            IF NEW.supersedes_id IS NULL THEN
                IF NEW.version <> 1 OR NEW.root_id <> NEW.id THEN
                    RAISE EXCEPTION 'Invalid first version' USING ERRCODE = '23514';
                END IF;
                RETURN NEW;
            END IF;
            SELECT * INTO previous FROM vetsys.record_entries
                WHERE clinic_id = NEW.clinic_id AND id = NEW.supersedes_id;
            IF NOT FOUND OR NEW.version <> previous.version + 1
                OR NEW.root_id <> previous.root_id
                OR NEW.encounter_id <> previous.encounter_id
                OR NEW.author_id <> previous.author_id
            THEN RAISE EXCEPTION 'Invalid record correction' USING ERRCODE = '23514'; END IF;
            RETURN NEW;
        END $$""")
    op.execute("REVOKE ALL ON FUNCTION vetsys.check_record_version() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER check_version BEFORE INSERT ON vetsys.record_entries "
        "FOR EACH ROW EXECUTE FUNCTION vetsys.check_record_version()"
    )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table, schema="vetsys")
    op.execute("DROP FUNCTION vetsys.check_record_version()")
    op.execute("DROP FUNCTION vetsys.reject_record_change()")
    op.drop_constraint("uq_encounter_patient", "encounters", type_="unique", schema="vetsys")
