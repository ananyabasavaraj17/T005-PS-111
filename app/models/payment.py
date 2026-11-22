from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.id_generator import get_id_generator


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(
        String(50), primary_key=True, default=get_id_generator("pay")
    )

    pledge_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("pledges.id"), nullable=False
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(30), default="PENDING", nullable=False
    )

    attempt_number: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )

    attempted_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    failure_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    transaction_reference: Mapped[str | None] = mapped_column(
        String(150), nullable=True
    )
