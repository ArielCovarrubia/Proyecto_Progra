from datetime import datetime, timedelta

import pytest
from sqlalchemy import event

from estacionamiento import Database, ServicioEstacionamiento, Tarifas
from estacionamiento.domain import TipoModalidad
from estacionamiento.models import EstadiaDB, PagoDB


@pytest.fixture
def parking(tmp_path):
    database_path = tmp_path / "estacionamiento.db"
    database = Database(f"sqlite:///{database_path.as_posix()}")
    service = ServicioEstacionamiento(
        database,
        Tarifas(por_minuto=100, diaria=4000, mensual=30000),
    )
    yield database_path, database, service
    database.cerrar()


def registrar_auto(service: ServicioEstacionamiento) -> None:
    service.registrar_vehiculo(" abcd12 ", "Ariel", "ariel@example.com")


def test_entry_exit_records_payment_and_survives_reopening(parking) -> None:
    database_path, database, service = parking
    registrar_auto(service)
    ingreso = datetime(2026, 1, 1, 12)

    estadia = service.registrar_ingreso("ABCD12", TipoModalidad.POR_MINUTO, ingreso)
    finalizada = service.registrar_salida(
        "ABCD12", ingreso + timedelta(seconds=70)
    )

    assert estadia.modalidad == TipoModalidad.POR_MINUTO
    assert finalizada.importe == 200
    assert service.historial_pagos()[0].importe == 200
    database.cerrar()

    reopened = Database(f"sqlite:///{database_path.as_posix()}")
    reopened_service = ServicioEstacionamiento(
        reopened,
        Tarifas(por_minuto=100, diaria=4000, mensual=30000),
    )
    assert len(reopened_service.historial_estadias("ABCD12")) == 1
    assert len(reopened_service.historial_pagos()) == 1
    reopened.cerrar()


def test_subscription_covers_stay_without_second_payment(parking) -> None:
    _, _, service = parking
    registrar_auto(service)
    inicio = datetime(2026, 1, 1)
    suscripcion = service.contratar_suscripcion("ABCD12", inicio)

    estadia = service.registrar_ingreso(
        "ABCD12", TipoModalidad.DIARIA, inicio + timedelta(days=1)
    )
    finalizada = service.registrar_salida(
        "ABCD12", inicio + timedelta(days=31)
    )

    assert suscripcion.importe == 30000
    assert estadia.modalidad == TipoModalidad.MENSUAL
    assert finalizada.importe == 0
    assert len(service.historial_pagos()) == 1
    assert service.historial_pagos()[0].suscripcion_id == suscripcion.id


def test_expired_subscription_does_not_cover_next_stay(parking) -> None:
    _, _, service = parking
    registrar_auto(service)
    inicio = datetime(2026, 1, 1)
    service.contratar_suscripcion("ABCD12", inicio)

    estadia = service.registrar_ingreso(
        "ABCD12", TipoModalidad.DIARIA, inicio + timedelta(days=30)
    )

    assert estadia.modalidad == TipoModalidad.DIARIA
    assert estadia.suscripcion_id is None


def test_rejects_duplicate_active_stays_and_overlapping_subscriptions(parking) -> None:
    _, _, service = parking
    registrar_auto(service)
    inicio = datetime(2026, 1, 1)

    service.registrar_ingreso("ABCD12", TipoModalidad.DIARIA, inicio)
    service.contratar_suscripcion("ABCD12", inicio + timedelta(days=10))
    with pytest.raises(ValueError, match="estadía activa"):
        service.registrar_ingreso(
            "ABCD12", TipoModalidad.POR_MINUTO, inicio + timedelta(minutes=1)
        )

    with pytest.raises(ValueError, match="superpone"):
        service.contratar_suscripcion("ABCD12", inicio + timedelta(days=11))


def test_failed_exit_rolls_back_without_closing_active_stay(parking) -> None:
    _, _, service = parking
    registrar_auto(service)
    ingreso = datetime(2026, 1, 1)
    service.registrar_ingreso("ABCD12", TipoModalidad.POR_MINUTO, ingreso)

    with pytest.raises(ValueError, match="anterior"):
        service.registrar_salida("ABCD12", ingreso - timedelta(seconds=1))

    actuales = service.vehiculos_presentes()
    assert len(actuales) == 1
    assert actuales[0].salida is None
    assert service.historial_pagos() == []


def test_exit_and_payment_are_rolled_back_together_when_payment_fails(parking) -> None:
    _, _, service = parking
    registrar_auto(service)
    ingreso = datetime(2026, 1, 1)
    service.registrar_ingreso("ABCD12", TipoModalidad.POR_MINUTO, ingreso)

    def fallar_pago(*args: object) -> None:
        raise RuntimeError(
            f"No se pudo registrar el pago ({len(args)} argumentos)."
        )

    event.listen(PagoDB, "before_insert", fallar_pago)
    try:
        with pytest.raises(RuntimeError, match="registrar el pago"):
            service.registrar_salida("ABCD12", ingreso + timedelta(minutes=1))
    finally:
        event.remove(PagoDB, "before_insert", fallar_pago)

    assert len(service.vehiculos_presentes()) == 1
    assert service.historial_pagos() == []


def test_subscription_and_payment_are_rolled_back_together_when_payment_fails(
    parking,
) -> None:
    _, _, service = parking
    registrar_auto(service)
    inicio = datetime(2026, 1, 1)

    def fallar_pago(*args: object) -> None:
        raise RuntimeError(
            f"No se pudo registrar el pago ({len(args)} argumentos)."
        )

    event.listen(PagoDB, "before_insert", fallar_pago)
    try:
        with pytest.raises(RuntimeError, match="registrar el pago"):
            service.contratar_suscripcion("ABCD12", inicio)
    finally:
        event.remove(PagoDB, "before_insert", fallar_pago)

    assert service.historial_pagos() == []
    assert service.registrar_ingreso(
        "ABCD12", TipoModalidad.DIARIA, inicio
    ).suscripcion_id is None


def test_present_and_history_queries_can_filter_by_plate_and_modality(parking) -> None:
    _, _, service = parking
    registrar_auto(service)
    inicio = datetime(2026, 1, 1)
    service.registrar_ingreso("ABCD12", TipoModalidad.DIARIA, inicio)

    presentes: list[EstadiaDB] = service.vehiculos_presentes()
    historico = service.historial_estadias(
        patente=" abcd12 ", modalidad=TipoModalidad.DIARIA
    )

    assert len(presentes) == len(historico) == 1
