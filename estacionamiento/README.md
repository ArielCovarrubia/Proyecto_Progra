# Módulo de dominio y persistencia

Este paquete contiene las reglas de cobro, los modelos SQLAlchemy y los servicios que
puede utilizar la interfaz Tkinter.

## Tarifas iniciales

Las tarifas de referencia están expresadas en pesos chilenos: $200 por minuto,
$5.000 por día y $45.000 por suscripción de 30 días. El equipo debe acordar estos
valores antes de la entrega; se pueden cambiar al crear `Tarifas`.

## Inicialización

```python
from estacionamiento import Database, ServicioEstacionamiento, Tarifas

db = Database("sqlite:///estacionamiento.db")
servicio = ServicioEstacionamiento(
    db,
    Tarifas(por_minuto=200, diaria=5000, mensual=45000),
)
```

La creación de `Database` crea las tablas si aún no existen. `db.cerrar()` libera la
conexión al cerrar la aplicación.

## Operaciones disponibles

```python
from datetime import datetime
from estacionamiento import TipoModalidad

servicio.registrar_vehiculo("ABCD12", "Nombre responsable", "correo o teléfono")
servicio.registrar_ingreso(
    "ABCD12", TipoModalidad.POR_MINUTO, datetime(2026, 1, 1, 9, 0)
)
estadia = servicio.registrar_salida("ABCD12", datetime(2026, 1, 1, 9, 2))
print(estadia.importe)
```

Las modalidades de ingreso son `TipoModalidad.POR_MINUTO` y `TipoModalidad.DIARIA`.
Una suscripción mensual vigente se aplica automáticamente:

```python
suscripcion = servicio.contratar_suscripcion("ABCD12", datetime(2026, 1, 1, 9))
presentes = servicio.vehiculos_presentes()
vehiculos = servicio.listar_vehiculos()
estadias = servicio.historial_estadias(patente="ABCD12")
pagos = servicio.historial_pagos(modalidad=TipoModalidad.MENSUAL)
```

La suscripción cubre el ingreso desde su inicio inclusive hasta su término exclusivo.
Una estadía que ingresó bajo cobertura conserva esa modalidad hasta la salida y no crea
un pago adicional. Los pagos mensuales se registran al contratar.

Las búsquedas por período de `historial_estadias` usan la fecha de ingreso; las de
`historial_pagos` usan la fecha de registro del pago. Las fechas deben ser `datetime`
locales sin zona horaria. Los servicios devuelven instancias SQLAlchemy con los campos
del registro, como `EstadiaDB.modalidad`, `EstadiaDB.ingreso` y `PagoDB.importe`.

## Pruebas

Desde la raíz del proyecto:

```powershell
python -m pip install -r requirements.txt
python -m pytest -q
```
