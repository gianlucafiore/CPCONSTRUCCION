# SPDX-License-Identifier: GPL-3.0-or-later
"""Determinación de precio aplicada al avance certificado de una obra."""
from decimal import Decimal
from core.pie import calcular_pie
from core.valorizacion import get_valorizacion_detalle, get_valorizacion


def resumen_comitente(conn, valorizacion_id):
    v = get_valorizacion(valorizacion_id)
    if not v:
        raise ValueError("El período no existe")
    _filas, resumen = get_valorizacion_detalle(valorizacion_id)
    base = Decimal(str(resumen["act_val"]))
    lineas, total = calcular_pie(conn, v["proyecto_id"], float(base))
    if lineas is None:
        raise ValueError("Configurá la Determinación de Precio del proyecto")
    return {"costo_directo": base, "adicionales": [
                (linea["nombre"], Decimal(str(linea["valor"])))
                for linea in lineas if linea["tipo"] != "subtotal"],
            "total": Decimal(str(total)), "periodo": v["periodo_hasta"]}
