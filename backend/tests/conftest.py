import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.core.config import settings
from app.core.db import AsyncSession
from app.crud.users import init_db
from app.main import app
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import get_superuser_token_headers

# from app.crud.graph import FrameworkManager, get_latest_framework
if "test" not in settings.POSTGRES_PASSWORD:
    raise RuntimeError("Tests must be run against a test database.")

# @pytest.fixture(scope="session")
# def event_loop():
#     """Creates an instance of the default event loop for the test session."""
#     loop = asyncio.new_event_loop()
#     yield loop
#     loop.close()


def isolated_engine() -> AsyncEngine:
    return create_async_engine(str(settings.SQLALCHEMY_DATABASE_URI))


@pytest_asyncio.fixture(scope="function")
async def db_connection(
    # event_loop
):
    # _ = event_loop
    engine = isolated_engine()

    async with engine.connect() as connection:
        # await connection.run_sync(SQLModel.metadata.create_all)
        sessionmaker = async_sessionmaker(
            bind=connection, class_=AsyncSession, expire_on_commit=False
        )
        async with sessionmaker() as session:
            await init_db(session)
        yield sessionmaker
        # await connection.run_sync(SQLModel.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def db(db_connection: async_sessionmaker[AsyncSession]):
    if "test" not in settings.POSTGRES_PASSWORD:
        raise RuntimeError("Tests must be run against a test database.")
    async with db_connection() as session:
        yield session


@pytest.fixture
def client():
    async def override_get_db():
        engine = isolated_engine()
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c


@pytest.fixture
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest_asyncio.fixture
async def normal_user_token_headers(
    client: TestClient, db: AsyncSession
) -> dict[str, str]:
    return await authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )
