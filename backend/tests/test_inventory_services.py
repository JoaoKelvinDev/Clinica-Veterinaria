from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.core.errors import AccessDenied, BusinessConflict
from app.modules.clinics.models import Role, User
from app.modules.inventory.models import Lot
from app.modules.inventory.schemas import ProductCreate
from app.modules.inventory.services import InventoryService, allocate_fefo


def test_fefo_ties_by_registration_and_undated_last() -> None:
    now, today = datetime.now(UTC), date(2030, 1, 1)
    older = Lot(id=uuid4(), code="OLD", expires_on=today, created_at=now - timedelta(days=1))
    newer = Lot(id=uuid4(), code="NEW", expires_on=today, created_at=now)
    undated = Lot(id=uuid4(), code="NONE", expires_on=None, created_at=now)
    expired = Lot(id=uuid4(), code="EXPIRED", expires_on=today - timedelta(days=1), created_at=now)
    rows = [
        (newer, Decimal("2")),
        (undated, Decimal("5")),
        (older, Decimal("1.001")),
        (expired, Decimal("8")),
    ]
    result = allocate_fefo(rows, Decimal("3.002"), today)
    assert [(lot.code, delta) for lot, delta in result] == [
        ("OLD", Decimal("-1.001")),
        ("NEW", Decimal("-2")),
        ("NONE", Decimal("-0.001")),
    ]
    with pytest.raises(BusinessConflict):
        allocate_fefo(rows, Decimal("8.002"), today)


def test_dated_lot_precedes_undated_even_on_last_representable_date() -> None:
    now = datetime.now(UTC)
    undated = Lot(id=uuid4(), expires_on=None, created_at=now - timedelta(days=1))
    dated = Lot(id=uuid4(), expires_on=date.max, created_at=now)
    assert allocate_fefo(
        [(undated, Decimal(1)), (dated, Decimal(1))], Decimal(1), date.today()
    ) == [(dated, Decimal(-1))]


@pytest.mark.parametrize("role", [Role.RECEPTION, Role.ASSISTANT, Role.VETERINARIAN])
def test_admin_permission_before_repository_access(role: Role) -> None:
    products, lots, movements = Mock(), Mock(), Mock()
    service = InventoryService(products, lots, movements)
    actor = User(role=role, active=True, deleted_at=None)
    with pytest.raises(AccessDenied):
        service.create(
            actor,
            ProductCreate(name="Fictício", unit="un", minimum_stock=Decimal(0), track_expiry=False),
        )
    assert products.mock_calls == lots.mock_calls == movements.mock_calls == []
