
from decimal import Decimal
from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)

    description: Mapped[str] = mapped_column(Text, nullable=False)

    goal_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    funding_model: Mapped[str] = mapped_column(String(30), nullable=False)

    start_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    deadline: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    status: Mapped[str] = mapped_column(
        String(30), default="DRAFT", nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


    extension_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )

    extension_granted_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )


    creator_id: Mapped[str] = mapped_column(
        String(100), nullable=False
    )


