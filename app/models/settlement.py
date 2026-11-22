from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.id_generator import get_id_generator


class Settlement(Base):
    __tablename__ = "settlements"

    id: Mapped[str] = mapped_column(
        String(50), primary_key=True, default=get_id_generator("stl")
    )

    campaign_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("campaigns.id"), nullable=False
    )

    pledged_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )

    collected_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )

    successful_charge_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )

    platform_fee: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )

    processing_fee: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )

    gst_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )

    total_fees: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )

    net_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )

    reserve_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )

    reserve_remaining: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )

    payout_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )

    refund_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )

    chargeback_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )

    chargeback_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )

    reserve_frozen: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(30), default="PENDING", nullable=False
    )

    payout_due_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    reserve_release_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    settled_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
