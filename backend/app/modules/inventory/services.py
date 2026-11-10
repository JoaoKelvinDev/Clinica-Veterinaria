from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.errors import AccessDenied, BusinessConflict, InvalidData, ResourceNotFound
from app.core.repositories import ClinicContext
from app.modules.clinics.models import Role, User
from app.modules.inventory.models import Lot, Product, StockMovement
from app.modules.inventory.repositories import LotRepository, MovementRepository, ProductRepository
from app.modules.inventory.schemas import (
    Adjustment,
    Issue,
    LotCreate,
    LotRead,
    MovementPage,
    MovementRead,
    ProductCreate,
    ProductEdit,
    ProductPage,
    ProductRead,
    ProductSummary,
    Receipt,
)


def require_operator(actor: User, *, admin: bool = False) -> None:
    allowed = {Role.ADMIN} if admin else {Role.ADMIN, Role.VETERINARIAN, Role.ASSISTANT}
    if not actor.active or actor.deleted_at is not None or actor.role not in allowed:
        raise AccessDenied("Seu perfil não permite esta operação de estoque.")


def allocate_fefo(
    lots: list[tuple[Lot, Decimal]], quantity: Decimal, today: date
) -> list[tuple[Lot, Decimal]]:
    allocations: list[tuple[Lot, Decimal]] = []
    for lot, balance in sorted(
        lots,
        key=lambda item: (
            item[0].expires_on is None,
            item[0].expires_on or date.max,
            item[0].created_at,
            item[0].id,
        ),
    ):
        if balance <= 0 or (lot.expires_on is not None and lot.expires_on < today):
            continue
        used = min(quantity, balance)
        allocations.append((lot, -used))
        quantity -= used
        if quantity == 0:
            return allocations
    raise BusinessConflict("Saldo disponível insuficiente. Nenhuma baixa foi registrada.")


class InventoryService:
    @classmethod
    def for_clinic(cls, session: Session, context: ClinicContext) -> InventoryService:
        return cls(
            ProductRepository(session, context),
            LotRepository(session, context),
            MovementRepository(session, context),
        )

    def __init__(
        self, products: ProductRepository, lots: LotRepository, movements: MovementRepository
    ) -> None:
        self.products, self.lots, self.movements = products, lots, movements

    def today(self) -> date:
        return datetime.now(ZoneInfo("America/Fortaleza")).date()

    def _product(self, product_id: UUID) -> Product:
        product = self.products.get(product_id, include_archived=True)
        if product is None:
            raise ResourceNotFound("Produto não encontrado.")
        return product

    def _locked(self, product_id: UUID, version: int) -> Product:
        product = self.products.locked(product_id)
        if product is None:
            raise ResourceNotFound("Produto ativo não encontrado.")
        if product.version != version:
            raise BusinessConflict("O estoque mudou. Atualize o produto antes de tentar novamente.")
        return product

    def _summary(self, product: Product, balances: list[tuple[Lot, Decimal]]) -> ProductSummary:
        today = self.today()
        physical = sum((balance for _, balance in balances), Decimal(0))
        expired = sum(
            (
                balance
                for lot, balance in balances
                if lot.expires_on is not None and lot.expires_on < today
            ),
            Decimal(0),
        )
        return ProductSummary(
            **{
                key: getattr(product, key)
                for key in (
                    "id",
                    "name",
                    "unit",
                    "minimum_stock",
                    "track_expiry",
                    "version",
                    "deleted_at",
                )
            },
            physical_stock=physical,
            available_stock=physical - expired,
            expired_stock=expired,
            low_stock=physical - expired < product.minimum_stock,
            expiring_lots=sum(
                balance > 0
                and lot.expires_on is not None
                and today <= lot.expires_on <= today + timedelta(days=30)
                for lot, balance in balances
            ),
            expired_lots=sum(
                balance > 0 and lot.expires_on is not None and lot.expires_on < today
                for lot, balance in balances
            ),
        )

    def _read(self, product: Product) -> ProductRead:
        balances = self.lots.balances([product.id])
        today = self.today()
        return ProductRead(
            **self._summary(product, balances).model_dump(),
            lots=[
                LotRead(
                    id=lot.id,
                    code=lot.code,
                    expires_on=lot.expires_on,
                    balance=balance,
                    expired=lot.expires_on is not None and lot.expires_on < today,
                    expiring=balance > 0
                    and lot.expires_on is not None
                    and today <= lot.expires_on <= today + timedelta(days=30),
                )
                for lot, balance in balances
            ],
        )

    def get(self, product_id: UUID) -> ProductRead:
        return self._read(self._product(product_id))

    def list_products(self, query: str, archived: bool, limit: int, offset: int) -> ProductPage:
        products, total = self.products.page(query.strip(), archived, limit, offset)
        balances = self.lots.balances([product.id for product in products]) if products else []
        grouped: dict[UUID, list[tuple[Lot, Decimal]]] = {}
        for lot, balance in balances:
            grouped.setdefault(lot.product_id, []).append((lot, balance))
        return ProductPage(
            items=[self._summary(product, grouped.get(product.id, [])) for product in products],
            total=total,
        )

    def history(self, product_id: UUID, limit: int, offset: int) -> MovementPage:
        self._product(product_id)
        items, total = self.movements.page(product_id, limit, offset)
        return MovementPage(
            items=[MovementRead.model_validate(item) for item in items], total=total
        )

    def create(self, actor: User, values: ProductCreate) -> ProductRead:
        require_operator(actor, admin=True)
        product = Product(clinic_id=self.products.context.clinic_id, **values.model_dump())
        self.products.save(product)
        return self._read(product)

    def edit(self, actor: User, product_id: UUID, values: ProductEdit) -> ProductRead:
        require_operator(actor, admin=True)
        product = self._locked(product_id, values.expected_version)
        if (
            product.unit != values.unit or product.track_expiry != values.track_expiry
        ) and self.movements.exists(product_id):
            raise BusinessConflict(
                "Unidade e controle de validade são preservados após a primeira movimentação."
            )
        if values.track_expiry and any(
            lot.expires_on is None for lot, _ in self.lots.balances([product_id])
        ):
            raise BusinessConflict(
                "Existem lotes sem validade. Crie outro produto para controlar validade."
            )
        for key, value in values.model_dump(exclude={"expected_version"}).items():
            setattr(product, key, value)
        product.version += 1
        self.products.save(product)
        return self._read(product)

    def archive(self, actor: User, product_id: UUID, version: int) -> ProductRead:
        require_operator(actor, admin=True)
        product = self._locked(product_id, version)
        if any(balance != 0 for _, balance in self.lots.balances([product_id])):
            raise BusinessConflict("Zere o saldo físico de todos os lotes antes de arquivar.")
        product.deleted_at = datetime.now(UTC)
        product.version += 1
        self.products.save(product)
        return self._read(product)

    def create_lot(self, actor: User, product_id: UUID, values: LotCreate) -> ProductRead:
        require_operator(actor)
        product = self._locked(product_id, values.expected_version)
        code = values.code.upper()
        if len(code) > 80:
            raise InvalidData("O código do lote deve ter até 80 caracteres após normalização.")
        if product.track_expiry and values.expires_on is None:
            raise InvalidData("Informe a validade deste lote.")
        if self.lots.code_exists(product_id, code):
            raise BusinessConflict("Este código de lote já existe no produto.")
        self.lots.save(
            Lot(
                clinic_id=product.clinic_id,
                product_id=product.id,
                code=code,
                expires_on=values.expires_on,
            )
        )
        product.version += 1
        self.products.save(product)
        return self._read(product)

    def _lot(self, product: Product, lot_id: UUID) -> tuple[Lot, Decimal]:
        for lot, balance in self.lots.balances([product.id]):
            if lot.id == lot_id:
                return lot, balance
        raise ResourceNotFound("Lote não encontrado neste produto.")

    def _record(
        self,
        actor: User,
        product: Product,
        allocations: list[tuple[Lot, Decimal]],
        kind: str,
        reason: str,
        corrects_id: UUID | None = None,
    ) -> ProductRead:
        operation_id = uuid4()
        for lot, delta in allocations:
            self.movements.save(
                StockMovement(
                    clinic_id=product.clinic_id,
                    product_id=product.id,
                    lot_id=lot.id,
                    operation_id=operation_id,
                    kind=kind,
                    quantity=delta,
                    reason=reason,
                    author_id=actor.id,
                    author_name=actor.name,
                    product_name=product.name,
                    unit=product.unit,
                    corrects_id=corrects_id,
                )
            )
        product.version += 1
        self.products.save(product)
        return self._read(product)

    def receive(self, actor: User, product_id: UUID, values: Receipt) -> ProductRead:
        require_operator(actor)
        product = self._locked(product_id, values.expected_version)
        lot, _ = self._lot(product, values.lot_id)
        if lot.expires_on is not None and lot.expires_on < self.today():
            raise BusinessConflict(
                "Lote vencido não aceita entrada normal. Use ajuste de inventário."
            )
        return self._record(actor, product, [(lot, values.quantity)], "inbound", values.reason)

    def issue(self, actor: User, product_id: UUID, values: Issue) -> ProductRead:
        require_operator(actor)
        product = self._locked(product_id, values.expected_version)
        allocations = allocate_fefo(self.lots.balances([product_id]), values.quantity, self.today())
        return self._record(actor, product, allocations, "outbound", values.reason)

    def adjust(self, actor: User, product_id: UUID, values: Adjustment) -> ProductRead:
        require_operator(actor, admin=True)
        product = self._locked(product_id, values.expected_version)
        lot, balance = self._lot(product, values.lot_id)
        if values.quantity == 0:
            raise InvalidData("O ajuste deve ser diferente de zero.")
        if balance + values.quantity < 0:
            raise BusinessConflict("O ajuste deixaria o lote com saldo negativo.")
        if values.corrects_id is not None:
            original = self.movements.get(values.corrects_id)
            if original is None or original.product_id != product_id or original.lot_id != lot.id:
                raise ResourceNotFound("Movimentação original não encontrada neste lote.")
        return self._record(
            actor,
            product,
            [(lot, values.quantity)],
            "adjustment",
            values.reason,
            values.corrects_id,
        )
