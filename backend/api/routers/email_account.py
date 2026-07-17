"""Email account API routes."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import auth, db, email_account
from schemas import (
    EmailAccountCreate,
    EmailAccountResponse,
    EmailAccountUpdate,
    UserResponse,
)

router = APIRouter(prefix="/email-accounts", tags=["Email Accounts"])


@router.post(path="")
async def create_email_account(
    data: Annotated[EmailAccountCreate, Body()],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        email_account.EmailAccountUsecase,
        Depends(dependency=email_account.get_email_account_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> EmailAccountResponse:
    """Create an email account."""
    return await usecase.create_email_account(
        session=session, user_id=current_user.id, data=data
    )


@router.get(path="")
async def list_email_accounts(
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        email_account.EmailAccountUsecase,
        Depends(dependency=email_account.get_email_account_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> list[EmailAccountResponse]:
    """List email accounts."""
    return await usecase.get_email_accounts(session=session, user_id=current_user.id)


@router.patch(path="/{account_id}")
async def update_email_account(
    account_id: Annotated[int, Path(gt=0)],
    data: Annotated[EmailAccountUpdate, Body()],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        email_account.EmailAccountUsecase,
        Depends(dependency=email_account.get_email_account_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> EmailAccountResponse:
    """Update an email account."""
    return await usecase.update_email_account(
        session=session, account_id=account_id, user_id=current_user.id, data=data
    )


@router.delete(path="/{account_id}")
async def delete_email_account(
    account_id: Annotated[int, Path(gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        email_account.EmailAccountUsecase,
        Depends(dependency=email_account.get_email_account_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> JSONResponse:
    """Delete an email account."""
    await usecase.delete_email_account(
        session=session, account_id=account_id, user_id=current_user.id
    )
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"detail": "Email account deleted"},
    )
