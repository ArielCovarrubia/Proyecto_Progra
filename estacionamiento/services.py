from datetime import datetime, timedelta
from typing import TypeAlias

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from estacionamiento.database import Database
from estacionamiento.domain import (
    Estadia,
    ModalidadCobro,
    ModalidadDiaria,
    ModalidadMensual,
    ModalidadPorMinuto,
    Pago,
    Suscripcion,
    Tarifas,
    TipoModalidad,
    Vehiculo,
)
from estacionamiento.models import EstadiaDB, PagoDB, SuscripcionDB, VehiculoDB

Fecha: TypeAlias = datetime | None


class ServicioEstacionamiento:
    def __init__(self, database: Database, tarifas: Tarifas | None = None) -> None:
        self.__database = database
        self.__tarifas = tarifas or Tarifas()

    @property
    def tarifas(self) -> Tarifas:
        return self.__tarifas

    def registrar_vehiculo(
        self, patente: str, responsable: str, contacto: str
    ) -> VehiculoDB:
        vehiculo = Vehiculo(patente, responsable, contacto)
        try:
            with self.__database.sesion() as session:
                if session.get(VehiculoDB, vehiculo.patente) is not None:
                    raise ValueError(f"Ya existe el vehículo {vehiculo.patente}.")
                registro = VehiculoDB(
                    patente=vehiculo.patente,
                    responsable=vehiculo.responsable,
                    contacto=vehiculo.contacto,
                )
                session.add(registro)
                session.flush()
                return registro
        except IntegrityError as error:
            raise ValueError(f"Ya existe el vehículo {vehiculo.patente}.") from error

    def registrar_ingreso(
        self,
        patente: str,
        modalidad: str,
        ingreso: Fecha = None,
    ) -> EstadiaDB:
        patente_normalizada = patente.strip().upper() if isinstance(patente, str) else ""
        if not patente_normalizada:
            raise ValueError("La patente no puede estar vacía.")
        fecha_ingreso = ingreso or datetime.now()
        with self.__database.sesion() as session:
            vehiculo = session.get(VehiculoDB, patente_normalizada)
            if vehiculo is None:
                raise ValueError(f"No existe el vehículo {patente_normalizada}.")
            activa = session.scalar(
                select(EstadiaDB).where(
                    EstadiaDB.patente == patente_normalizada,
                    EstadiaDB.salida.is_(None),
                )
            )
            if activa is not None:
                raise ValueError(
                    f"El vehículo {patente_normalizada} ya tiene una estadía activa."
                )

            suscripcion = session.scalar(
                select(SuscripcionDB).where(
                    SuscripcionDB.patente == patente_normalizada,
                    SuscripcionDB.inicio <= fecha_ingreso,
                    SuscripcionDB.termino > fecha_ingreso,
                )
            )
            if suscripcion is not None:
                modalidad_cobro = self.__crear_modalidad(TipoModalidad.MENSUAL)
            else:
                if modalidad == TipoModalidad.POR_MINUTO:
                    modalidad_cobro = self.__crear_modalidad(TipoModalidad.POR_MINUTO)
                elif modalidad == TipoModalidad.DIARIA:
                    modalidad_cobro = self.__crear_modalidad(TipoModalidad.DIARIA)
                else:
                    raise ValueError(
                        "La modalidad de ingreso debe ser 'por_minuto' o 'diaria'."
                    )

            estadia = Estadia(patente_normalizada, fecha_ingreso, modalidad_cobro)
            registro = EstadiaDB(
                patente=estadia.patente,
                ingreso=estadia.ingreso,
                modalidad=estadia.modalidad.codigo,
                suscripcion=suscripcion,
            )
            session.add(registro)
            try:
                session.flush()
            except IntegrityError as error:
                raise ValueError(
                    f"El vehículo {patente_normalizada} ya tiene una estadía activa."
                ) from error
            return registro

    def registrar_salida(self, patente: str, salida: Fecha = None) -> EstadiaDB:
        patente_normalizada = patente.strip().upper() if isinstance(patente, str) else ""
        if not patente_normalizada:
            raise ValueError("La patente no puede estar vacía.")
        fecha_salida = salida or datetime.now()
        with self.__database.sesion() as session:
            estadia_db = session.scalar(
                select(EstadiaDB).where(
                    EstadiaDB.patente == patente_normalizada,
                    EstadiaDB.salida.is_(None),
                )
            )
            if estadia_db is None:
                raise ValueError(
                    f"El vehículo {patente_normalizada} no tiene una estadía activa."
                )
            modalidad = self.__crear_modalidad(estadia_db.modalidad)
            estadia = Estadia(
                estadia_db.patente,
                estadia_db.ingreso,
                modalidad,
            )
            importe = estadia.finalizar(fecha_salida)
            pago = Pago(importe, modalidad.codigo, fecha_salida)
            estadia_db.salida = fecha_salida
            estadia_db.importe = importe
            if estadia_db.suscripcion_id is None:
                session.add(
                    PagoDB(
                        estadia=estadia_db,
                        modalidad=pago.modalidad,
                        importe=pago.importe,
                        registrado_en=pago.registrado_en,
                    )
                )
            session.flush()
            return estadia_db

    def contratar_suscripcion(
        self,
        patente: str,
        inicio: Fecha = None,
    ) -> SuscripcionDB:
        patente_normalizada = patente.strip().upper() if isinstance(patente, str) else ""
        if not patente_normalizada:
            raise ValueError("La patente no puede estar vacía.")
        fecha_inicio = inicio or datetime.now()
        fecha_termino = fecha_inicio + Suscripcion.DURACION
        nueva = Suscripcion(
            patente_normalizada,
            fecha_inicio,
            fecha_termino,
            self.__tarifas.mensual,
        )
        try:
            with self.__database.sesion() as session:
                if session.get(VehiculoDB, nueva.patente) is None:
                    raise ValueError(f"No existe el vehículo {nueva.patente}.")
                existentes = session.scalars(
                    select(SuscripcionDB).where(
                        SuscripcionDB.patente == nueva.patente,
                        SuscripcionDB.inicio < nueva.termino,
                        SuscripcionDB.termino > nueva.inicio,
                    )
                ).all()
                if existentes:
                    raise ValueError(
                        f"El vehículo {nueva.patente} ya tiene una suscripción "
                        "que se superpone con ese período."
                    )
                suscripcion_db = SuscripcionDB(
                    patente=nueva.patente,
                    inicio=nueva.inicio,
                    termino=nueva.termino,
                    importe=nueva.importe,
                )
                session.add(suscripcion_db)
                session.flush()
                pago = Pago(nueva.importe, TipoModalidad.MENSUAL, fecha_inicio)
                session.add(
                    PagoDB(
                        suscripcion=suscripcion_db,
                        modalidad=pago.modalidad,
                        importe=pago.importe,
                        registrado_en=pago.registrado_en,
                    )
                )
                session.flush()
                return suscripcion_db
        except IntegrityError as error:
            raise ValueError(
                f"No se pudo guardar la suscripción de {nueva.patente}."
            ) from error

    def vehiculos_presentes(self) -> list[EstadiaDB]:
        with self.__database.sesion() as session:
            return list(
                session.scalars(
                    select(EstadiaDB)
                    .where(EstadiaDB.salida.is_(None))
                    .order_by(EstadiaDB.ingreso)
                ).all()
            )

    def listar_vehiculos(self, patente: str | None = None) -> list[VehiculoDB]:
        consulta = select(VehiculoDB)
        if patente:
            patente_normalizada = patente.strip().upper()
            consulta = consulta.where(VehiculoDB.patente == patente_normalizada)
        with self.__database.sesion() as session:
            return list(
                session.scalars(consulta.order_by(VehiculoDB.patente)).all()
            )

    def historial_estadias(
        self,
        patente: str | None = None,
        desde: datetime | None = None,
        hasta: datetime | None = None,
        modalidad: str | None = None,
    ) -> list[EstadiaDB]:
        consulta = select(EstadiaDB)
        if patente:
            consulta = consulta.where(EstadiaDB.patente == patente.strip().upper())
        if desde is not None:
            consulta = consulta.where(EstadiaDB.ingreso >= desde)
        if hasta is not None:
            consulta = consulta.where(EstadiaDB.ingreso <= hasta)
        if modalidad is not None:
            consulta = consulta.where(EstadiaDB.modalidad == modalidad)
        with self.__database.sesion() as session:
            return list(
                session.scalars(consulta.order_by(EstadiaDB.ingreso.desc())).all()
            )

    def historial_pagos(
        self,
        desde: datetime | None = None,
        hasta: datetime | None = None,
        modalidad: str | None = None,
    ) -> list[PagoDB]:
        consulta = select(PagoDB)
        if desde is not None:
            consulta = consulta.where(PagoDB.registrado_en >= desde)
        if hasta is not None:
            consulta = consulta.where(PagoDB.registrado_en <= hasta)
        if modalidad is not None:
            consulta = consulta.where(PagoDB.modalidad == modalidad)
        with self.__database.sesion() as session:
            return list(
                session.scalars(consulta.order_by(PagoDB.registrado_en.desc())).all()
            )

    def __crear_modalidad(self, codigo: str) -> ModalidadCobro:
        if codigo == TipoModalidad.POR_MINUTO:
            return ModalidadPorMinuto(self.__tarifas.por_minuto)
        if codigo == TipoModalidad.DIARIA:
            return ModalidadDiaria(self.__tarifas.diaria)
        if codigo == TipoModalidad.MENSUAL:
            return ModalidadMensual(self.__tarifas.mensual)
        raise ValueError(f"Modalidad desconocida: {codigo}.")
