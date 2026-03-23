import asyncio as aio
import logging

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select, text
from tenacity import after_log, before_log, retry, stop_after_attempt, wait_fixed

from app.core.db import AsyncSession, engine
from app.core.logging import logger_setup

logger = logger_setup(__name__)

max_tries = 60 * 5  # 5 minutes
wait_seconds = 1


@retry(
    stop=stop_after_attempt(max_tries),
    wait=wait_fixed(wait_seconds),
    before=before_log(logger, logging.INFO),
    after=after_log(logger, logging.WARN),
)
async def init(db_engine: AsyncEngine) -> None:
    try:
        async with AsyncSession(db_engine) as session:
            # Try to create session to check if DB is awake
            await session.exec(select(1))
        async with db_engine.begin() as conn:
            # Ensure pgvector extension is installed
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    except Exception as e:
        logger.error(e)
        raise e


async def main() -> None:
    logger.info("Initializing service")
    await init(engine)
    logger.info("Service finished initializing")


if __name__ == "__main__":
    aio.run(main())
