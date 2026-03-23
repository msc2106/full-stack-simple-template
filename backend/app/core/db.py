import logfire
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio.session import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings

engine = create_async_engine(str(settings.SQLALCHEMY_DATABASE_URI))
make_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

if settings.LOGFIRE_ENABLED:
    logfire.instrument_sqlalchemy(engine=engine)
