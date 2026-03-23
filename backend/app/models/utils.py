from datetime import UTC, datetime

from sqlalchemy import TIMESTAMP
from sqlmodel import Column


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


def make_timestamp_column(*column_args, **column_kwargs) -> Column:
    return Column(TIMESTAMP(timezone=True), *column_args, **column_kwargs)
