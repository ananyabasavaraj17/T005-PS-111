
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RewardTier(Base):
    __tablename__ = "reward_tiers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)

    family: Mapped[str] = mapped_column(String(100), nullable=False)

    description: Mapped[str] = mapped_column(String(500), nullable=False)

    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    quantity_limit: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    quantity_sold: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )

    is_early_bird: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    early_bird_discount: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0.00"), nullable=False
    )

    early_bird_limit: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )

    early_bird_claimed: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
