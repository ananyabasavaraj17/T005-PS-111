
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StretchGoal(Base):
    __tablename__ = "stretch_goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id"), nullable=False
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)

    description: Mapped[str] = mapped_column(String(500), nullable=False)

    target_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )

    is_unlocked: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
