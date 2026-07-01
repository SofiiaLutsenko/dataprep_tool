from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import ForeignKey, String, Integer, DateTime, Enum, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def normalize_email(email: str) -> str:
    """Normalizes email at the API layer so duplicate registrations fail
    with a clean 400 instead of a raw IntegrityError. The functional
    index on User (ix_users_email_lower) is the actual source of truth
    for uniqueness — this just gives a nicer error path for the common
    case where writes go through the API."""
    return email.strip().lower()


# Enum for available subscription tiers
class TierType(PyEnum):
    BASIC = "basic"
    PRO = "pro"


class SubscriptionTier(Base):
    __tablename__ = "subscription_tiers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[TierType] = mapped_column(
        Enum(TierType),
        unique=True,
        nullable=False,
        default=TierType.BASIC
    )

    # Even with feature gating, a basic daily limit protects against DDoS/spam
    daily_request_limit: Mapped[int] = mapped_column(Integer, default=50)

    # Relationship to User table
    users: Mapped[list["User"]] = relationship("User", back_populates="tier")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # NOTE: no unique=True here — uniqueness is enforced by the functional
    # index below on lower(email), so case variants (Bob@x.com / bob@x.com)
    # can't both exist even if a write path bypasses normalize_email().
    email: Mapped[str] = mapped_column(String, nullable=False)

    hashed_password: Mapped[str] = mapped_column(String, nullable=False)

    # Идентификаторы для интеграции со Stripe
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, unique=True, index=True)

    # Foreign key referencing subscription_tiers. Default is 1 (BASIC tier).
    # NOTE: this assumes a BASIC row exists at id=1 — seeded in main.py's
    # lifespan handler on startup.
    tier_id: Mapped[int] = mapped_column(
        ForeignKey("subscription_tiers.id"),
        nullable=False,
        default=1
    )

    # Relationships
    tier: Mapped["SubscriptionTier"] = relationship("SubscriptionTier", back_populates="users")
    usage_logs: Mapped[list["UsageLog"]] = relationship("UsageLog", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        # DB-level guarantee of case-insensitive email uniqueness.
        # If you already have a users table, this needs a migration
        # (Alembic, or manual DROP/CREATE INDEX) — it won't retroactively
        # apply to an existing schema just by restarting the app.
        Index("ix_users_email_lower", func.lower(email), unique=True),
    )


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Timestamp of the request (UTC)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    # Metadata for the request (e.g., "basic_masking", "pro_masking")
    action: Mapped[str] = mapped_column(String, nullable=False)

    # Relationship back to User table
    user: Mapped["User"] = relationship("User", back_populates="usage_logs")

    # Composite index — quota/rate-limit queries filter by user_id and
    # range-scan on timestamp (e.g. "how many requests today"). Without
    # this, that query is a sequential scan once the table grows.
    __table_args__ = (
        Index("ix_usage_logs_user_timestamp", "user_id", "timestamp"),
    )