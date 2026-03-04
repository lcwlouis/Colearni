"""Auth route definitions – magic link request, verify, logout, /me."""

from __future__ import annotations

from adapters.db.auth import (
    consume_magic_link_token,
    get_or_create_user_by_email,
    get_tutor_profile,
    issue_auth_session,
    issue_magic_link_token,
    revoke_auth_session,
)
from adapters.db.dependencies import get_db_session
from apps.api.dependencies import get_current_user
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Request / Response schemas ────────────────────────────────────────


class MagicLinkRequest(BaseModel):
    email: EmailStr


class MagicLinkResponse(BaseModel):
    message: str
    # In dev mode the token is echoed; in production it would be emailed.
    debug_token: str | None = None


class VerifyTokenRequest(BaseModel):
    token: str = Field(min_length=1)


class VerifyTokenResponse(BaseModel):
    session_token: str
    user: "UserPublic"


class UserPublic(BaseModel):
    public_id: str
    email: str
    display_name: str | None = None


class TutorProfileResponse(BaseModel):
    readiness_summary: str
    learning_style_notes: str
    last_activity_at: str | None = None


# ── Routes ────────────────────────────────────────────────────────────


@router.post("/magic-link", response_model=MagicLinkResponse, status_code=status.HTTP_200_OK)
def request_magic_link(
    payload: MagicLinkRequest,
    db: Session = Depends(get_db_session),
) -> MagicLinkResponse:
    """Issue a magic-link token for the given email address.

    In production the token would be emailed; in dev we echo it back for
    convenience so that the frontend can auto-verify without an email service.
    """
    raw_token, _expires_at = issue_magic_link_token(db, email=payload.email)
    return MagicLinkResponse(
        message="Magic link sent. Check your email.",
        debug_token=raw_token,
    )


@router.post("/verify", response_model=VerifyTokenResponse)
def verify_magic_link(
    payload: VerifyTokenRequest,
    db: Session = Depends(get_db_session),
) -> VerifyTokenResponse:
    """Exchange a magic-link token for a session token + user record."""
    email = consume_magic_link_token(db, raw_token=payload.token)
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired magic link.",
        )
    user = get_or_create_user_by_email(db, email=email)
    raw_session_token, _session_row = issue_auth_session(db, user_id=user.id)
    return VerifyTokenResponse(
        session_token=raw_session_token,
        user=UserPublic(
            public_id=user.public_id,
            email=user.email,
            display_name=user.display_name,
        ),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user),
) -> Response:
    """Revoke the current session token."""
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        raw_token = auth_header[7:].strip()
        if raw_token:
            revoke_auth_session(db, raw_token=raw_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserPublic)
def get_me(user=Depends(get_current_user)) -> UserPublic:
    """Return the authenticated user profile."""
    return UserPublic(
        public_id=user.public_id,
        email=user.email,
        display_name=user.display_name,
    )


@router.get("/me/tutor-profile", response_model=TutorProfileResponse)
def get_my_tutor_profile(
    user=Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> TutorProfileResponse:
    """Return or initialize the tutor profile for the authenticated user."""
    profile = get_tutor_profile(db, user_id=user.id)
    return TutorProfileResponse(
        readiness_summary=profile.get("readiness_summary", ""),
        learning_style_notes=profile.get("learning_style_notes", ""),
        last_activity_at=(
            str(profile["last_activity_at"]) if profile.get("last_activity_at") else None
        ),
    )


__all__ = ["router"]
