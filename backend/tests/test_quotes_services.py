from decimal import Decimal
from unittest.mock import Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.errors import AccessDenied, InvalidData
from app.modules.clinics.models import Role, User
from app.modules.quotes.schemas import MAX_CENTS, QuoteItemInput
from app.modules.quotes.services import QuoteService, calculate, require_writer


def item(quantity: str = "1", price: int = 100) -> QuoteItemInput:
    return QuoteItemInput(
        kind="service",
        description="Serviço fictício",
        quantity=Decimal(quantity),
        unit_price_cents=price,
    )


@pytest.mark.parametrize(
    "quantity,price,expected", [("1.5", 1250, 1875), ("0.5", 1, 1), ("0.499", 1, 0), ("2", 0, 0)]
)
def test_exact_calculation_and_half_up(quantity: str, price: int, expected: int) -> None:
    assert calculate([item(quantity, price)], 0) == (expected, expected)


def test_round_each_item_before_sum_and_allow_full_discount() -> None:
    assert calculate([item("0.5", 1), item("0.5", 1)], 2) == (2, 0)


@pytest.mark.parametrize(
    "items,discount",
    [([item()], 101), ([item("2", MAX_CENTS)], 0), ([item("1", MAX_CENTS), item()], 0)],
)
def test_discount_and_money_limits(items: list[QuoteItemInput], discount: int) -> None:
    with pytest.raises(InvalidData):
        calculate(items, discount)


@pytest.mark.parametrize(
    "changes",
    [
        {"quantity": "0"},
        {"quantity": "-1"},
        {"quantity": "1.0001"},
        {"quantity": 1.5},
        {"quantity": "NaN"},
        {"unit_price_cents": -1},
        {"unit_price_cents": 1.5},
        {"unit_price_cents": True},
        {"description": " "},
    ],
)
def test_invalid_items_are_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        QuoteItemInput.model_validate(
            {
                "kind": "product",
                "description": "Produto fictício",
                "quantity": "1",
                "unit_price_cents": 100,
                **changes,
            }
        )


def test_assistant_and_inactive_users_cannot_write() -> None:
    for role, active in ((Role.ASSISTANT, True), (Role.ADMIN, False)):
        with pytest.raises(AccessDenied):
            require_writer(User(id=uuid4(), role=role, active=active))
    service = QuoteService(Mock(), Mock(), Mock())
    with pytest.raises(AccessDenied):
        service.present(User(role=Role.ASSISTANT, active=True), uuid4(), 1)
    service.quotes.locked.assert_not_called()  # type: ignore[attr-defined]
