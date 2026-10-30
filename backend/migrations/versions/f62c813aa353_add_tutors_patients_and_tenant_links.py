"""Cadastros de tutores, pacientes e vínculos isolados por clínica."""

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = "f62c813aa353"
down_revision: str | None = "e303b8c5a9a4"
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
    op.create_table(
        "tutors",
        *common(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("phone", sa.String(16)),
        sa.Column("document", sa.String(30)),
        sa.Column("address", sa.String(500)),
        sa.Column("whatsapp_opt_in", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("whatsapp_opt_in_at", sa.DateTime(timezone=True)),
        sa.Column("whatsapp_opt_in_source", sa.String(200)),
        sa.Column("whatsapp_opt_out_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["clinic_id"], ["vetsys.clinics.id"]),
        sa.UniqueConstraint("clinic_id", "id", name="uq_tutor_clinic_id"),
        sa.CheckConstraint(
            "NOT whatsapp_opt_in OR (phone IS NOT NULL AND whatsapp_opt_in_at IS NOT NULL "
            "AND whatsapp_opt_in_source IS NOT NULL)",
            name="valid_whatsapp_consent",
        ),
        schema="vetsys",
    )
    op.create_table(
        "patients",
        *common(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("species", sa.String(80), nullable=False),
        sa.Column("breed", sa.String(120)),
        sa.Column("sex", sa.String(7), nullable=False, server_default="unknown"),
        sa.Column("neutered", sa.Boolean()),
        sa.Column("birth_date", sa.Date()),
        sa.Column("estimated_age_months", sa.Integer()),
        sa.Column("coat", sa.String(120)),
        sa.Column("microchip", sa.String(50)),
        sa.Column("notes", sa.String(2000)),
        sa.ForeignKeyConstraint(["clinic_id"], ["vetsys.clinics.id"]),
        sa.UniqueConstraint("clinic_id", "id", name="uq_patient_clinic_id"),
        sa.CheckConstraint("sex IN ('male','female','unknown')", name="patient_sex"),
        sa.CheckConstraint(
            "birth_date IS NULL OR estimated_age_months IS NULL", name="one_age_source"
        ),
        sa.CheckConstraint("estimated_age_months >= 0", name="non_negative_age"),
        schema="vetsys",
    )
    op.create_table(
        "tutor_patients",
        *common(),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("tutor_id", sa.Uuid(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(
            ["clinic_id", "patient_id"], ["vetsys.patients.clinic_id", "vetsys.patients.id"]
        ),
        sa.ForeignKeyConstraint(
            ["clinic_id", "tutor_id"], ["vetsys.tutors.clinic_id", "vetsys.tutors.id"]
        ),
        sa.UniqueConstraint("clinic_id", "patient_id", "tutor_id", name="uq_tutor_patient_pair"),
        schema="vetsys",
    )
    op.create_index(
        "uq_patient_active_microchip",
        "patients",
        ["clinic_id", "microchip"],
        unique=True,
        schema="vetsys",
        postgresql_where=sa.text("microchip IS NOT NULL AND deleted_at IS NULL"),
    )
    op.create_index(
        "uq_patient_primary_tutor",
        "tutor_patients",
        ["clinic_id", "patient_id"],
        unique=True,
        schema="vetsys",
        postgresql_where=sa.text("is_primary AND deleted_at IS NULL"),
    )
    op.create_index(
        "ix_link_patient", "tutor_patients", ["clinic_id", "patient_id"], schema="vetsys"
    )
    op.create_index("ix_link_tutor", "tutor_patients", ["clinic_id", "tutor_id"], schema="vetsys")
    tenant = "clinic_id = nullif((SELECT current_setting('vetsys.clinic_id', true)), '')::uuid"
    writer = "(SELECT current_setting('vetsys.role', true)) IN ('admin','reception')"
    fields = {
        "tutors": (
            "name,phone,document,address,whatsapp_opt_in,whatsapp_opt_in_at,"
            "whatsapp_opt_in_source,whatsapp_opt_out_at,updated_at,deleted_at"
        ),
        "patients": (
            "name,species,breed,sex,neutered,birth_date,estimated_age_months,"
            "coat,microchip,notes,updated_at,deleted_at"
        ),
        "tutor_patients": "is_primary,updated_at,deleted_at",
    }
    for table, columns in fields.items():
        op.create_index(f"ix_vetsys_{table}_clinic_id", table, ["clinic_id"], schema="vetsys")
        op.execute(f"ALTER TABLE vetsys.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE vetsys.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_read ON vetsys.{table} FOR SELECT TO vetsys_app USING ({tenant})"
        )
        op.execute(
            f"CREATE POLICY tenant_insert ON vetsys.{table} FOR INSERT TO vetsys_app "
            f"WITH CHECK ({tenant} AND {writer})"
        )
        op.execute(
            f"CREATE POLICY tenant_update ON vetsys.{table} FOR UPDATE TO vetsys_app "
            f"USING ({tenant} AND {writer}) WITH CHECK ({tenant} AND {writer})"
        )
        op.execute(f"GRANT SELECT, INSERT ON vetsys.{table} TO vetsys_app")
        op.execute(f"GRANT UPDATE ({columns}) ON vetsys.{table} TO vetsys_app")


def downgrade() -> None:
    for table in ("tutor_patients", "patients", "tutors"):
        op.drop_table(table, schema="vetsys")
