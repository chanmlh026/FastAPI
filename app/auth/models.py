from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.auth.constants import EMAIL_UNIQUE_INDEX, MAX_EMAIL_LENGTH
from app.db.database import Base


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(MAX_EMAIL_LENGTH), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=true()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index(EMAIL_UNIQUE_INDEX, func.lower(email), unique=True),)
