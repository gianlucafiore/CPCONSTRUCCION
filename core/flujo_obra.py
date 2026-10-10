# SPDX-License-Identifier: GPL-3.0-or-later
"""Indicadores no destructivos del circuito de obra.

'Con datos' no equivale a aprobado/completo; solo indica registros disponibles.
"""
from core.database import get_db


ETAPAS = {
    "presupuesto": ("partidas", "proyecto_id"),
    "contratos": ("contratos_subcontrato", "proyecto_id"),
    "planificacion": ("cronograma_partidas", None),
    "ejecucion": ("valorizaciones", "proyecto_id"),
    "certificacion": ("certificados_comitente", "proyecto_id"),
}


def estado_etapas(proyecto_id):
    db = get_db()
    try:
        disponibles = {
            row[0] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        respuesta = {}
        for clave, (tabla, columna) in ETAPAS.items():
            if tabla not in disponibles:
                respuesta[clave] = "Sin registros"
                continue
            if columna:
                cantidad = db.execute(
                    f"SELECT COUNT(*) FROM {tabla} WHERE {columna}=?",
                    (proyecto_id,)
                ).fetchone()[0]
            else:
                cantidad = db.execute(
                    "SELECT COUNT(*) FROM cronograma_partidas cp "
                    "JOIN partidas p ON p.id=cp.partida_id WHERE p.proyecto_id=?",
                    (proyecto_id,)
                ).fetchone()[0] if "partidas" in disponibles else 0
            respuesta[clave] = "Con datos" if cantidad else "Sin registros"
        respuesta["ajustes"] = "Disponible"
        return respuesta
    finally:
        db.close()
