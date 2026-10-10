# SPDX-License-Identifier: GPL-3.0-or-later
"""Cálculos independientes para certificados de obra de CPconstruccion.

Los importes y porcentajes son contractuales. Este módulo no determina
automáticamente normas, retenciones ni alícuotas aplicables.
"""
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP


def _dinero(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _numero(value) -> Decimal:
    return Decimal(str(value))


def certificado_subcontrato(
    monto_contrato, avance_anterior_pct, avance_acumulado_pct, *,
    anticipo_otorgado=0, recupero_anticipo_pct=0, retencion_pct=0,
    otros_descuentos=0, adicionales_periodo=0
) -> dict:
    """Calcula un período por avance acumulado, sin registrar un pago.

    recupero_anticipo_pct se aplica al bruto del período. El anticipo
    efectivamente recuperado queda limitado al saldo pendiente.
    """
    contrato = _dinero(monto_contrato)
    anterior = _numero(avance_anterior_pct)
    actual = _numero(avance_acumulado_pct)
    if contrato < 0 or not (0 <= anterior <= actual <= 100):
        raise ValueError("Avances inválidos o monto de contrato negativo")
    if not (0 <= _numero(recupero_anticipo_pct) <= 100):
        raise ValueError("Porcentaje de recupero inválido")
    if not (0 <= _numero(retencion_pct) <= 100):
        raise ValueError("Porcentaje de retención inválido")
    extras = _dinero(adicionales_periodo)
    otros = _dinero(otros_descuentos)
    anticipo = _dinero(anticipo_otorgado)
    if min(extras, otros, anticipo) < 0:
        raise ValueError("Los importes adicionales y descuentos no pueden ser negativos")
    acumulado_anterior = _dinero(contrato * anterior / 100)
    acumulado_actual = _dinero(contrato * actual / 100)
    bruto = acumulado_actual - acumulado_anterior + extras
    recupero_previo = _dinero(acumulado_anterior * _numero(recupero_anticipo_pct) / 100)
    saldo_anticipo = max(Decimal("0"), anticipo - recupero_previo)
    recupero = min(saldo_anticipo, _dinero(bruto * _numero(recupero_anticipo_pct) / 100))
    retencion = _dinero(bruto * _numero(retencion_pct) / 100)
    neto = _dinero(bruto - recupero - retencion - otros)
    return {
        'avance_periodo_pct': float(actual - anterior),
        'avance_acumulado_pct': float(actual),
        'bruto_periodo': float(bruto),
        'recupero_anticipo': float(recupero),
        'retencion': float(retencion),
        'otros_descuentos': float(otros),
        'neto_a_liquidar': float(neto),
        'saldo_anticipo_estimado': float(saldo_anticipo - recupero),
    }


def determinacion_precio_certificado(costo_directo_periodo, rubros: list[dict]) -> dict:
    """Determina precio del período a partir de un costo directo certificado.

    Recibe rubros ordenados con {nombre, tipo, porcentaje|importe}.
    Tipos: pct_cd (sobre costo directo), pct_sub (sobre subtotal corriente),
    fijo (importe del período), subtotal (cambio de base). Cada concepto
    debe provenir del contrato; no se presume automáticamente IVA.
    """
    cd = _dinero(costo_directo_periodo)
    if cd < 0:
        raise ValueError("Costo directo negativo")
    total = cd
    base_sub = cd
    items = []
    for rubro in rubros:
        tipo = rubro['tipo']
        if tipo == 'subtotal':
            base_sub = total
            continue
        if tipo == 'pct_cd':
            valor = _dinero(cd * _numero(rubro['porcentaje']) / 100)
        elif tipo == 'pct_sub':
            valor = _dinero(base_sub * _numero(rubro['porcentaje']) / 100)
        elif tipo == 'fijo':
            valor = _dinero(rubro['importe'])
        else:
            raise ValueError(f"Tipo de rubro no admitido: {tipo}")
        total += valor
        items.append({'nombre': rubro['nombre'], 'importe': float(valor)})
    return {'costo_directo': float(cd), 'rubros': items, 'precio_periodo': float(_dinero(total))}
