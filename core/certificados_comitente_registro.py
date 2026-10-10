# SPDX-License-Identifier: GPL-3.0-or-later
"""Certificados al comitente: registros independientes de las mediciones.

Guardar un certificado no implica aprobación, facturación ni cobranza.
Los importes quedan congelados como fotografía del cálculo registrado.
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal
import json
from core.certificados_comitente import resumen_comitente


def inicializar(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS certificados_comitente (
        id INTEGER PRIMARY KEY,
        proyecto_id INTEGER NOT NULL REFERENCES proyectos(id),
        valorizacion_id INTEGER NOT NULL REFERENCES valorizaciones(id),
        numero INTEGER NOT NULL,
        fecha TEXT NOT NULL,
        estado TEXT NOT NULL DEFAULT 'borrador',
        costo_directo TEXT NOT NULL,
        total TEXT NOT NULL,
        detalle_json TEXT NOT NULL,
        UNIQUE(proyecto_id,numero),
        UNIQUE(valorizacion_id),
        CHECK(estado IN ('borrador','presentado','aprobado','observado'))
    )""")


def registrar_desde_medicion(conn, proyecto_id, valorizacion_id):
    inicializar(conn)
    v = conn.execute("SELECT proyecto_id FROM valorizaciones WHERE id=?",
                     (valorizacion_id,)).fetchone()
    if not v or v[0] != proyecto_id:
        raise ValueError("La medición no pertenece al proyecto")
    if conn.execute("SELECT 1 FROM certificados_comitente WHERE valorizacion_id=?",
                    (valorizacion_id,)).fetchone():
        raise ValueError("Ya existe un certificado para esa medición")
    resumen = resumen_comitente(conn, valorizacion_id)
    numero = conn.execute(
        "SELECT COALESCE(MAX(numero),0)+1 FROM certificados_comitente WHERE proyecto_id=?",
        (proyecto_id,)
    ).fetchone()[0]
    detalle = [
        {"nombre": nombre, "importe": str(importe)}
        for nombre, importe in resumen["adicionales"]
    ]
    row = conn.execute(
        "INSERT INTO certificados_comitente "
        "(proyecto_id,valorizacion_id,numero,fecha,costo_directo,total,detalle_json) "
        "VALUES(?,?,?,?,?,?,?)",
        (proyecto_id,valorizacion_id,numero,date.today().isoformat(),
         str(resumen["costo_directo"]),str(resumen["total"]),
         json.dumps(detalle,ensure_ascii=False))
    )
    return row.lastrowid


def cambiar_estado(conn, certificado_id, nuevo_estado):
    if nuevo_estado not in ("borrador","presentado","aprobado","observado"):
        raise ValueError("Estado desconocido")
    actual = conn.execute("SELECT estado FROM certificados_comitente WHERE id=?",
                          (certificado_id,)).fetchone()
    if not actual:
        raise ValueError("Certificado inexistente")
    if actual[0] == 'aprobado' and nuevo_estado != 'aprobado':
        raise ValueError("Un certificado aprobado no puede reabrirse")
    conn.execute("UPDATE certificados_comitente SET estado=? WHERE id=?",
                 (nuevo_estado, certificado_id))
