"""Persistencia contractual del certificado al comitente."""
import sqlite3
from decimal import Decimal
from unittest.mock import patch
import pytest
from core.certificados_comitente_registro import (
    inicializar, registrar_desde_medicion, cambiar_estado,
)


def _db():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE proyectos(id INTEGER PRIMARY KEY)")
    db.execute("CREATE TABLE valorizaciones(id INTEGER PRIMARY KEY, proyecto_id INTEGER)")
    db.execute("INSERT INTO proyectos VALUES(1)")
    db.execute("INSERT INTO valorizaciones VALUES(8,1)")
    inicializar(db)
    return db


def test_registrar_no_duplica_medicion_y_guarda_importes():
    db = _db()
    dato = {"costo_directo": Decimal("1000.00"),
            "total": Decimal("1391.50"),
            "adicionales": [("Gastos generales", Decimal("100.00"))]}
    with patch("core.certificados_comitente_registro.resumen_comitente", return_value=dato):
        cid = registrar_desde_medicion(db, 1, 8)
        row = db.execute("SELECT numero,estado,total FROM certificados_comitente WHERE id=?",
                         (cid,)).fetchone()
        assert row == (1, "borrador", "1391.50")
        with pytest.raises(ValueError):
            registrar_desde_medicion(db, 1, 8)


def test_aprobado_no_vuelve_a_borrador():
    db = _db()
    dato = {"costo_directo": Decimal("1000"), "total": Decimal("1000"), "adicionales": []}
    with patch("core.certificados_comitente_registro.resumen_comitente", return_value=dato):
        cid = registrar_desde_medicion(db, 1, 8)
    cambiar_estado(db, cid, "aprobado")
    with pytest.raises(ValueError):
        cambiar_estado(db, cid, "borrador")
