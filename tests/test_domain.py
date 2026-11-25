from datetime import datetime, timedelta

import pytest

from estacionamiento.domain import (
    ModalidadDiaria,
    ModalidadMensual,
    ModalidadPorMinuto,
    Suscripcion,
    Tarifas,
    Vehiculo,
)


def test_minute_rate_rounds_up_partial_minutes_and_charges_minimum() -> None:
    ingreso = datetime(2026, 1, 1, 12)
    modalidad = ModalidadPorMinuto(100)

    assert modalidad.calcular(ingreso, ingreso + timedelta(seconds=70)) == 200
    assert modalidad.calcular(ingreso, ingreso) == 100


def test_daily_rate_rounds_up_partial_days() -> None:
    ingreso = datetime(2026, 1, 1, 12)
    modalidad = ModalidadDiaria(5000)

    assert modalidad.calcular(ingreso, ingreso + timedelta(hours=24)) == 5000
    assert modalidad.calcular(ingreso, ingreso + timedelta(hours=24, minutes=1)) == 10000


def test_monthly_subscription_has_exclusive_end_and_zero_stay_charge() -> None:
    inicio = datetime(2026, 1, 1)
    termino = inicio + timedelta(days=30)
    suscripcion = Suscripcion(" abcd12 ", inicio, termino, 45000)
    modalidad = ModalidadMensual(45000)

    assert suscripcion.vigente_en(inicio)
    assert not suscripcion.vigente_en(termino)
    assert modalidad.importe_contratacion == 45000
    assert modalidad.calcular(inicio, termino + timedelta(days=1)) == 0


def test_subscription_period_must_be_exactly_thirty_days() -> None:
    inicio = datetime(2026, 1, 1)

    with pytest.raises(ValueError, match="30 días"):
        Suscripcion("ABCD12", inicio, inicio + timedelta(days=29), 45000)


def test_domain_rejects_empty_vehicle_and_nonpositive_rates() -> None:
    with pytest.raises(ValueError, match="patente"):
        Vehiculo("  ", "Responsable", "contacto")
    with pytest.raises(ValueError, match="mayor que cero"):
        Tarifas(por_minuto=0)


def test_domain_setters_validate_and_normalize_values() -> None:
    vehiculo = Vehiculo("abcd12", "Ariel", "contacto")
    modalidad = ModalidadPorMinuto(100)

    vehiculo.patente = " xy1234 "
    modalidad.tarifa = 250

    assert vehiculo.patente == "XY1234"
    assert modalidad.tarifa == 250
    with pytest.raises(ValueError, match="patente"):
        vehiculo.patente = " "
    with pytest.raises(ValueError, match="mayor que cero"):
        modalidad.tarifa = -1


def test_subscription_overlap_allows_adjacent_periods() -> None:
    inicio = datetime(2026, 1, 1)
    primera = Suscripcion("ABCD12", inicio, inicio + timedelta(days=30), 45000)
    adyacente = Suscripcion(
        "ABCD12",
        inicio + timedelta(days=30),
        inicio + timedelta(days=60),
        45000,
    )
    superpuesta = Suscripcion(
        "ABCD12",
        inicio + timedelta(days=29),
        inicio + timedelta(days=59),
        45000,
    )

    assert not primera.se_superpone(adyacente)
    assert primera.se_superpone(superpuesta)
