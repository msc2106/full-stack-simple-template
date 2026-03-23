import uuid

from fastapi import APIRouter, HTTPException
from sqlmodel import col, func, select

import app.models.item as ItemModels
from app.api.deps import CurrentUser, SessionDep
from app.models.generic import Message
from app.models.tables import Item

router = APIRouter(prefix="/items", tags=["items"])


@router.get("/")
async def read_items(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 100
) -> ItemModels.ItemsPublic:
    """
    Retrieve items:
    - Returns all items for superusers.
    - Returns users' own items for others
    """

    if current_user.is_superuser:
        count_statement = select(func.count()).select_from(Item)
        count_response = await session.exec(count_statement)
        statement = (
            select(Item).order_by(col(Item.created_at).desc()).offset(skip).limit(limit)
        )
        items_response = await session.exec(statement)
    else:
        count_statement = (
            select(func.count())
            .select_from(Item)
            .where(Item.owner_id == current_user.id)
        )
        count_response = await session.exec(count_statement)
        statement = (
            select(Item)
            .where(Item.owner_id == current_user.id)
            .order_by(col(Item.created_at).desc())
            .offset(skip)
            .limit(limit)
        )
        items_response = await session.exec(statement)

    return ItemModels.ItemsPublic(
        data=[item.public() for item in items_response.all()],
        count=count_response.one(),
    )


@router.get("/{id}")
async def read_item(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> ItemModels.ItemPublic:
    """
    Get item by ID.
    """
    item = await session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return item.public()


@router.post("/")
async def create_item(
    *, session: SessionDep, current_user: CurrentUser, item_in: ItemModels.ItemCreate
) -> ItemModels.ItemPublic:
    """
    Create new item.
    """
    item = Item.model_validate(item_in, update={"owner_id": current_user.id})
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item.public()


@router.put("/{id}")
async def update_item(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    item_in: ItemModels.ItemUpdate,
) -> ItemModels.ItemPublic:
    """
    Update an item.
    """
    item = await session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    update_dict = item_in.model_dump(exclude_unset=True)
    item.sqlmodel_update(update_dict)
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item.public()


@router.delete("/{id}")
async def delete_item(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """
    Delete an item.
    """
    item = await session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    await session.delete(item)
    await session.commit()
    return Message(message="Item deleted successfully")
