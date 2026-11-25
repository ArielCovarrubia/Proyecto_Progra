from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from math import ceil


def _validar_fecha(fecha: datetime, nombre: str) -> None:
    if not isinstance(fecha, datetime):
        raise TypeError(f"{nombre} debe ser una fecha y hora.")
    if fecha.tzinfo is not None and fecha.utcoffset() is not None:
        raise ValueError("Use fechas y horas locales sin zona horaria.")


def _segundos_entre(inicio: datetime, termino: datetime) -> float:
    _validar_fecha(inicio, "La fecha de inicio")
    _validar_fecha(termino, "La fecha de término")
    if termino < inicio:
        raise ValueError("La fecha de término no puede ser anterior al inicio.")
    return (termino - inicio).total_seconds()


def _validar_tarifa(tarifa: int) -> None:
    if isinstance(tarifa, bool) or not isinstance(tarifa, int) or tarifa <= 0:
        raise ValueError("La tarifa debe ser un número entero de pesos mayor que cero.")


def _normalizar_patente(patente: str) -> str:
    if not isinstance(patente, str):
        raise TypeError("La patente debe ser texto.")
    patente_normalizada = patente.strip().upper()
    if not patente_normalizada:
        raise ValueError("La patente no puede estar vacía.")
    return patente_normalizada


class TipoModalidad:
    POR_MINUTO = "por_minuto"
    DIARIA = "diaria"
    MENSUAL = "mensual"


class Tarifas:
    def __init__(
        self,
        por_minuto: int = 200,
        diaria: int = 5000,
        mensual: int = 45000,
    ) -> None:
        _validar_tarifa(por_minuto)
        _validar_tarifa(diaria)
        _validar_tarifa(mensual)
        self.__por_minuto = por_minuto
        self.__diaria = diaria
        self.__mensual = mensual

    @property
    def por_minuto(self) -> int:
        return self.__por_minuto

    @por_minuto.setter
    def por_minuto(self, tarifa: int) -> None:
        _validar_tarifa(tarifa)
        self.__por_minuto = tarifa

    @property
    def diaria(self) -> int:
        return self.__diaria

    @diaria.setter
    def diaria(self, tarifa: int) -> None:
        _validar_tarifa(tarifa)
        self.__diaria = tarifa

    @property
    def mensual(self) -> int:
        return self.__mensual

    @mensual.setter
    def mensual(self, tarifa: int) -> None:
        _validar_tarifa(tarifa)
        self.__mensual = tarifa


class Vehiculo:
    def __init__(self, patente: str, responsable: str, contacto: str) -> None:
        self.patente = patente
        self.responsable = responsable
        self.contacto = contacto

    @property
    def patente(self) -> str:
        return self.__patente

    @patente.setter
    def patente(self, patente: str) -> None:
        self.__patente = _normalizar_patente(patente)

    @property
    def responsable(self) -> str:
        return self.__responsable

    @responsable.setter
    def responsable(self, responsable: str) -> None:
        if not isinstance(responsable, str) or not responsable.strip():
            raise ValueError("El nombre de la persona responsable no puede estar vacío.")
        self.__responsable = responsable.strip()

    @property
    def contacto(self) -> str:
        return self.__contacto

    @contacto.setter
    def contacto(self, contacto: str) -> None:
        if not isinstance(contacto, str) or not contacto.strip():
            raise ValueError("El contacto de la persona responsable no puede estar vacío.")
        self.__contacto = contacto.strip()


class ModalidadCobro(ABC):
    codigo: str

    def __init__(self, tarifa: int) -> None:
        _validar_tarifa(tarifa)
        self.__tarifa = tarifa

    @property
    def tarifa(self) -> int:
        return self.__tarifa

    @tarifa.setter
    def tarifa(self, tarifa: int) -> None:
        _validar_tarifa(tarifa)
        self.__tarifa = tarifa

    @abstractmethod
    def calcular(self, ingreso: datetime, salida: datetime) -> int:
        raise NotImplementedError


class ModalidadPorMinuto(ModalidadCobro):
    codigo = TipoModalidad.POR_MINUTO

    def calcular(self, ingreso: datetime, salida: datetime) -> int:
        segundos = _segundos_entre(ingreso, salida)
        minutos = max(1, ceil(segundos / 60))
        return minutos * self.tarifa


class ModalidadDiaria(ModalidadCobro):
    codigo = TipoModalidad.DIARIA

    def calcular(self, ingreso: datetime, salida: datetime) -> int:
        segundos = _segundos_entre(ingreso, salida)
        dias = max(1, ceil(segundos / timedelta(days=1).total_seconds()))
        return dias * self.tarifa


class ModalidadMensual(ModalidadCobro):
    codigo = TipoModalidad.MENSUAL

    @property
    def importe_contratacion(self) -> int:
        return self.tarifa

    def calcular(self, ingreso: datetime, salida: datetime) -> int:
        _segundos_entre(ingreso, salida)
        return 0


class Suscripcion:
    DURACION = timedelta(days=30)

    def __init__(
        self,
        patente: str,
        inicio: datetime,
        termino: datetime,
        tarifa: int,
    ) -> None:
        _validar_fecha(inicio, "El inicio")
        _validar_fecha(termino, "El término")
        if termino - inicio != self.DURACION:
            raise ValueError("La suscripción debe durar exactamente 30 días.")
        self.__patente = _normalizar_patente(patente)
        self.__inicio = inicio
        self.__termino = termino
        self.__modalidad = ModalidadMensual(tarifa)

    @property
    def patente(self) -> str:
        return self.__patente

    @property
    def inicio(self) -> datetime:
        return self.__inicio

    @property
    def termino(self) -> datetime:
        return self.__termino

    @property
    def importe(self) -> int:
        return self.__modalidad.importe_contratacion

    def vigente_en(self, fecha: datetime) -> bool:
        _validar_fecha(fecha, "La fecha de consulta")
        return self.__inicio <= fecha < self.__termino

    def se_superpone(self, otra: Suscripcion) -> bool:
        return self.__inicio < otra.termino and otra.inicio < self.__termino


class Estadia:
    def __init__(
        self,
        patente: str,
        ingreso: datetime,
        modalidad: ModalidadCobro,
    ) -> None:
        _validar_fecha(ingreso, "El ingreso")
        self.__patente = _normalizar_patente(patente)
        self.__ingreso = ingreso
        self.__modalidad = modalidad
        self.__salida: datetime | None = None

    @property
    def patente(self) -> str:
        return self.__patente

    @property
    def ingreso(self) -> datetime:
        return self.__ingreso

    @property
    def salida(self) -> datetime | None:
        return self.__salida

    @property
    def modalidad(self) -> ModalidadCobro:
        return self.__modalidad

    def finalizar(self, salida: datetime) -> int:
        if self.__salida is not None:
            raise ValueError("La estadía ya fue finalizada.")
        importe = self.__modalidad.calcular(self.__ingreso, salida)
        self.__salida = salida
        return importe


class Pago:
    def __init__(self, importe: int, modalidad: str, registrado_en: datetime) -> None:
        if isinstance(importe, bool) or not isinstance(importe, int) or importe < 0:
            raise ValueError("El importe del pago debe ser un entero no negativo.")
        _validar_fecha(registrado_en, "La fecha del pago")
        self.__importe = importe
        self.__modalidad = modalidad
        self.__registrado_en = registrado_en

    @property
    def importe(self) -> int:
        return self.__importe

    @property
    def modalidad(self) -> str:
        return self.__modalidad

    @property
    def registrado_en(self) -> datetime:
        return self.__registrado_en
