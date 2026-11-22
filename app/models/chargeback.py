from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.id_generator import get_id_generator


class Chargeback(Base):
    __tablename__ = "chargebacks"

    id: Mapped[str] = mapped_column(
        String(50), primary_key=True, default=get_id_generator("chb")
    )

    pledge_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("pledges.id"), nullable=False
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )

    chargeback_fee: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("500.00"), nullable=False
    )

    reason: Mapped[str] = mapped_column(String(200), nullable=False)

    status: Mapped[str] = mapped_column(
        String(30), default="OPEN", nullable=False
    )

    reserve_amount_used: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
