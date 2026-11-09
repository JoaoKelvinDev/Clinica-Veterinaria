"""Rascunhos simulados, com origem preservada e aprovação exclusiva do veterinário."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "90a37f9a5549"
down_revision: str | None = "421d5c158269"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "ai_drafts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("clinic_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=False),
        sa.Column("content", JSONB(), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("llm_provider", sa.String(80), nullable=False),
        sa.Column("llm_model", sa.String(100), nullable=False),
        sa.Column("stt_provider", sa.String(80)),
        sa.Column("stt_model", sa.String(100)),
        sa.Column("prompt_version", sa.String(80), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="pending"),
        sa.Column("resolved_by", sa.Uuid()),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("record_entry_id", sa.Uuid()),
        sa.UniqueConstraint("clinic_id", "record_entry_id", name="uq_ai_draft_record"),
        sa.ForeignKeyConstraint(
            ["clinic_id", "encounter_id", "patient_id"],
            ["vetsys.encounters.clinic_id", "vetsys.encounters.id", "vetsys.encounters.patient_id"],
        ),
        sa.ForeignKeyConstraint(
            ["clinic_id", "requested_by"], ["vetsys.users.clinic_id", "vetsys.users.id"]
        ),
        sa.ForeignKeyConstraint(
            ["clinic_id", "resolved_by"], ["vetsys.users.clinic_id", "vetsys.users.id"]
        ),
        sa.ForeignKeyConstraint(
            ["clinic_id", "record_entry_id", "patient_id"],
            [
                "vetsys.record_entries.clinic_id",
                "vetsys.record_entries.id",
                "vetsys.record_entries.patient_id",
            ],
        ),
        sa.CheckConstraint("source IN ('text','mock_audio')", name="ai_draft_source"),
        sa.CheckConstraint("length(transcript) BETWEEN 1 AND 20000", name="ai_draft_transcript"),
        sa.CheckConstraint("jsonb_typeof(content) = 'object'", name="ai_draft_content"),
        sa.CheckConstraint("deleted_at IS NULL", name="ai_draft_preserved"),
        sa.CheckConstraint(
            "(status = 'pending' AND resolved_by IS NULL AND resolved_at IS NULL "
            "AND record_entry_id IS NULL) OR "
            "(status = 'approved' AND resolved_by IS NOT NULL AND resolved_at IS NOT NULL "
            "AND record_entry_id IS NOT NULL) OR "
            "(status = 'discarded' AND resolved_by IS NOT NULL AND resolved_at IS NOT NULL "
            "AND record_entry_id IS NULL)",
            name="ai_draft_resolution",
        ),
        schema="vetsys",
    )
    op.create_index("ix_vetsys_ai_drafts_clinic_id", "ai_drafts", ["clinic_id"], schema="vetsys")
    op.create_index(
        "ix_ai_draft_patient",
        "ai_drafts",
        ["clinic_id", "patient_id", "created_at"],
        schema="vetsys",
    )
    op.execute("ALTER TABLE vetsys.ai_drafts ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE vetsys.ai_drafts FORCE ROW LEVEL SECURITY")
    op.execute("GRANT SELECT, INSERT ON vetsys.ai_drafts TO vetsys_app")
    op.execute(
        "GRANT UPDATE (status,resolved_by,resolved_at,record_entry_id,updated_at) "
        "ON vetsys.ai_drafts TO vetsys_app"
    )
    tenant = "clinic_id = nullif((SELECT current_setting('vetsys.clinic_id', true)), '')::uuid"
    role = "(SELECT current_setting('vetsys.role', true))"
    user = "nullif((SELECT current_setting('vetsys.user_id', true)), '')::uuid"
    op.execute(
        "CREATE POLICY tenant_read ON vetsys.ai_drafts FOR SELECT TO vetsys_app "
        f"USING ({tenant} AND {role} IN ('admin','veterinarian','assistant'))"
    )
    op.execute(
        "CREATE POLICY tenant_insert ON vetsys.ai_drafts FOR INSERT TO vetsys_app "
        f"WITH CHECK ({tenant} AND {role} = 'veterinarian' AND requested_by = {user} "
        "AND status = 'pending' AND deleted_at IS NULL)"
    )
    op.execute(
        "CREATE POLICY tenant_update ON vetsys.ai_drafts FOR UPDATE TO vetsys_app "
        f"USING ({tenant} AND {role} = 'veterinarian') "
        f"WITH CHECK ({tenant} AND {role} = 'veterinarian' AND resolved_by = {user})"
    )
    op.execute("""CREATE FUNCTION vetsys.check_ai_draft_resolution() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'AI drafts cannot be deleted' USING ERRCODE = '42501';
            END IF;
            IF OLD.status <> 'pending' OR NEW.status NOT IN ('approved','discarded')
               OR (to_jsonb(NEW) - ARRAY[
                   'status','resolved_by','resolved_at','record_entry_id','updated_at'])
                  IS DISTINCT FROM
                  (to_jsonb(OLD) - ARRAY[
                   'status','resolved_by','resolved_at','record_entry_id','updated_at'])
            THEN
                RAISE EXCEPTION 'Invalid draft transition or immutable content changed'
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.status = 'approved' AND NOT EXISTS (
                SELECT 1 FROM vetsys.record_entries e WHERE e.clinic_id = NEW.clinic_id
                AND e.id = NEW.record_entry_id AND e.patient_id = NEW.patient_id
                AND e.encounter_id = NEW.encounter_id AND e.author_id = NEW.resolved_by
            ) THEN
                RAISE EXCEPTION 'Approval must reference the reviewed record'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$""")
    op.execute("REVOKE ALL ON FUNCTION vetsys.check_ai_draft_resolution() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER check_resolution BEFORE UPDATE OR DELETE ON vetsys.ai_drafts "
        "FOR EACH ROW EXECUTE FUNCTION vetsys.check_ai_draft_resolution()"
    )


def downgrade() -> None:
    op.drop_table("ai_drafts", schema="vetsys")
    op.execute("DROP FUNCTION vetsys.check_ai_draft_resolution()")
