"""add manual financial ledger

Revision ID: e4b9de0589fe
Revises: 7373a052b884
Create Date: 2026-11-10 16:09:36.817236

"""

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4b9de0589fe"
down_revision = "7373a052b884"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE vetsys.financial_entries (
        id uuid PRIMARY KEY, clinic_id uuid NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now(), deleted_at timestamptz,
        kind varchar(7) NOT NULL, description varchar(300) NOT NULL,
        category varchar(80) NOT NULL, amount_cents bigint NOT NULL,
        occurred_on date NOT NULL, payment_method varchar(20) NOT NULL,
        author_id uuid NOT NULL, author_name varchar(200) NOT NULL,
        tutor_id uuid, tutor_name varchar(200), patient_id uuid, patient_name varchar(200),
        reverses_id uuid, reversal_reason varchar(500),
        CONSTRAINT uq_financial_clinic UNIQUE (clinic_id,id),
        CONSTRAINT uq_financial_reversal UNIQUE (clinic_id,reverses_id),
        FOREIGN KEY (clinic_id,author_id) REFERENCES vetsys.users(clinic_id,id),
        FOREIGN KEY (clinic_id,tutor_id) REFERENCES vetsys.tutors(clinic_id,id),
        FOREIGN KEY (clinic_id,patient_id) REFERENCES vetsys.patients(clinic_id,id),
        FOREIGN KEY (clinic_id,reverses_id) REFERENCES vetsys.financial_entries(clinic_id,id),
        CHECK (kind IN ('income','expense')),
        CHECK (amount_cents > 0 AND amount_cents <= 1000000000000),
        CHECK (length(btrim(description)) > 0 AND length(btrim(category)) > 0),
        CHECK (payment_method IN ('cash','pix','debit_card','credit_card','bank_transfer','other')),
        CHECK ((tutor_id IS NULL) = (tutor_name IS NULL)),
        CHECK ((patient_id IS NULL) = (patient_name IS NULL)),
        CHECK (deleted_at IS NULL AND updated_at = created_at),
        CHECK ((reverses_id IS NULL AND reversal_reason IS NULL) OR
               (reverses_id IS NOT NULL AND length(btrim(reversal_reason)) BETWEEN 3 AND 500
                AND reversal_reason IS NOT NULL AND reverses_id <> id))
    )""")
    for name, columns in (
        ("period", "clinic_id,occurred_on,id"),
        ("author", "clinic_id,author_id"),
        ("tutor", "clinic_id,tutor_id"),
        ("patient", "clinic_id,patient_id"),
    ):
        op.execute(f"CREATE INDEX ix_financial_{name} ON vetsys.financial_entries ({columns})")
    op.execute("ALTER TABLE vetsys.financial_entries ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE vetsys.financial_entries FORCE ROW LEVEL SECURITY")
    op.execute("GRANT SELECT, INSERT ON vetsys.financial_entries TO vetsys_app")
    tenant = "clinic_id = nullif((SELECT current_setting('vetsys.clinic_id', true)), '')::uuid"
    role = "(SELECT current_setting('vetsys.role', true))"
    user = "nullif((SELECT current_setting('vetsys.user_id', true)), '')::uuid"
    op.execute(
        "CREATE POLICY tenant_read ON vetsys.financial_entries FOR SELECT TO vetsys_app "
        f"USING ({tenant} AND ({role} = 'admin' OR ({role} = 'reception' AND kind = 'income')))"
    )
    op.execute(
        "CREATE POLICY tenant_insert ON vetsys.financial_entries FOR INSERT TO vetsys_app "
        f"WITH CHECK ({tenant} AND author_id = {user} AND "
        f"({role} = 'admin' OR ({role} = 'reception' AND kind = 'income' AND reverses_id IS NULL)))"
    )
    op.execute("""CREATE FUNCTION vetsys.guard_financial_entry() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
        DECLARE original vetsys.financial_entries;
        BEGIN
            IF TG_OP <> 'INSERT' THEN
                RAISE EXCEPTION 'Financial entries are immutable' USING ERRCODE = '42501';
            END IF;
            IF NEW.occurred_on > (CURRENT_TIMESTAMP AT TIME ZONE 'America/Fortaleza')::date THEN
                RAISE EXCEPTION 'Future financial date' USING ERRCODE = '23514';
            END IF;
            IF NEW.reverses_id IS NOT NULL THEN
                SELECT * INTO original FROM vetsys.financial_entries
                  WHERE clinic_id = NEW.clinic_id AND id = NEW.reverses_id;
                IF NOT FOUND OR original.reverses_id IS NOT NULL OR
                    ROW(NEW.kind,NEW.description,NEW.category,NEW.amount_cents,NEW.occurred_on,
                        NEW.payment_method,NEW.tutor_id,NEW.tutor_name,NEW.patient_id,NEW.patient_name)
                    IS DISTINCT FROM
                    ROW(original.kind,original.description,original.category,original.amount_cents,
                        original.occurred_on,original.payment_method,original.tutor_id,
                        original.tutor_name,original.patient_id,original.patient_name) THEN
                    RAISE EXCEPTION 'Invalid financial reversal' USING ERRCODE = '23514';
                END IF;
            END IF;
            RETURN NEW;
        END $$""")
    op.execute("REVOKE ALL ON FUNCTION vetsys.guard_financial_entry() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER guard_financial BEFORE INSERT OR UPDATE OR DELETE "
        "ON vetsys.financial_entries FOR EACH ROW EXECUTE FUNCTION vetsys.guard_financial_entry()"
    )


def downgrade() -> None:
    op.drop_table("financial_entries", schema="vetsys")
    op.execute("DROP FUNCTION vetsys.guard_financial_entry()")
