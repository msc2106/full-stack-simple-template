import uuid
from datetime import datetime

from sqlmodel import Field, Relationship

from . import utils
from .item import ItemBase, ItemPublic
from .user import UserBase, UserPublic


class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid7, primary_key=True)
    hashed_password: str
    created_at: datetime | None = Field(
        default_factory=utils.get_datetime_utc, sa_column=utils.make_timestamp_column()
    )
    items: list[Item] = Relationship(back_populates="owner", cascade_delete=True)

    def public(self) -> UserPublic:
        return UserPublic(
            id=self.id,
            email=self.email,
            full_name=self.full_name,
            is_active=self.is_active,
            is_superuser=self.is_superuser,
            created_at=self.created_at,
        )


class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid7, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=utils.get_datetime_utc, sa_column=utils.make_timestamp_column()
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User = Relationship(back_populates="items")

    def public(self) -> ItemPublic:
        return ItemPublic(
            id=self.id,
            title=self.title,
            description=self.description,
            created_at=self.created_at,
            owner_id=self.owner_id,
        )
