from app.core.config import settings
from app.core.db import AsyncSession
from app.core.security import verify_password
from app.crud.users import get_user_by_email
from app.models.tables import User


async def authenticate(
    *, session: AsyncSession, email: str, password: str
) -> User | None:
    db_user = await get_user_by_email(session=session, email=email)
    if not db_user:
        # Prevent timing attacks by running password verification
        # even when user doesn't exist
        # This ensures the response time is similar whether or not the email exists
        verify_password(password, settings.DUMMY_HASH)
        return None
    verified, updated_password_hash = verify_password(password, db_user.hashed_password)
    if not verified:
        return None
    if updated_password_hash:
        db_user.hashed_password = updated_password_hash
        session.add(db_user)
        await session.commit()
        await session.refresh(db_user)
    return db_user
