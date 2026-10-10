from core.certificaciones_ar import (
    certificado_subcontrato, determinacion_precio_certificado,
)


def test_subcontrato_recupera_anticipo():
    r = certificado_subcontrato(
        100000, 20, 50, anticipo_otorgado=20000,
        recupero_anticipo_pct=20, retencion_pct=5,
    )
    assert r['bruto_periodo'] == 30000
    assert r['recupero_anticipo'] == 6000
    assert r['retencion'] == 1500
    assert r['neto_a_liquidar'] == 22500


def test_subcontrato_sin_doble_certificar():
    r = certificado_subcontrato(100000, 50, 50)
    assert r['neto_a_liquidar'] == 0


def test_determinacion_precio_periodo():
    r = determinacion_precio_certificado(100000, [
        {'nombre': 'Gastos generales', 'tipo': 'pct_cd', 'porcentaje': 10},
        {'nombre': 'Beneficio', 'tipo': 'pct_cd', 'porcentaje': 5},
        {'nombre': 'Subtotal', 'tipo': 'subtotal'},
        {'nombre': 'IVA', 'tipo': 'pct_sub', 'porcentaje': 21},
    ])
    assert r['precio_periodo'] == 139150


def test_avance_regresivo_prohibido():
    try:
        certificado_subcontrato(100000, 60, 40)
    except ValueError:
        return
    assert False, "Debe rechazar un avance acumulado inferior al anterior"
