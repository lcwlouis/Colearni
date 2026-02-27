"""Authentication/session persistence helpers."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class UserRow:
    id: int
    public_id: str
    email: str
    display_name: str | None


@dataclass(frozen=True)
class AuthSessionRow:
    id: int
    public_id: str
    user_id: int
    token_hash: str
    expires_at: datetime
    revoked_at: datetime | None


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_magic_link_token(
    session: Session,
    *,
    email: str,
    ttl_minutes: int = 30,
) -> tuple[str, datetime]:
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_token(raw_token)
    expires_at = _utc_now() + timedelta(minutes=max(1, ttl_minutes))

    session.execute(
        text(
            """
            INSERT INTO auth_magic_links (email, token_hash, expires_at)
            VALUES (:email, :token_hash, :expires_at)
            """
        ),
        {
            "email": email.strip().lower(),
            "token_hash": token_hash,
            "expires_at": expires_at,
        },
    )
    session.commit()
    return raw_token, expires_at


def consume_magic_link_token(session: Session, *, raw_token: str) -> str | None:
    token_hash = hash_token(raw_token)
    row = (
        session.execute(
            text(
                """
                SELECT id, email
                FROM auth_magic_links
                WHERE token_hash = :token_hash
                  AND consumed_at IS NULL
                  AND expires_at > now()
                ORDER BY id DESC
                LIMIT 1
                FOR UPDATE
                """
            ),
            {"token_hash": token_hash},
        )
        .mappings()
        .first()
    )
    if row is None:
        session.rollback()
        return None

    session.execute(
        text(
            """
            UPDATE auth_magic_links
            SET consumed_at = now()
            WHERE id = :id
            """
        ),
        {"id": int(row["id"])},
    )
    session.commit()
    return str(row["email"]).strip().lower()


def get_or_create_user_by_email(
    session: Session,
    *,
    email: str,
    display_name: str | None = None,
) -> UserRow:
    normalized_email = email.strip().lower()
    normalized_name = (display_name or "").strip() or None

    row = (
        session.execute(
            text(
                """
                INSERT INTO users (email, display_name)
                VALUES (:email, :display_name)
                ON CONFLICT (email)
                DO UPDATE
                    SET display_name = COALESCE(users.display_name, EXCLUDED.display_name),
                        updated_at = now()
                RETURNING id, public_id, email, display_name
                """
            ),
            {"email": normalized_email, "display_name": normalized_name},
        )
        .mappings()
        .one()
    )
    session.commit()
    return UserRow(
        id=int(row["id"]),
        public_id=str(row["public_id"]),
        email=str(row["email"]),
        display_name=str(row["display_name"]) if row["display_name"] is not None else None,
    )


def issue_auth_session(
    session: Session,
    *,
    user_id: int,
    ttl_days: int = 14,
) -> tuple[str, AuthSessionRow]:
    raw_token = secrets.token_urlsafe(48)
    token_hash = hash_token(raw_token)
    expires_at = _utc_now() + timedelta(days=max(1, ttl_days))

    row = (
        session.execute(
            text(
                """
                INSERT INTO auth_sessions (user_id, token_hash, expires_at, last_seen_at)
                VALUES (:user_id, :token_hash, :expires_at, now())
                RETURNING id, public_id, user_id, token_hash, expires_at, revoked_at
                """
            ),
            {
                "user_id": user_id,
                "token_hash": token_hash,
                "expires_at": expires_at,
            },
        )
        .mappings()
        .one()
    )
    session.commit()
    return raw_token, AuthSessionRow(
        id=int(row["id"]),
        public_id=str(row["public_id"]),
        user_id=int(row["user_id"]),
        token_hash=str(row["token_hash"]),
        expires_at=row["expires_at"],
        revoked_at=row["revoked_at"],
    )


def get_user_for_auth_token(session: Session, *, raw_token: str) -> UserRow | None:
    token_hash = hash_token(raw_token)
    row = (
        session.execute(
            text(
                """
                SELECT
                    u.id,
                    u.public_id,
                    u.email,
                    u.display_name,
                    s.id AS auth_session_id
                FROM auth_sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.token_hash = :token_hash
                  AND s.revoked_at IS NULL
                  AND s.expires_at > now()
                LIMIT 1
                """
            ),
            {"token_hash": token_hash},
        )
        .mappings()
        .first()
    )
    if row is None:
        return None

    session.execute(
        text(
            """
            UPDATE auth_sessions
            SET last_seen_at = now()
            WHERE id = :id
            """
        ),
        {"id": int(row["auth_session_id"])},
    )
    session.commit()

    return UserRow(
        id=int(row["id"]),
        public_id=str(row["public_id"]),
        email=str(row["email"]),
        display_name=str(row["display_name"]) if row["display_name"] is not None else None,
    )


def revoke_auth_session(session: Session, *, raw_token: str) -> None:
    token_hash = hash_token(raw_token)
    session.execute(
        text(
            """
            UPDATE auth_sessions
            SET revoked_at = now()
            WHERE token_hash = :token_hash
              AND revoked_at IS NULL
            """
        ),
        {"token_hash": token_hash},
    )
    session.commit()


def get_user_by_id(session: Session, *, user_id: int) -> UserRow | None:
    row = (
        session.execute(
            text(
                """
                SELECT id, public_id, email, display_name
                FROM users
                WHERE id = :user_id
                LIMIT 1
                """
            ),
            {"user_id": user_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    return UserRow(
        id=int(row["id"]),
        public_id=str(row["public_id"]),
        email=str(row["email"]),
        display_name=str(row["display_name"]) if row["display_name"] is not None else None,
    )


def get_tutor_profile(session: Session, *, user_id: int) -> dict[str, object]:
    row = (
        session.execute(
            text(
                """
                INSERT INTO user_tutor_profile (user_id)
                VALUES (:user_id)
                ON CONFLICT (user_id)
                DO UPDATE SET updated_at = user_tutor_profile.updated_at
                RETURNING user_id, readiness_summary, learning_style_notes, last_activity_at
                """
            ),
            {"user_id": user_id},
        )
        .mappings()
        .one()
    )
    session.commit()
    return {
        "user_id": int(row["user_id"]),
        "readiness_summary": str(row["readiness_summary"] or ""),
        "learning_style_notes": str(row["learning_style_notes"] or ""),
        "last_activity_at": row["last_activity_at"],
    }


def touch_user_activity(session: Session, *, user_id: int) -> None:
    session.execute(
        text(
            """
            INSERT INTO user_tutor_profile (user_id, last_activity_at)
            VALUES (:user_id, now())
            ON CONFLICT (user_id)
            DO UPDATE SET last_activity_at = now(), updated_at = now()
            """
        ),
        {"user_id": user_id},
    )
