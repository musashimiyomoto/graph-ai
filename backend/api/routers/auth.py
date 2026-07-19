"""Auth API routes."""

from typing import Annotated

from fastapi import APIRouter, Body, Cookie, Depends, Path, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import auth, db, rate_limit
from schemas import (
    AuthSessionResponse,
    EmailActionRequest,
    LoginCreate,
    LoginResponse,
    PasswordChangeRequest,
    PasswordResetRequest,
    TokenActionRequest,
    UserCreate,
    UserResponse,
)
from settings import auth_settings

router = APIRouter(prefix="/auth", tags=["Auth"])
_REFRESH_COOKIE = "graph_ai_refresh"
_EMAIL_ACTION_DETAIL = "If the account is eligible, an email has been sent"


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Set the rotated refresh token as an HttpOnly cookie."""
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=refresh_token,
        max_age=auth_settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=auth_settings.environment.lower() not in {"local", "test"},
        samesite="lax",
        path="/",
    )


@router.post(path="/login")
async def login(
    data: Annotated[LoginCreate, Body(description="Data for login")],
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[auth.AuthUsecase, Depends(dependency=auth.get_auth_usecase)],
    _rate_limit: Annotated[
        None, Depends(dependency=rate_limit.enforce_login_rate_limit)
    ],
) -> LoginResponse:
    """Authenticate a user and return a token."""
    result, refresh_token = await usecase.login(
        session=session,
        data=data,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    _set_refresh_cookie(response, refresh_token)
    return result


@router.post(path="/refresh")
async def refresh(
    response: Response,
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[auth.AuthUsecase, Depends(dependency=auth.get_auth_usecase)],
    refresh_token: Annotated[str | None, Cookie(alias=_REFRESH_COOKIE)] = None,
) -> LoginResponse:
    """Rotate the refresh session and return a new access token."""
    result, rotated = await usecase.refresh(
        session=session,
        refresh_token=refresh_token,
    )
    _set_refresh_cookie(response, rotated)
    return result


@router.post(path="/logout")
async def logout(
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[auth.AuthUsecase, Depends(dependency=auth.get_auth_usecase)],
    refresh_token: Annotated[str | None, Cookie(alias=_REFRESH_COOKIE)] = None,
) -> JSONResponse:
    """Revoke the current refresh session and clear its cookie."""
    await usecase.logout(session=session, refresh_token=refresh_token)
    response = JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"detail": "Logged out"},
    )
    response.delete_cookie(key=_REFRESH_COOKIE, path="/")
    return response


@router.get(path="/sessions")
async def list_sessions(
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[auth.AuthUsecase, Depends(dependency=auth.get_auth_usecase)],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
    refresh_token: Annotated[str | None, Cookie(alias=_REFRESH_COOKIE)] = None,
) -> list[AuthSessionResponse]:
    """List active refresh sessions for the current account."""
    return await usecase.list_sessions(
        session=session,
        user_id=current_user.id,
        refresh_token=refresh_token,
    )


@router.delete(path="/sessions/{auth_session_id}")
async def revoke_session(
    auth_session_id: Annotated[int, Path(gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[auth.AuthUsecase, Depends(dependency=auth.get_auth_usecase)],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> JSONResponse:
    """Revoke one owned refresh session."""
    await usecase.revoke_session(
        session=session,
        user_id=current_user.id,
        auth_session_id=auth_session_id,
    )
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"detail": "Authentication session revoked"},
    )


@router.post(path="/register")
async def register(
    data: Annotated[UserCreate, Body(description="Data for register")],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[auth.AuthUsecase, Depends(dependency=auth.get_auth_usecase)],
    _rate_limit: Annotated[
        None, Depends(dependency=rate_limit.enforce_register_rate_limit)
    ],
) -> UserResponse:
    """Register a new user."""
    return await usecase.register(session=session, data=data)


@router.post(path="/resend-verification")
async def resend_verification(
    data: Annotated[EmailActionRequest, Body()],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[auth.AuthUsecase, Depends(dependency=auth.get_auth_usecase)],
    _rate_limit: Annotated[
        None, Depends(dependency=rate_limit.enforce_email_action_rate_limit)
    ],
) -> JSONResponse:
    """Send a fresh verification link without exposing account existence."""
    await usecase.request_email_verification(session=session, email=str(data.email))
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"detail": _EMAIL_ACTION_DETAIL},
    )


@router.post(path="/verify-email")
async def verify_email(
    data: Annotated[TokenActionRequest, Body()],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[auth.AuthUsecase, Depends(dependency=auth.get_auth_usecase)],
) -> JSONResponse:
    """Consume an email verification token."""
    await usecase.verify_email(session=session, token=data.token)
    return JSONResponse(content={"detail": "Email verified successfully"})


@router.post(path="/forgot-password")
async def forgot_password(
    data: Annotated[EmailActionRequest, Body()],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[auth.AuthUsecase, Depends(dependency=auth.get_auth_usecase)],
    _rate_limit: Annotated[
        None, Depends(dependency=rate_limit.enforce_email_action_rate_limit)
    ],
) -> JSONResponse:
    """Send a password recovery link without exposing account existence."""
    await usecase.request_password_reset(session=session, email=str(data.email))
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"detail": _EMAIL_ACTION_DETAIL},
    )


@router.post(path="/reset-password")
async def reset_password(
    data: Annotated[PasswordResetRequest, Body()],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[auth.AuthUsecase, Depends(dependency=auth.get_auth_usecase)],
) -> JSONResponse:
    """Choose a new password with a one-time recovery token."""
    await usecase.reset_password(
        session=session,
        token=data.token,
        new_password=data.new_password,
    )
    response = JSONResponse(content={"detail": "Password reset successfully"})
    response.delete_cookie(key=_REFRESH_COOKIE, path="/")
    return response


@router.post(path="/change-password")
async def change_password(
    data: Annotated[PasswordChangeRequest, Body()],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[auth.AuthUsecase, Depends(dependency=auth.get_auth_usecase)],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> JSONResponse:
    """Change the current password and revoke every login session."""
    await usecase.change_password(
        session=session,
        user_id=current_user.id,
        current_password=data.current_password,
        new_password=data.new_password,
    )
    response = JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"detail": "Password changed; sign in again"},
    )
    response.delete_cookie(key=_REFRESH_COOKIE, path="/")
    return response
