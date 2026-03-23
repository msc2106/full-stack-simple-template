import asyncio as aio

from app.core.db import AsyncSession, engine
from app.core.logging import logger_setup
from app.crud.users import init_db

logger = logger_setup(__name__)


async def init() -> None:
    async with AsyncSession(engine) as session:
        await init_db(session)


async def main() -> None:
    logger.info("Creating initial data")
    await init()
    logger.info("Initial data created")


if __name__ == "__main__":
    aio.run(main())
