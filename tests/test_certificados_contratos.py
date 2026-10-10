from decimal import Decimal
import pytest
from core.certificados_contratos import certificado_subcontrato, determinacion_precio


def test_subcontrato_recupero_y_reparo():
    r = certificado_subcontrato(100000, 20, 50, 5000, 20, 5)
    assert r["bruto"] == Decimal("30000.00")
    assert r["recupero"] == Decimal("5000.00")
    assert r["fondo_reparo"] == Decimal("1500.00")
    assert r["neto"] == Decimal("23500.00")


def test_avance_invalido():
    with pytest.raises(ValueError):
        certificado_subcontrato(100, 60, 40)


def test_precio_compuesto():
    r = determinacion_precio(100000, [
        ("GG", "pct_cd", 10), ("Utilidad", "pct_sub", 5),
        ("IVA ilustrativo", "pct_sub", 21),
    ])
    assert r["total"] == Decimal("139755.00")
