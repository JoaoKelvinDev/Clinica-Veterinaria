"""add quotes and protected presentation

Revision ID: 9182a5b73863
Revises: 90a37f9a5549
Create Date: 2026-11-09 16:46:58.087785

"""

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9182a5b73863"
down_revision: str | None = "90a37f9a5549"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("""CREATE TABLE vetsys.quotes (
        id uuid PRIMARY KEY, clinic_id uuid NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now(), deleted_at timestamptz,
        patient_id uuid NOT NULL, tutor_id uuid NOT NULL,
        patient_name varchar(200) NOT NULL, tutor_name varchar(200) NOT NULL,
        encounter_id uuid, source_quote_id uuid,
        status varchar(12) NOT NULL DEFAULT 'draft', version integer NOT NULL DEFAULT 1,
        valid_until date, subtotal_cents bigint NOT NULL,
        discount_cents bigint NOT NULL, total_cents bigint NOT NULL,
        created_by uuid NOT NULL, updated_by uuid NOT NULL,
        presented_at timestamptz, presented_by uuid,
        decision_at timestamptz, decision_by uuid,
        decision_source varchar(20), decision_note varchar(500),
        CONSTRAINT uq_quote_clinic_id UNIQUE (clinic_id, id),
        FOREIGN KEY (clinic_id,patient_id) REFERENCES vetsys.patients(clinic_id,id),
        FOREIGN KEY (clinic_id,tutor_id) REFERENCES vetsys.tutors(clinic_id,id),
        FOREIGN KEY (clinic_id,encounter_id,patient_id)
            REFERENCES vetsys.encounters(clinic_id,id,patient_id),
        FOREIGN KEY (clinic_id,source_quote_id) REFERENCES vetsys.quotes(clinic_id,id),
        FOREIGN KEY (clinic_id,created_by) REFERENCES vetsys.users(clinic_id,id),
        FOREIGN KEY (clinic_id,updated_by) REFERENCES vetsys.users(clinic_id,id),
        FOREIGN KEY (clinic_id,presented_by) REFERENCES vetsys.users(clinic_id,id),
        FOREIGN KEY (clinic_id,decision_by) REFERENCES vetsys.users(clinic_id,id),
        CONSTRAINT quote_status CHECK (status IN ('draft','sent','approved','rejected')),
        CONSTRAINT quote_version CHECK (version >= 1),
        CONSTRAINT quote_totals CHECK (subtotal_cents BETWEEN 0 AND 1000000000000
            AND discount_cents BETWEEN 0 AND subtotal_cents
            AND total_cents = subtotal_cents - discount_cents),
        CONSTRAINT quote_preserved CHECK (deleted_at IS NULL),
        CONSTRAINT quote_presentation CHECK (
            (status = 'draft' AND presented_at IS NULL AND presented_by IS NULL)
            OR (status <> 'draft' AND presented_at IS NOT NULL AND presented_by IS NOT NULL)),
        CONSTRAINT quote_decision CHECK (
            (status IN ('draft','sent') AND decision_at IS NULL AND decision_by IS NULL
             AND decision_source IS NULL AND decision_note IS NULL)
            OR (status IN ('approved','rejected') AND decision_at IS NOT NULL
                AND decision_by IS NOT NULL AND decision_source IN ('in_person','phone','other')))
    )""")
    op.execute("""CREATE TABLE vetsys.quote_items (
        id uuid PRIMARY KEY, clinic_id uuid NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now(), deleted_at timestamptz,
        quote_id uuid NOT NULL, position integer NOT NULL,
        kind varchar(10) NOT NULL, description varchar(300) NOT NULL,
        quantity numeric(9,3) NOT NULL, unit_price_cents bigint NOT NULL,
        line_total_cents bigint GENERATED ALWAYS AS (round(quantity * unit_price_cents)) STORED,
        FOREIGN KEY (clinic_id,quote_id) REFERENCES vetsys.quotes(clinic_id,id),
        CONSTRAINT uq_quote_item_position UNIQUE (clinic_id,quote_id,position),
        CONSTRAINT quote_item_position CHECK (position BETWEEN 1 AND 100),
        CONSTRAINT quote_item_kind CHECK (kind IN ('service','product')),
        CONSTRAINT quote_item_quantity CHECK (quantity > 0 AND quantity <= 999999.999),
        CONSTRAINT quote_item_money CHECK (unit_price_cents BETWEEN 0 AND 1000000000000
            AND line_total_cents BETWEEN 0 AND 1000000000000),
        CONSTRAINT quote_item_preserved CHECK (deleted_at IS NULL)
    )""")
    op.create_index("ix_vetsys_quotes_clinic_id", "quotes", ["clinic_id"], schema="vetsys")
    op.create_index(
        "ix_quote_patient", "quotes", ["clinic_id", "patient_id", "created_at"], schema="vetsys"
    )
    op.create_index("ix_quote_list", "quotes", ["clinic_id", "created_at"], schema="vetsys")
    op.create_index(
        "ix_vetsys_quote_items_clinic_id", "quote_items", ["clinic_id"], schema="vetsys"
    )
    tenant = "clinic_id = nullif((SELECT current_setting('vetsys.clinic_id', true)), '')::uuid"
    user = "nullif((SELECT current_setting('vetsys.user_id', true)), '')::uuid"
    writer = "(SELECT current_setting('vetsys.role', true)) IN ('admin','veterinarian','reception')"
    reader = (
        "(SELECT current_setting('vetsys.role', true)) "
        "IN ('admin','veterinarian','reception','assistant')"
    )
    for table in ("quotes", "quote_items"):
        op.execute(f"ALTER TABLE vetsys.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE vetsys.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"GRANT SELECT, INSERT ON vetsys.{table} TO vetsys_app")
        op.execute(
            f"CREATE POLICY tenant_read ON vetsys.{table} FOR SELECT TO vetsys_app "
            f"USING ({tenant} AND {reader})"
        )
    op.execute("""GRANT UPDATE (patient_id,tutor_id,patient_name,tutor_name,encounter_id,
        status,version,valid_until,subtotal_cents,discount_cents,total_cents,updated_by,updated_at,
        presented_at,presented_by,decision_at,decision_by,decision_source,decision_note)
        ON vetsys.quotes TO vetsys_app""")
    op.execute(
        "CREATE POLICY tenant_insert ON vetsys.quotes FOR INSERT TO vetsys_app "
        f"WITH CHECK ({tenant} AND {writer} AND status = 'draft' "
        f"AND created_by = {user} AND updated_by = {user} AND deleted_at IS NULL)"
    )
    op.execute(
        "CREATE POLICY tenant_update ON vetsys.quotes FOR UPDATE TO vetsys_app "
        f"USING ({tenant} AND {writer}) WITH CHECK ({tenant} AND {writer} AND updated_by = {user})"
    )
    draft_parent = (
        "EXISTS (SELECT 1 FROM vetsys.quotes q WHERE q.clinic_id = quote_items.clinic_id "
        "AND q.id = quote_items.quote_id AND q.status = 'draft')"
    )
    op.execute("GRANT DELETE ON vetsys.quote_items TO vetsys_app")
    op.execute(
        "CREATE POLICY tenant_insert ON vetsys.quote_items FOR INSERT TO vetsys_app "
        f"WITH CHECK ({tenant} AND {writer} AND {draft_parent} AND deleted_at IS NULL)"
    )
    op.execute(
        "CREATE POLICY tenant_delete ON vetsys.quote_items FOR DELETE TO vetsys_app "
        f"USING ({tenant} AND {writer} AND {draft_parent})"
    )
    op.execute("""CREATE FUNCTION vetsys.guard_quote() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
        DECLARE line_sum bigint; line_count integer;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'Quotes are preserved' USING ERRCODE = '42501';
            END IF;
            IF NEW.id <> OLD.id OR NEW.clinic_id <> OLD.clinic_id
               OR NEW.created_by <> OLD.created_by OR NEW.created_at <> OLD.created_at
               OR NEW.source_quote_id IS DISTINCT FROM OLD.source_quote_id
               OR NEW.version <> OLD.version + 1 THEN
                RAISE EXCEPTION 'Invalid quote identity or version' USING ERRCODE = '42501';
            END IF;
            IF OLD.status = 'draft' THEN
                IF NEW.status NOT IN ('draft','sent') THEN
                    RAISE EXCEPTION 'Present before recording decision' USING ERRCODE = '42501';
                END IF;
                IF NEW.status = 'sent' THEN
                    SELECT count(*), coalesce(sum(line_total_cents),0)
                        INTO line_count, line_sum FROM vetsys.quote_items
                        WHERE clinic_id = NEW.clinic_id AND quote_id = NEW.id;
                    IF line_count = 0 OR line_sum <> NEW.subtotal_cents
                       OR NEW.presented_by <> NEW.updated_by
                       OR NEW.valid_until < timezone('America/Fortaleza', now())::date THEN
                        RAISE EXCEPTION 'Invalid presentation' USING ERRCODE = '23514';
                    END IF;
                END IF;
            ELSIF OLD.status = 'sent' THEN
                IF NEW.status NOT IN ('approved','rejected')
                   OR OLD.valid_until < timezone('America/Fortaleza', now())::date
                   OR NEW.decision_by <> NEW.updated_by
                   OR (to_jsonb(NEW) - ARRAY['status','version','updated_by','updated_at',
                       'decision_by','decision_at','decision_source','decision_note'])
                      IS DISTINCT FROM
                      (to_jsonb(OLD) - ARRAY['status','version','updated_by','updated_at',
                       'decision_by','decision_at','decision_source','decision_note']) THEN
                    RAISE EXCEPTION 'Presented content is immutable' USING ERRCODE = '42501';
                END IF;
            ELSE
                RAISE EXCEPTION 'Final quote is immutable' USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END $$""")
    op.execute("""CREATE FUNCTION vetsys.guard_quote_item() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
        DECLARE parent_status text; parent_id uuid; tenant_id uuid;
        BEGIN
            IF TG_OP = 'INSERT' THEN parent_id := NEW.quote_id; tenant_id := NEW.clinic_id;
            ELSE parent_id := OLD.quote_id; tenant_id := OLD.clinic_id; END IF;
            SELECT status INTO parent_status FROM vetsys.quotes
                WHERE id = parent_id AND clinic_id = tenant_id FOR UPDATE;
            IF parent_status IS DISTINCT FROM 'draft' THEN
                RAISE EXCEPTION 'Presented items are immutable' USING ERRCODE = '42501';
            END IF;
            IF TG_OP = 'UPDATE' AND (NEW.quote_id <> OLD.quote_id
               OR NEW.clinic_id <> OLD.clinic_id OR NEW.id <> OLD.id) THEN
                RAISE EXCEPTION 'Item cannot change quote or clinic' USING ERRCODE = '42501';
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END $$""")
    for function in ("guard_quote", "guard_quote_item"):
        op.execute(f"REVOKE ALL ON FUNCTION vetsys.{function}() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER guard_change BEFORE UPDATE OR DELETE ON vetsys.quotes "
        "FOR EACH ROW EXECUTE FUNCTION vetsys.guard_quote()"
    )
    op.execute(
        "CREATE TRIGGER guard_change BEFORE INSERT OR UPDATE OR DELETE ON vetsys.quote_items "
        "FOR EACH ROW EXECUTE FUNCTION vetsys.guard_quote_item()"
    )


def downgrade() -> None:
    op.drop_table("quote_items", schema="vetsys")
    op.drop_table("quotes", schema="vetsys")
    op.execute("DROP FUNCTION vetsys.guard_quote_item()")
    op.execute("DROP FUNCTION vetsys.guard_quote()")
