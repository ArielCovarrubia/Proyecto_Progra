from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class VehiculoDB(Base):
    __tablename__ = "vehiculos"

    patente: Mapped[str] = mapped_column(String(20), primary_key=True)
    responsable: Mapped[str] = mapped_column(String(120), nullable=False)
    contacto: Mapped[str] = mapped_column(String(120), nullable=False)

    estadias: Mapped[list[EstadiaDB]] = relationship(back_populates="vehiculo")
    suscripciones: Mapped[list[SuscripcionDB]] = relationship(back_populates="vehiculo")


class EstadiaDB(Base):
    __tablename__ = "estadias"
    __table_args__ = (
        Index(
            "uq_estadia_activa_por_vehiculo",
            "patente",
            unique=True,
            sqlite_where=text("salida IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patente: Mapped[str] = mapped_column(
        ForeignKey("vehiculos.patente"), nullable=False, index=True
    )
    ingreso: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    salida: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    modalidad: Mapped[str] = mapped_column(String(20), nullable=False)
    suscripcion_id: Mapped[int | None] = mapped_column(
        ForeignKey("suscripciones.id"), nullable=True
    )
    importe: Mapped[int | None] = mapped_column(Integer, nullable=True)

    vehiculo: Mapped[VehiculoDB] = relationship(back_populates="estadias")
    suscripcion: Mapped[SuscripcionDB | None] = relationship(
        back_populates="estadias"
    )
    pago: Mapped[PagoDB | None] = relationship(
        back_populates="estadia", uselist=False
    )


class SuscripcionDB(Base):
    __tablename__ = "suscripciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patente: Mapped[str] = mapped_column(
        ForeignKey("vehiculos.patente"), nullable=False, index=True
    )
    inicio: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    termino: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    importe: Mapped[int] = mapped_column(Integer, nullable=False)

    vehiculo: Mapped[VehiculoDB] = relationship(back_populates="suscripciones")
    estadias: Mapped[list[EstadiaDB]] = relationship(back_populates="suscripcion")
    pago: Mapped[PagoDB | None] = relationship(
        back_populates="suscripcion", uselist=False
    )


class PagoDB(Base):
    __tablename__ = "pagos"
    __table_args__ = (
        CheckConstraint(
            "(estadia_id IS NOT NULL AND suscripcion_id IS NULL) OR "
            "(estadia_id IS NULL AND suscripcion_id IS NOT NULL)",
            name="ck_pago_un_solo_origen",
        ),
        CheckConstraint("importe >= 0", name="ck_pago_importe_no_negativo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    estadia_id: Mapped[int | None] = mapped_column(
        ForeignKey("estadias.id"), nullable=True, unique=True
    )
    suscripcion_id: Mapped[int | None] = mapped_column(
        ForeignKey("suscripciones.id"), nullable=True, unique=True
    )
    modalidad: Mapped[str] = mapped_column(String(20), nullable=False)
    importe: Mapped[int] = mapped_column(Integer, nullable=False)
    registrado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    estadia: Mapped[EstadiaDB | None] = relationship(back_populates="pago")
    suscripcion: Mapped[SuscripcionDB | None] = relationship(back_populates="pago")
