from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import cast
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.core.repositories import ClinicContext, TenantRepository
from app.modules.inventory.models import Lot, Product, StockMovement


class ProductRepository(TenantRepository[Product]):
    def __init__(self, session: Session, context: ClinicContext) -> None:
        super().__init__(session, context, Product)

    def alert_counts(self, today: date, expiring_until: date) -> tuple[int, int, int]:
        ledger = (
            select(StockMovement.lot_id, func.sum(StockMovement.quantity).label("balance"))
            .where(
                StockMovement.clinic_id == self.context.clinic_id,
                StockMovement.deleted_at.is_(None),
            )
            .group_by(StockMovement.lot_id)
            .subquery()
        )
        lots = (
            select(
                Lot.product_id, Lot.expires_on, func.coalesce(ledger.c.balance, 0).label("balance")
            )
            .outerjoin(ledger, ledger.c.lot_id == Lot.id)
            .where(Lot.clinic_id == self.context.clinic_id, Lot.deleted_at.is_(None))
            .subquery()
        )
        available = func.coalesce(
            func.sum(
                case(
                    (or_(lots.c.expires_on.is_(None), lots.c.expires_on >= today), lots.c.balance),
                    else_=0,
                )
            ),
            0,
        )
        expired = func.count().filter(and_(lots.c.balance > 0, lots.c.expires_on < today))
        expiring = func.count().filter(
            and_(lots.c.balance > 0, lots.c.expires_on.between(today, expiring_until))
        )
        products = (
            self._select()
            .outerjoin(lots, lots.c.product_id == Product.id)
            .with_only_columns(
                Product.id,
                Product.minimum_stock,
                available.label("available"),
                expired.label("expired"),
                expiring.label("expiring"),
            )
            .group_by(Product.id, Product.minimum_stock)
            .subquery()
        )
        low, expired_total, expiring_total = self.session.execute(
            select(
                func.count().filter(products.c.available < products.c.minimum_stock),
                func.coalesce(func.sum(products.c.expired), 0),
                func.coalesce(func.sum(products.c.expiring), 0),
            )
        ).one()
        return int(str(low)), int(str(expired_total)), int(str(expiring_total))

    def locked(self, product_id: UUID) -> Product | None:
        return self.session.scalar(
            self._select()
            .where(Product.id == product_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def page(
        self, query: str, archived: bool, limit: int, offset: int
    ) -> tuple[Sequence[Product], int]:
        statement = self._select(include_archived=archived)
        if archived:
            statement = statement.where(Product.deleted_at.is_not(None))
        if query:
            statement = statement.where(Product.name.icontains(query, autoescape=True))
        total = self.session.scalar(statement.with_only_columns(func.count())) or 0
        return self.session.scalars(
            statement.order_by(Product.name, Product.id).limit(limit).offset(offset)
        ).all(), total


class LotRepository(TenantRepository[Lot]):
    def __init__(self, session: Session, context: ClinicContext) -> None:
        super().__init__(session, context, Lot)

    def balances(self, product_ids: list[UUID]) -> list[tuple[Lot, Decimal]]:
        ledger = (
            select(StockMovement.lot_id, func.sum(StockMovement.quantity).label("balance"))
            .where(
                StockMovement.clinic_id == self.context.clinic_id,
                StockMovement.product_id.in_(product_ids),
            )
            .group_by(StockMovement.lot_id)
            .subquery()
        )
        rows = self.session.execute(
            self._select()
            .add_columns(func.coalesce(ledger.c.balance, 0))
            .outerjoin(ledger, ledger.c.lot_id == Lot.id)
            .where(Lot.product_id.in_(product_ids))
            .order_by(Lot.expires_on.asc().nulls_last(), Lot.created_at, Lot.id)
        ).all()
        return [(cast(Lot, lot), cast(Decimal, balance)) for lot, balance in rows]

    def code_exists(self, product_id: UUID, code: str) -> bool:
        return (
            self.session.scalar(
                self._select().where(Lot.product_id == product_id, Lot.code == code).limit(1)
            )
            is not None
        )


class MovementRepository(TenantRepository[StockMovement]):
    def __init__(self, session: Session, context: ClinicContext) -> None:
        super().__init__(session, context, StockMovement)

    def exists(self, product_id: UUID) -> bool:
        return (
            self.session.scalar(
                self._select().where(StockMovement.product_id == product_id).limit(1)
            )
            is not None
        )

    def page(
        self, product_id: UUID, limit: int, offset: int
    ) -> tuple[Sequence[StockMovement], int]:
        statement = self._select().where(StockMovement.product_id == product_id)
        total = self.session.scalar(statement.with_only_columns(func.count())) or 0
        return self.session.scalars(
            statement.order_by(StockMovement.created_at.desc(), StockMovement.id)
            .limit(limit)
            .offset(offset)
        ).all(), total
