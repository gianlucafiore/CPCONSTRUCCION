# SPDX-License-Identifier: GPL-3.0-or-later
"""Cálculos contractuales para certificaciones."""
from decimal import Decimal, ROUND_HALF_UP


def dinero(value):
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def certificado_subcontrato(contrato, previo, acumulado, anticipo_pendiente=0,
                           recupero_pct=0, reparo_pct=0):
    contrato = dinero(contrato)
    previo, acumulado = Decimal(str(previo)), Decimal(str(acumulado))
    recupero_pct, reparo_pct = Decimal(str(recupero_pct)), Decimal(str(reparo_pct))
    if not (contrato >= 0 and 0 <= previo <= acumulado <= 100):
        raise ValueError("Contrato o avance inválido")
    if not (0 <= recupero_pct <= 100 and 0 <= reparo_pct <= 100):
        raise ValueError("Retenciones inválidas")
    saldo = dinero(anticipo_pendiente)
    if saldo < 0:
        raise ValueError("Saldo de anticipo inválido")
    bruto = dinero(contrato * (acumulado - previo) / 100)
    recupero = min(saldo, dinero(bruto * recupero_pct / 100))
    reparo = dinero(bruto * reparo_pct / 100)
    return {"bruto": bruto, "recupero": recupero,
            "fondo_reparo": reparo, "neto": dinero(bruto - recupero - reparo),
            "saldo_anticipo": dinero(saldo - recupero)}


def determinacion_precio(costo_directo, conceptos):
    """Aplica importes contractuales y porcentajes sobre CD o subtotal."""
    cd = dinero(costo_directo)
    if cd < 0:
        raise ValueError("Costo directo negativo")
    subtotal = cd
    desglose = []
    for nombre, tipo, valor in conceptos:
        p = Decimal(str(valor))
        if not p.is_finite() or p < 0:
            raise ValueError("Concepto inválido")
        if tipo == "pct_cd":
            importe = dinero(cd * p / 100)
        elif tipo == "pct_sub":
            importe = dinero(subtotal * p / 100)
        elif tipo == "importe":
            importe = dinero(p)
        else:
            raise ValueError("Tipo de concepto inválido")
        subtotal += importe
        desglose.append((nombre, importe))
    return {"costo_directo": cd, "conceptos": desglose, "total": dinero(subtotal)}
