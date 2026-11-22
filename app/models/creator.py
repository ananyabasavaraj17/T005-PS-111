from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Creator(Base):
    __tablename__ = "creators"

    creator_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    creator_name: Mapped[str] = mapped_column(String(200), nullable=False)
    team_member_backer_ids: Mapped[str] = mapped_column(
        String(500), default="", nullable=False
    )
