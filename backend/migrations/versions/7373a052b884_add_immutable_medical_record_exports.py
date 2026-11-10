"""add immutable medical record exports

Revision ID: 7373a052b884
Revises: 9986a520b54b
Create Date: 2026-11-10 15:17:47.368999

"""

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7373a052b884"
down_revision = "9986a520b54b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE vetsys.record_exports (
        id uuid PRIMARY KEY, clinic_id uuid NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now(), deleted_at timestamptz,
        patient_id uuid NOT NULL, tutor_id uuid NOT NULL, author_id uuid NOT NULL,
        author_name varchar(200) NOT NULL, author_crmv varchar(40) NOT NULL,
        tutor_name varchar(200) NOT NULL, file_key varchar(300) NOT NULL UNIQUE,
        sha256 varchar(64) NOT NULL, size_bytes integer NOT NULL,
        attachment_count integer NOT NULL, missing_file_count integer NOT NULL,
        attachments jsonb NOT NULL,
        FOREIGN KEY (clinic_id,patient_id) REFERENCES vetsys.patients(clinic_id,id),
        FOREIGN KEY (clinic_id,tutor_id) REFERENCES vetsys.tutors(clinic_id,id),
        FOREIGN KEY (clinic_id,author_id) REFERENCES vetsys.users(clinic_id,id),
        CONSTRAINT record_export_preserved CHECK (deleted_at IS NULL),
        CONSTRAINT record_export_hash CHECK (sha256 ~ '^[0-9a-f]{64}$'),
        CONSTRAINT record_export_size CHECK (size_bytes > 0 AND size_bytes <= 10485760),
        CONSTRAINT record_export_counts CHECK (attachment_count >= 0 AND missing_file_count >= 0),
        CONSTRAINT record_export_attachments CHECK (
            jsonb_typeof(attachments) = 'array'
            AND jsonb_array_length(attachments) = attachment_count)
    )""")
    op.execute(
        "CREATE INDEX ix_record_export_patient ON vetsys.record_exports "
        "(clinic_id,patient_id,created_at,id)"
    )
    op.execute("CREATE INDEX ix_record_export_author ON vetsys.record_exports(clinic_id,author_id)")
    op.execute("CREATE INDEX ix_record_export_tutor ON vetsys.record_exports(clinic_id,tutor_id)")
    op.execute("ALTER TABLE vetsys.record_exports ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE vetsys.record_exports FORCE ROW LEVEL SECURITY")
    op.execute("GRANT SELECT, INSERT ON vetsys.record_exports TO vetsys_app")
    tenant = "clinic_id = nullif((SELECT current_setting('vetsys.clinic_id', true)), '')::uuid"
    role = "(SELECT current_setting('vetsys.role', true))"
    user = "nullif((SELECT current_setting('vetsys.user_id', true)), '')::uuid"
    op.execute(
        "CREATE POLICY tenant_read ON vetsys.record_exports FOR SELECT TO vetsys_app "
        f"USING ({tenant} AND {role} IN ('admin','veterinarian','assistant'))"
    )
    op.execute(
        "CREATE POLICY tenant_insert ON vetsys.record_exports FOR INSERT TO vetsys_app "
        f"WITH CHECK ({tenant} AND {role} = 'veterinarian' AND author_id = {user})"
    )
    op.execute("""CREATE FUNCTION vetsys.preserve_record_export() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
        BEGIN
            RAISE EXCEPTION 'Record exports are immutable' USING ERRCODE = '42501';
        END $$""")
    op.execute("REVOKE ALL ON FUNCTION vetsys.preserve_record_export() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER guard_change BEFORE UPDATE OR DELETE ON vetsys.record_exports "
        "FOR EACH ROW EXECUTE FUNCTION vetsys.preserve_record_export()"
    )


def downgrade() -> None:
    op.drop_table("record_exports", schema="vetsys")
    op.execute("DROP FUNCTION vetsys.preserve_record_export()")
