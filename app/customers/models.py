from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.customers.constants import MAX_NAME_LENGTH


class CustomerModel(Base):
    __tablename__ = "customers"

    customer_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=False
    )

    name: Mapped[str] = mapped_column(String(MAX_NAME_LENGTH), nullable=False)
