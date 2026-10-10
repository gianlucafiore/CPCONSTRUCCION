"""Los PDF de comitente leen el histórico, no la medición recalculada."""
import json
import sqlite3
from core.certificados_comitente_pdf import html_certificado_comitente


def test_pdf_conserva_valores_historicos_y_escapa_textos():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE proyectos(id INTEGER PRIMARY KEY,nombre TEXT)")
    db.execute(
        "CREATE TABLE valorizaciones(id INTEGER PRIMARY KEY,periodo_desde TEXT,periodo_hasta TEXT)"
    )
    db.execute(
        "CREATE TABLE certificados_comitente("
        "id INTEGER PRIMARY KEY,proyecto_id INTEGER,valorizacion_id INTEGER,"
        "numero INTEGER,fecha TEXT,estado TEXT,costo_directo TEXT,total TEXT,"
        "detalle_json TEXT)"
    )
    db.execute("INSERT INTO proyectos VALUES(1,'Obra <Central>')")
    db.execute("INSERT INTO valorizaciones VALUES(8,'2026-09-01','2026-09-30')")
    db.execute(
        "INSERT INTO certificados_comitente VALUES(1,1,8,3,'2026-10-01',"
        "'aprobado','1000','1230',?)",
        (json.dumps([{"nombre":"Gastos <obra>","importe":"230"}]),)
    )
    html = html_certificado_comitente(db, 1)
    assert "1.230,00" in html
    assert "Obra &lt;Central&gt;" in html
    assert "Gastos &lt;obra&gt;" in html
    assert "2026-09-30" in html


def test_pdf_rechaza_certificado_inexistente():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE certificados_comitente(id INTEGER PRIMARY KEY, "
               "proyecto_id INTEGER, valorizacion_id INTEGER, numero INTEGER, "
               "fecha TEXT, estado TEXT, costo_directo TEXT, total TEXT, detalle_json TEXT)")
    db.execute("CREATE TABLE proyectos(id INTEGER PRIMARY KEY, nombre TEXT)")
    db.execute("CREATE TABLE valorizaciones(id INTEGER PRIMARY KEY, periodo_desde TEXT, "
               "periodo_hasta TEXT)")
    try:
        html_certificado_comitente(db, 900)
    except ValueError:
        pass
    else:
        assert False
