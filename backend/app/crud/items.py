from uuid import UUID

from app.core.db import AsyncSession
from app.models.item import ItemCreate
from app.models.tables import Item


async def create_item(
    *, session: AsyncSession, item_in: ItemCreate, owner_id: UUID
) -> Item:
    db_item = Item.model_validate(item_in, update={"owner_id": owner_id})
    session.add(db_item)
    await session.commit()
    await session.refresh(db_item)
    return db_item
