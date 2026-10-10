"""Pruebas del identificador interno de insumos de CPconstruccion."""
import sqlite3
from core.database import siguiente_codigo_recurso


def _db():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE recursos (codigo TEXT)")
    return db


def test_codigo_independiente_de_inei():
    db = _db()
    db.execute("INSERT INTO recursos VALUES ('4700001')")
    assert siguiente_codigo_recurso(db) == '9900001'
    db.execute("INSERT INTO recursos VALUES ('9900001')")
    assert siguiente_codigo_recurso(db) == '9900002'
    db.close()


def test_codigo_salta_al_mayor_existente():
    db = _db()
    db.executemany("INSERT INTO recursos VALUES (?)", [('9900010',), ('9900003',)])
    assert siguiente_codigo_recurso(db) == '9900011'
    db.close()
