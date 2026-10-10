# SPDX-License-Identifier: GPL-3.0-or-later
"""Formato imprimible de certificados guardados al comitente.

Siempre usa los importes históricos registrados, nunca recalcula el presupuesto.
"""
from decimal import Decimal
from html import escape
import json


def _importe(valor):
    numero = Decimal(str(valor))
    if not numero.is_finite():
        raise ValueError("Importe inválido del certificado")
    return f"{numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def html_certificado_comitente(conn, certificado_id: int) -> str:
    fila = conn.execute(
        """SELECT c.numero, c.fecha, c.estado, c.costo_directo, c.total,
                  c.detalle_json, p.nombre, v.periodo_desde, v.periodo_hasta
           FROM certificados_comitente c
           JOIN proyectos p ON p.id=c.proyecto_id
           JOIN valorizaciones v ON v.id=c.valorizacion_id
           WHERE c.id=?""", (certificado_id,)
    ).fetchone()
    if fila is None:
        raise ValueError("Certificado inexistente")
    numero, fecha, estado, cd, total, detalle, proyecto, desde, hasta = fila
    conceptos = json.loads(detalle)
    if not isinstance(conceptos, list):
        raise ValueError("Detalle del certificado inválido")
    filas = [
        "<tr><td>Costo directo ejecutado</td><td align='right'>$ "
        + _importe(cd) + "</td></tr>"
    ]
    for concepto in conceptos:
        nombre = escape(str(concepto["nombre"]))
        importe = _importe(concepto["importe"])
        filas.append(
            "<tr><td>" + nombre + "</td><td align='right'>$ "
            + importe + "</td></tr>"
        )
    filas.append(
        "<tr><th align='left'>Total del certificado</th>"
        "<th align='right'>$ " + _importe(total) + "</th></tr>"
    )
    return (
        "<html><head><meta charset='utf-8'></head>"
        "<body style='font-family:sans-serif;font-size:10pt;'>"
        "<h2>Certificado de obra al comitente</h2>"
        "<p>Documento contractual. No constituye factura ni recibo de cobro.</p>"
        "<p><b>Obra:</b> " + escape(str(proyecto)) + "</p>"
        "<p><b>Certificado N.º:</b> " + escape(str(numero))
        + " &nbsp; <b>Fecha:</b> " + escape(str(fecha))
        + " &nbsp; <b>Estado:</b> " + escape(str(estado)).upper() + "</p>"
        "<p><b>Período medido:</b> " + escape(str(desde or '—'))
        + " a " + escape(str(hasta or '—')) + "</p>"
        "<table width='100%' cellpadding='7' cellspacing='0'"
        " style='border-collapse:collapse;'>"
        + "".join(filas) + "</table>"
        "<p>Los importes corresponden a la Determinación de precio registrada"
        " al crear el certificado. No implican conformidad ni pago automático.</p>"
        "<br><p>Firma comitente: _____________________________</p>"
        "<p>Firma contratista: ____________________________</p>"
        "</body></html>"
    )
