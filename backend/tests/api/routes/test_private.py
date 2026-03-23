import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from app.core.config import settings
from app.core.db import AsyncSession
from app.models.tables import User
from tests.utils.utils import random_email


@pytest.mark.asyncio
async def test_create_user(client: TestClient, db: AsyncSession) -> None:
    email = random_email()
    r = client.post(
        f"{settings.API_V1_STR}/private/users/",
        json={
            "email": email,
            "password": "password123",
            "full_name": "Pollo Listo",
        },
    )

    assert r.status_code == 200

    data = r.json()

    response = await db.exec(select(User).where(User.id == data["id"]))
    user = response.first()

    assert user
    assert user.email == email
    assert user.full_name == "Pollo Listo"
