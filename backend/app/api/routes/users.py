import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, func, select

import app.crud.users as crud
import app.models.user as UserModels
from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
)
from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.models.generic import Message
from app.models.tables import User
from app.utils import generate_new_account_email, send_email

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", dependencies=[Depends(get_current_active_superuser)])
async def read_users(
    session: SessionDep, skip: int = 0, limit: int = 100
) -> UserModels.UsersPublic:
    """
    Retrieve users.
    """

    count_statement = select(func.count()).select_from(User)
    count_response = await session.exec(count_statement)

    statement = (
        select(User).order_by(col(User.created_at).desc()).offset(skip).limit(limit)
    )
    users_response = await session.exec(statement)

    return UserModels.UsersPublic(
        data=[user.public() for user in users_response.all()],
        count=count_response.one(),
    )


@router.post("/", dependencies=[Depends(get_current_active_superuser)])
async def create_user(
    *, session: SessionDep, user_in: UserModels.UserCreate
) -> UserModels.UserPublic:
    """
    Create new user.
    """
    user = await crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )

    user = await crud.create_user(session=session, user_create=user_in)
    if settings.emails_enabled and user_in.email:
        email_data = generate_new_account_email(
            email_to=user_in.email, username=user_in.email, password=user_in.password
        )
        send_email(
            email_to=user_in.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    return user.public()


@router.patch("/me")
async def update_user_me(
    *, session: SessionDep, user_in: UserModels.UserUpdateMe, current_user: CurrentUser
) -> UserModels.UserPublic:
    """
    Update own user.
    """

    if user_in.email:
        existing_user = await crud.get_user_by_email(
            session=session, email=user_in.email
        )
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )
    user_data = user_in.model_dump(exclude_unset=True)
    current_user.sqlmodel_update(user_data)
    session.add(current_user)
    await session.commit()
    await session.refresh(current_user)
    return current_user.public()


@router.patch("/me/password")
async def update_password_me(
    *, session: SessionDep, body: UserModels.UpdatePassword, current_user: CurrentUser
) -> Message:
    """
    Update own password.
    """
    verified, _ = verify_password(body.current_password, current_user.hashed_password)
    if not verified:
        raise HTTPException(status_code=400, detail="Incorrect password")
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=400, detail="New password cannot be the same as the current one"
        )
    hashed_password = get_password_hash(body.new_password)
    current_user.hashed_password = hashed_password
    session.add(current_user)
    await session.commit()
    return Message(message="Password updated successfully")


@router.get("/me")
async def read_user_me(current_user: CurrentUser) -> UserModels.UserPublic:
    """
    Get current user.
    """
    return current_user.public()


@router.delete("/me")
async def delete_user_me(session: SessionDep, current_user: CurrentUser) -> Message:
    """
    Delete own user.
    """
    if current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    await session.delete(current_user)
    await session.commit()
    return Message(message="User deleted successfully")


@router.post("/signup")
async def register_user(
    session: SessionDep, user_in: UserModels.UserRegister
) -> UserModels.UserPublic:
    """
    Create new user without the need to be logged in.
    """
    user = await crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system",
        )
    user_create = UserModels.UserCreate.model_validate(user_in)
    user = await crud.create_user(session=session, user_create=user_create)
    return user.public()


@router.get("/{user_id}")
async def read_user_by_id(
    user_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> UserModels.UserPublic:
    """
    Get a specific user by id.
    """
    user = await session.get(User, user_id)
    if user == current_user:
        return current_user.public()
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="The user doesn't have enough privileges",
        )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user.public()


@router.patch("/{user_id}", dependencies=[Depends(get_current_active_superuser)])
async def update_user(
    *,
    session: SessionDep,
    user_id: uuid.UUID,
    user_in: UserModels.UserUpdate,
) -> UserModels.UserPublic:
    """
    Update a user.
    """

    db_user = await session.get(User, user_id)
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="The user with this id does not exist in the system",
        )
    if user_in.email:
        existing_user = await crud.get_user_by_email(
            session=session, email=user_in.email
        )
        if existing_user and existing_user.id != user_id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )

    db_user = await crud.update_user(session=session, db_user=db_user, user_in=user_in)
    return db_user.public()


@router.delete("/{user_id}", dependencies=[Depends(get_current_active_superuser)])
async def delete_user(
    session: SessionDep, current_user: CurrentUser, user_id: uuid.UUID
) -> Message:
    """
    Delete a user.
    """
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user == current_user:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    await session.delete(user)
    await session.commit()
    return Message(message="User deleted successfully")
