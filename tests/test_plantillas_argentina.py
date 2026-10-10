"""Comprobaciones básicas de las plantillas argentinas de CPconstruccion."""
from core.plantillas_pie import listar_plantillas_pie, obtener_plantilla_pie


def test_plantillas_sin_costos_extranjeros():
    plantillas = listar_plantillas_pie()
    assert plantillas
    for _clave, _nombre, items in plantillas:
        for item in items:
            assert item.get('precio', 0) == 0
            texto = item['descripcion'].lower()
            assert 'invirte.pe' not in texto
            assert 'sctr' not in texto
            assert 'carta fianza' not in texto


def test_plantillas_no_comparten_estado():
    items = obtener_plantilla_pie('gg')
    assert items
    items[0]['descripcion'] = 'modificado'
    assert obtener_plantilla_pie('gg')[0]['descripcion'] != 'modificado'
