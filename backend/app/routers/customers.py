"""Customer endpoints."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.firebase import get_firestore_client
from app.dependencies.access import assert_can_access_customer, assert_can_write_customer
from app.dependencies.auth import AuthUser, get_current_user
from app.models.customer import CustomerCreate, CustomerOut, CustomerUpdate
from app.services import customer_service

router = APIRouter(prefix="/customers", tags=["customers"])

CurrentUser = Annotated[AuthUser, Depends(get_current_user)]


@router.get("", response_model=list[CustomerOut])
async def list_customers(user: CurrentUser) -> list[CustomerOut]:
    return customer_service.list_customers(user)


@router.post("", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
async def create_customer(payload: CustomerCreate, user: CurrentUser) -> CustomerOut:
    assert_can_write_customer(get_firestore_client(), user, None)
    return customer_service.create_customer(payload, created_by=user.uid)


@router.get("/{customer_id}", response_model=CustomerOut)
async def get_customer(customer_id: str, user: CurrentUser) -> CustomerOut:
    db = get_firestore_client()
    assert_can_access_customer(db, user, customer_id)
    customer = customer_service.get_customer(customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="customer not found")
    return customer


@router.put("/{customer_id}", response_model=CustomerOut)
async def update_customer(customer_id: str, payload: CustomerUpdate,
                          user: CurrentUser) -> CustomerOut:
    assert_can_write_customer(get_firestore_client(), user, customer_id)
    return customer_service.update_customer(customer_id, payload)
