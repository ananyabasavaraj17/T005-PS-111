from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.id_generator import get_id_generator


class StretchGoal(Base):
    __tablename__ = "stretch_goals"

    id: Mapped[str] = mapped_column(
        String(50), primary_key=True, default=get_id_generator("sg")
    )

    campaign_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("campaigns.id"), nullable=False
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)

    description: Mapped[str] = mapped_column(String(500), nullable=False)

    target_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )

    is_unlocked: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
