"""Pruebas del cálculo de actualización contractual independiente del país."""
import sqlite3
from decimal import Decimal
from core.indices_genericos import (
    inicializar, guardar_valor, calcular_factor, actualizar_importe,
)


def _conexion():
    db = sqlite3.connect(":memory:")
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("CREATE TABLE proyectos(id INTEGER PRIMARY KEY)")
    db.execute("INSERT INTO proyectos(id) VALUES(1)")
    inicializar(db)
    db.execute("INSERT INTO fuentes_indices(id,nombre,pais) VALUES(1,'Fuente prueba','AR')")
    for id_, nombre in ((1, 'CAC'), (2, 'IPC'), (3, 'ICC')):
        db.execute(
            "INSERT INTO series_indices(id,fuente_id,codigo,nombre) VALUES(?,1,?,?)",
            (id_, nombre, nombre),
        )
    db.execute(
        "INSERT INTO formulas_actualizacion(id,proyecto_id,nombre,periodo_base,metodo)"
        " VALUES(1,1,'Mixta','2026-01','ponderado')"
    )
    for serie, peso, final in ((1, '50', '120'), (2, '30', '110'), (3, '20', '115')):
        db.execute("INSERT INTO formula_indices VALUES(1,?,?)", (serie, peso))
        guardar_valor(db, serie, '2026-01', 100)
        guardar_valor(db, serie, '2026-04', final)
    return db


def test_promedio_ponderado():
    db = _conexion()
    r = calcular_factor(db, 1, '2026-04')
    assert r['factor'] == Decimal('1.16')
    assert actualizar_importe(1000000, r['factor']) == Decimal('1160000.00')


def test_promedio_simple():
    db = _conexion()
    db.execute("UPDATE formulas_actualizacion SET metodo='simple' WHERE id=1")
    r = calcular_factor(db, 1, '2026-04')
    assert r['factor'] == Decimal('1.15')


def test_faltantes_rechazados():
    db = _conexion()
    db.execute("DELETE FROM valores_indices WHERE serie_id=3 AND periodo='2026-04'")
    try:
        calcular_factor(db, 1, '2026-04')
    except ValueError:
        pass
    else:
        assert False, 'El cálculo debe rechazar períodos incompletos'


def test_periodo_invalido():
    db = _conexion()
    try:
        guardar_valor(db, 1, '2026-13', 100)
    except ValueError:
        pass
    else:
        assert False


def test_idempotencia_tablas():
    db = _conexion()
    inicializar(db)
    assert db.execute("SELECT COUNT(*) FROM series_indices").fetchone()[0] == 3
