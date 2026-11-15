
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Pledge(Base):
    __tablename__ = "pledges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id"), nullable=False
    )

    backer_id: Mapped[str] = mapped_column(String(100), nullable=False)

    tier_id: Mapped[int | None] = mapped_column(
        ForeignKey("reward_tiers.id"), nullable=True
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    status: Mapped[str] = mapped_column(
        String(30), default="PLEDGED", nullable=False
    )

    is_early_bird: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow,
        onupdate=datetime.utcnow, nullable=False
    )

    extra_contribution: Mapped[Decimal] = mapped_column(
    Numeric(12, 2),
    default=Decimal("0.00"),
    nullable=False
)