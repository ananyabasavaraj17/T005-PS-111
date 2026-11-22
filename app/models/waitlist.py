from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.id_generator import get_id_generator


class Waitlist(Base):
    __tablename__ = "waitlist"

    id: Mapped[str] = mapped_column(
        String(50), primary_key=True, default=get_id_generator("wtl")
    )

    campaign_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("campaigns.id"), nullable=False
    )

    tier_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("reward_tiers.id"), nullable=False
    )

    backer_id: Mapped[str] = mapped_column(
        String(100), nullable=False
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(30), default="WAITING", nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
