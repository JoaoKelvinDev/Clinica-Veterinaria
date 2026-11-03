"""Documentos do paciente (laudos e históricos externos), somente-inclusão."""

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = "c91f3a7d2b04"
down_revision: str | None = "b7d41e9a2c55"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "patient_documents",
        sa.Column[UUID]("id", sa.Uuid(), primary_key=True),
        sa.Column[UUID]("clinic_id", sa.Uuid(), nullable=False),
        sa.Column[datetime](
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column[datetime](
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column[datetime]("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid()),
        sa.Column("root_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("supersedes_id", sa.Uuid()),
        sa.Column("correction_reason", sa.String(500)),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("origin_name", sa.String(200), nullable=False),
        sa.Column("origin_crmv", sa.String(40)),
        sa.Column("document_date", sa.Date(), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("file_key", sa.String(300)),
        sa.Column("file_name", sa.String(200)),
        sa.Column("content_type", sa.String(40)),
        sa.Column("size_bytes", sa.Integer()),
        sa.Column("sha256", sa.String(64)),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("author_name", sa.String(200), nullable=False),
        sa.Column("author_crmv", sa.String(40)),
        sa.UniqueConstraint("clinic_id", "id", name="uq_patient_document_clinic_id"),
        sa.UniqueConstraint("clinic_id", "id", "patient_id", name="uq_patient_document_patient"),
        sa.UniqueConstraint("clinic_id", "supersedes_id", name="uq_patient_document_supersedes"),
        sa.UniqueConstraint("clinic_id", "root_id", "version", name="uq_patient_document_version"),
        sa.ForeignKeyConstraint(
            ["clinic_id", "patient_id"], ["vetsys.patients.clinic_id", "vetsys.patients.id"]
        ),
        sa.ForeignKeyConstraint(
            ["clinic_id", "author_id"], ["vetsys.users.clinic_id", "vetsys.users.id"]
        ),
        sa.ForeignKeyConstraint(
            ["clinic_id", "encounter_id", "patient_id"],
            ["vetsys.encounters.clinic_id", "vetsys.encounters.id", "vetsys.encounters.patient_id"],
        ),
        sa.ForeignKeyConstraint(
            ["clinic_id", "supersedes_id", "patient_id"],
            [
                "vetsys.patient_documents.clinic_id",
                "vetsys.patient_documents.id",
                "vetsys.patient_documents.patient_id",
            ],
        ),
        sa.CheckConstraint(
            "kind IN ('lab_report','external_history','prescription','other')",
            name="patient_document_kind",
        ),
        sa.CheckConstraint("summary IS NOT NULL OR file_key IS NOT NULL", name="document_content"),
        sa.CheckConstraint(
            "(file_key IS NULL) = (file_name IS NULL) AND (file_key IS NULL) = (sha256 IS NULL) "
            "AND (file_key IS NULL) = (size_bytes IS NULL) "
            "AND (file_key IS NULL) = (content_type IS NULL)",
            name="document_file_metadata",
        ),
        sa.CheckConstraint(
            "content_type IS NULL OR content_type IN ('application/pdf','image/jpeg','image/png')",
            name="document_content_type",
        ),
        sa.CheckConstraint(
            "size_bytes IS NULL OR (size_bytes > 0 AND size_bytes <= 10485760)",
            name="document_size",
        ),
        sa.CheckConstraint("sha256 IS NULL OR sha256 ~ '^[0-9a-f]{64}$'", name="document_sha256"),
        sa.CheckConstraint(
            "(version = 1 AND supersedes_id IS NULL AND correction_reason IS NULL) OR "
            "(version > 1 AND supersedes_id IS NOT NULL AND correction_reason IS NOT NULL)",
            name="document_correction",
        ),
        schema="vetsys",
    )
    op.create_index(
        "ix_vetsys_patient_documents_clinic_id", "patient_documents", ["clinic_id"], schema="vetsys"
    )
    op.create_index(
        "ix_patient_document_patient",
        "patient_documents",
        ["clinic_id", "patient_id", "created_at"],
        schema="vetsys",
    )

    tenant = "clinic_id = nullif((SELECT current_setting('vetsys.clinic_id', true)), '')::uuid"
    role = "(SELECT current_setting('vetsys.role', true))"
    user = "nullif((SELECT current_setting('vetsys.user_id', true)), '')::uuid"
    op.execute("ALTER TABLE vetsys.patient_documents ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE vetsys.patient_documents FORCE ROW LEVEL SECURITY")
    op.execute("GRANT SELECT, INSERT ON vetsys.patient_documents TO vetsys_app")
    op.execute(
        "CREATE POLICY tenant_read ON vetsys.patient_documents FOR SELECT TO vetsys_app "
        f"USING ({tenant} AND {role} IN ('admin','veterinarian','assistant'))"
    )
    op.execute(
        "CREATE POLICY tenant_insert ON vetsys.patient_documents FOR INSERT TO vetsys_app "
        f"WITH CHECK ({tenant} AND {role} IN ('veterinarian','assistant') "
        f"AND author_id = {user} AND deleted_at IS NULL)"
    )
    op.execute(
        "CREATE TRIGGER reject_change BEFORE UPDATE OR DELETE ON vetsys.patient_documents "
        "FOR EACH ROW EXECUTE FUNCTION vetsys.reject_record_change()"
    )
    # Correção continua a cadeia: mesmo paciente e autor, versão seguinte.
    op.execute("""CREATE FUNCTION vetsys.check_document_version() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
        DECLARE previous vetsys.patient_documents;
        BEGIN
            IF NEW.supersedes_id IS NULL THEN
                IF NEW.version <> 1 OR NEW.root_id <> NEW.id THEN
                    RAISE EXCEPTION 'Invalid first version' USING ERRCODE = '23514';
                END IF;
                RETURN NEW;
            END IF;
            SELECT * INTO previous FROM vetsys.patient_documents
                WHERE clinic_id = NEW.clinic_id AND id = NEW.supersedes_id;
            IF NOT FOUND OR NEW.version <> previous.version + 1
                OR NEW.root_id <> previous.root_id
                OR NEW.author_id <> previous.author_id
            THEN RAISE EXCEPTION 'Invalid document correction' USING ERRCODE = '23514'; END IF;
            RETURN NEW;
        END $$""")
    op.execute("REVOKE ALL ON FUNCTION vetsys.check_document_version() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER check_version BEFORE INSERT ON vetsys.patient_documents "
        "FOR EACH ROW EXECUTE FUNCTION vetsys.check_document_version()"
    )


def downgrade() -> None:
    op.drop_table("patient_documents", schema="vetsys")
    op.execute("DROP FUNCTION vetsys.check_document_version()")
