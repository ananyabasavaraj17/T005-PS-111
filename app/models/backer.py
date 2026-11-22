from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Backer(Base):
    __tablename__ = "backers"

    backer_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    backer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    device_id: Mapped[str] = mapped_column(String(50), nullable=False)
