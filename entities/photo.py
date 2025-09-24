# entities/photo.py
import enum
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Boolean, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from db.database import Base

class GeneroEnum(str, enum.Enum):
    masculino = "masculino"
    feminino = "feminino"

class Photo(Base):
    __tablename__ = "fotos"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    original_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    ia_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    quantidade: Mapped[int] = mapped_column(Integer, default=0)
    impressa: Mapped[bool] = mapped_column(Boolean, default=False)

    genero: Mapped[GeneroEnum | None] = mapped_column(SAEnum(GeneroEnum, name="genero_enum"), nullable=True)
    tema: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                                                 onupdate=lambda: datetime.now(timezone.utc))
