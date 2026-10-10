import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from core.indices_genericos import inicializar, importar_csv


def _db():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE proyectos(id INTEGER PRIMARY KEY)")
    inicializar(db)
    db.execute("INSERT INTO fuentes_indices(id,nombre) VALUES(1,'Prueba')")
    db.execute("INSERT INTO series_indices(id,fuente_id,codigo,nombre) "
               "VALUES(1,1,'ABC','Serie')")
    return db


def test_importacion_csv():
    with TemporaryDirectory() as td:
        archivo = Path(td) / "historico.csv"
        archivo.write_text("periodo;valor\n2026-01;100,5\n2026-02;103,2\n", encoding="utf-8")
        db = _db()
        assert importar_csv(db, 1, str(archivo)) == 2
        assert db.execute("SELECT valor FROM valores_indices WHERE periodo='2026-02'").fetchone()[0] == "103.2"


def test_csv_invalido_no_escribe_parcialmente():
    with TemporaryDirectory() as td:
        archivo = Path(td) / "mal.csv"
        archivo.write_text("periodo,valor\n2026-01,100\n2026-13,150\n", encoding="utf-8")
        db = _db()
        try:
            importar_csv(db, 1, str(archivo))
        except ValueError:
            pass
        else:
            assert False
        assert db.execute("SELECT COUNT(*) FROM valores_indices").fetchone()[0] == 0
