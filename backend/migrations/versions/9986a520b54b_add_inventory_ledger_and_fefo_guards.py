"""add inventory ledger and FEFO guards

Revision ID: 9986a520b54b
Revises: 9182a5b73863
Create Date: 2026-11-09 17:27:14.963537

"""

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9986a520b54b"
down_revision = "9182a5b73863"
branch_labels = None
depends_on = None


def upgrade() -> None:
    common = """id uuid PRIMARY KEY, clinic_id uuid NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now(), deleted_at timestamptz"""
    op.execute(f"""CREATE TABLE vetsys.products ({common},
        name varchar(200) NOT NULL CHECK (length(trim(name)) > 0),
        unit varchar(20) NOT NULL CHECK (length(trim(unit)) > 0),
        minimum_stock numeric(9,3) NOT NULL CHECK (minimum_stock BETWEEN 0 AND 999999.999),
        track_expiry boolean NOT NULL, version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
        CONSTRAINT uq_product_clinic UNIQUE (clinic_id,id),
        FOREIGN KEY (clinic_id) REFERENCES vetsys.clinics(id)
    )""")
    op.execute(f"""CREATE TABLE vetsys.lots ({common},
        product_id uuid NOT NULL, code varchar(80) NOT NULL, expires_on date,
        CONSTRAINT uq_lot_code UNIQUE (clinic_id,product_id,code),
        CONSTRAINT uq_lot_product UNIQUE (clinic_id,product_id,id),
        FOREIGN KEY (clinic_id,product_id) REFERENCES vetsys.products(clinic_id,id),
        CHECK (deleted_at IS NULL), CHECK (code = upper(trim(code)) AND length(code) > 0)
    )""")
    op.execute(f"""CREATE TABLE vetsys.stock_movements ({common},
        product_id uuid NOT NULL, lot_id uuid NOT NULL, operation_id uuid NOT NULL,
        kind varchar(12) NOT NULL CHECK (kind IN ('inbound','outbound','adjustment')),
        quantity numeric(9,3) NOT NULL CHECK (quantity <> 0 AND abs(quantity) <= 999999.999),
        reason varchar(500) NOT NULL CHECK (length(trim(reason)) >= 3),
        author_id uuid NOT NULL, author_name varchar(200) NOT NULL,
        product_name varchar(200) NOT NULL, unit varchar(20) NOT NULL, corrects_id uuid,
        CONSTRAINT uq_movement_lot UNIQUE (clinic_id,product_id,lot_id,id),
        FOREIGN KEY (clinic_id,product_id,lot_id) REFERENCES vetsys.lots(clinic_id,product_id,id),
        FOREIGN KEY (clinic_id,author_id) REFERENCES vetsys.users(clinic_id,id),
        FOREIGN KEY (clinic_id,product_id,lot_id,corrects_id)
            REFERENCES vetsys.stock_movements(clinic_id,product_id,lot_id,id),
        CHECK (deleted_at IS NULL),
        CHECK ((kind = 'inbound' AND quantity > 0) OR (kind = 'outbound' AND quantity < 0)
            OR kind = 'adjustment'),
        CHECK (corrects_id IS NULL OR (kind = 'adjustment' AND corrects_id <> id))
    )""")
    op.execute("CREATE INDEX ix_product_list ON vetsys.products(clinic_id,name,id)")
    op.execute(
        "CREATE INDEX ix_stock_ledger ON vetsys.stock_movements"
        "(clinic_id,product_id,lot_id,created_at)"
    )
    op.execute(
        "CREATE INDEX ix_stock_history ON vetsys.stock_movements"
        "(clinic_id,product_id,created_at DESC,id)"
    )
    op.execute("CREATE INDEX ix_stock_author ON vetsys.stock_movements(clinic_id,author_id)")
    tenant = "clinic_id = nullif((SELECT current_setting('vetsys.clinic_id', true)), '')::uuid"
    role = "(SELECT current_setting('vetsys.role', true))"
    user = "nullif((SELECT current_setting('vetsys.user_id', true)), '')::uuid"
    operator = f"{role} IN ('admin','veterinarian','assistant')"
    for table in ("products", "lots", "stock_movements"):
        op.execute(f"ALTER TABLE vetsys.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE vetsys.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"GRANT SELECT, INSERT ON vetsys.{table} TO vetsys_app")
        op.execute(
            f"CREATE POLICY tenant_read ON vetsys.{table} FOR SELECT TO vetsys_app "
            f"USING ({tenant} AND {role} IN ('admin','veterinarian','assistant','reception'))"
        )
    op.execute(
        "GRANT UPDATE (name,unit,minimum_stock,track_expiry,version,deleted_at,updated_at) "
        "ON vetsys.products TO vetsys_app"
    )
    op.execute(
        "CREATE POLICY tenant_insert ON vetsys.products FOR INSERT TO vetsys_app "
        f"WITH CHECK ({tenant} AND {role} = 'admin' AND deleted_at IS NULL AND version = 1)"
    )
    op.execute(
        "CREATE POLICY tenant_update ON vetsys.products FOR UPDATE TO vetsys_app "
        f"USING ({tenant} AND {operator}) WITH CHECK ({tenant} AND {operator})"
    )
    op.execute(
        "CREATE POLICY tenant_insert ON vetsys.lots FOR INSERT TO vetsys_app "
        f"WITH CHECK ({tenant} AND {operator} AND deleted_at IS NULL)"
    )
    op.execute(
        "CREATE POLICY tenant_insert ON vetsys.stock_movements FOR INSERT TO vetsys_app "
        f"WITH CHECK ({tenant} AND {operator} AND author_id = {user} "
        f"AND (kind <> 'adjustment' OR {role} = 'admin') AND deleted_at IS NULL)"
    )
    op.execute("""CREATE FUNCTION vetsys.guard_inventory_product() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'Inventory history is preserved' USING ERRCODE = '42501';
            END IF;
            IF OLD.deleted_at IS NOT NULL OR NEW.version <> OLD.version + 1
                OR NEW.id <> OLD.id OR NEW.clinic_id <> OLD.clinic_id
                OR NEW.created_at <> OLD.created_at THEN
                RAISE EXCEPTION 'Invalid product update' USING ERRCODE = '42501';
            END IF;
            IF current_user = 'vetsys_app' AND current_setting('vetsys.role',true) <> 'admin'
                AND (to_jsonb(NEW) - ARRAY['version','updated_at']) IS DISTINCT FROM
                    (to_jsonb(OLD) - ARRAY['version','updated_at']) THEN
                RAISE EXCEPTION 'Only admin changes product metadata' USING ERRCODE = '42501';
            END IF;
            IF (NEW.unit <> OLD.unit OR NEW.track_expiry <> OLD.track_expiry) AND EXISTS (
                SELECT 1 FROM vetsys.stock_movements WHERE clinic_id = OLD.clinic_id
                AND product_id = OLD.id) THEN
                RAISE EXCEPTION 'Unit and expiry policy are preserved' USING ERRCODE = '23514';
            END IF;
            IF NEW.track_expiry AND EXISTS (SELECT 1 FROM vetsys.lots
                WHERE clinic_id = NEW.clinic_id AND product_id = NEW.id AND expires_on IS NULL) THEN
                RAISE EXCEPTION 'Expiry is required' USING ERRCODE = '23514';
            END IF;
            IF NEW.deleted_at IS NOT NULL AND EXISTS (SELECT 1 FROM vetsys.stock_movements
                WHERE clinic_id = NEW.clinic_id AND product_id = NEW.id
                GROUP BY lot_id HAVING sum(quantity) <> 0) THEN
                RAISE EXCEPTION 'Physical stock must be zero' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$""")
    op.execute("""CREATE FUNCTION vetsys.guard_inventory_lot() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
        DECLARE parent vetsys.products;
        BEGIN
            IF TG_OP <> 'INSERT' THEN
                RAISE EXCEPTION 'Lot identity is preserved' USING ERRCODE = '42501';
            END IF;
            SELECT * INTO parent FROM vetsys.products
                WHERE clinic_id = NEW.clinic_id AND id = NEW.product_id FOR UPDATE;
            IF parent.id IS NULL OR parent.deleted_at IS NOT NULL
                OR (parent.track_expiry AND NEW.expires_on IS NULL) THEN
                RAISE EXCEPTION 'Invalid lot product or expiry' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$""")
    op.execute("""CREATE FUNCTION vetsys.guard_stock_movement() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
        DECLARE parent vetsys.products; expiry date; balance numeric;
        BEGIN
            IF TG_OP <> 'INSERT' THEN
                RAISE EXCEPTION 'Stock movements are immutable' USING ERRCODE = '42501';
            END IF;
            SELECT * INTO parent FROM vetsys.products
                WHERE clinic_id = NEW.clinic_id AND id = NEW.product_id FOR UPDATE;
            IF parent.id IS NULL OR parent.deleted_at IS NOT NULL OR NEW.unit <> parent.unit
                OR NEW.product_name <> parent.name THEN
                RAISE EXCEPTION 'Invalid movement product' USING ERRCODE = '23514';
            END IF;
            SELECT expires_on INTO expiry FROM vetsys.lots WHERE clinic_id = NEW.clinic_id
                AND product_id = NEW.product_id AND id = NEW.lot_id;
            IF NOT FOUND OR (NEW.kind <> 'adjustment'
                AND expiry < timezone('America/Fortaleza', now())::date) THEN
                RAISE EXCEPTION 'Invalid or expired lot' USING ERRCODE = '23514';
            END IF;
            SELECT coalesce(sum(quantity),0) INTO balance FROM vetsys.stock_movements
                WHERE clinic_id = NEW.clinic_id AND product_id = NEW.product_id
                    AND lot_id = NEW.lot_id;
            IF balance + NEW.quantity < 0 THEN
                RAISE EXCEPTION 'Negative stock is forbidden' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$""")
    for table, function in (
        ("products", "guard_inventory_product"),
        ("lots", "guard_inventory_lot"),
        ("stock_movements", "guard_stock_movement"),
    ):
        events = "UPDATE OR DELETE" if table == "products" else "INSERT OR UPDATE OR DELETE"
        op.execute(f"REVOKE ALL ON FUNCTION vetsys.{function}() FROM PUBLIC")
        op.execute(
            f"CREATE TRIGGER guard_change BEFORE {events} ON vetsys.{table} "
            f"FOR EACH ROW EXECUTE FUNCTION vetsys.{function}()"
        )


def downgrade() -> None:
    for table in ("stock_movements", "lots", "products"):
        op.drop_table(table, schema="vetsys")
    for function in ("guard_stock_movement", "guard_inventory_lot", "guard_inventory_product"):
        op.execute(f"DROP FUNCTION vetsys.{function}()")
