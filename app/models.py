from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import ForeignKey, String, Integer, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


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
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    
    # Foreign key referencing subscription_tiers. Default is 1 (BASIC tier)
    tier_id: Mapped[int] = mapped_column(
        ForeignKey("subscription_tiers.id"), 
        nullable=False, 
        default=1
    )
    
    # Relationships
    tier: Mapped["SubscriptionTier"] = relationship("SubscriptionTier", back_populates="users")
    usage_logs: Mapped[list["UsageLog"]] = relationship("UsageLog", back_populates="user", cascade="all, delete-orphan")


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