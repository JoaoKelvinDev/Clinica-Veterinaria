from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import AuthContext
from app.modules.inventory.schemas import (
    Adjustment,
    Issue,
    LotCreate,
    MovementPage,
    ProductCreate,
    ProductEdit,
    ProductPage,
    ProductRead,
    Receipt,
    VersionInput,
)
from app.modules.inventory.services import InventoryService

router = APIRouter(prefix="/inventory", tags=["Estoque"])


def inventory_service(auth: AuthContext) -> InventoryService:
    return InventoryService.for_clinic(auth.session, auth.clinic)


Service = Annotated[InventoryService, Depends(inventory_service)]


@router.get("/products", response_model=ProductPage)
def list_products(
    service: Service,
    q: str = Query(default="", max_length=100),
    archived: bool = False,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ProductPage:
    return service.list_products(q, archived, limit, offset)


@router.get("/products/{product_id}", response_model=ProductRead)
def get_product(product_id: UUID, service: Service) -> ProductRead:
    return service.get(product_id)


@router.get("/products/{product_id}/movements", response_model=MovementPage)
def history(
    product_id: UUID,
    service: Service,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> MovementPage:
    return service.history(product_id, limit, offset)


@router.post("/products", response_model=ProductRead, status_code=201)
def create(values: ProductCreate, auth: AuthContext, service: Service) -> ProductRead:
    return service.create(auth.actor, values)


@router.put("/products/{product_id}", response_model=ProductRead)
def edit(product_id: UUID, values: ProductEdit, auth: AuthContext, service: Service) -> ProductRead:
    return service.edit(auth.actor, product_id, values)


@router.post("/products/{product_id}/archive", response_model=ProductRead)
def archive(
    product_id: UUID, values: VersionInput, auth: AuthContext, service: Service
) -> ProductRead:
    return service.archive(auth.actor, product_id, values.expected_version)


@router.post("/products/{product_id}/lots", response_model=ProductRead, status_code=201)
def create_lot(
    product_id: UUID, values: LotCreate, auth: AuthContext, service: Service
) -> ProductRead:
    return service.create_lot(auth.actor, product_id, values)


@router.post("/products/{product_id}/receipts", response_model=ProductRead, status_code=201)
def receive(product_id: UUID, values: Receipt, auth: AuthContext, service: Service) -> ProductRead:
    return service.receive(auth.actor, product_id, values)


@router.post("/products/{product_id}/issues", response_model=ProductRead, status_code=201)
def issue(product_id: UUID, values: Issue, auth: AuthContext, service: Service) -> ProductRead:
    return service.issue(auth.actor, product_id, values)


@router.post("/products/{product_id}/adjustments", response_model=ProductRead, status_code=201)
def adjust(
    product_id: UUID, values: Adjustment, auth: AuthContext, service: Service
) -> ProductRead:
    return service.adjust(auth.actor, product_id, values)
