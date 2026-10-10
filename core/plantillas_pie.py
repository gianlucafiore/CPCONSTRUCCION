# SPDX-License-Identifier: GPL-3.0-or-later
# Plantillas orientativas para presupuestos de construcción en Argentina.
# No incluyen precios ni cargas sociales prefijadas.
"""Plantillas iniciales de gastos generales para CPconstruccion.

Los conceptos son editables y todos los valores monetarios comienzan en cero.
No se incluyen porcentajes legales ni precios referenciales inventados.
"""
from __future__ import annotations


def _grupo(nombre: str) -> dict:
    return {'tipo': 'grupo', 'descripcion': nombre}


def _item(nombre: str, unidad: str = 'glb') -> dict:
    return {'tipo': 'item', 'descripcion': nombre, 'unidad': unidad,
            'n_personas': 1, 'tiempo': 1, 'pct_participacion': 100,
            'precio': 0}


_PLANTILLAS: list[tuple[str, str, list[dict]]] = [
    ('gg', 'Gastos generales de obra (Argentina)', [
        _grupo('GASTOS DE ORGANIZACIÓN Y ADMINISTRACIÓN'),
        _item('Administración y dirección técnica', 'mes'),
        _item('Oficina y servicios de obra', 'mes'),
        _item('Seguros y garantías', 'glb'),
        _item('Gestiones y permisos', 'glb'),
        _grupo('IMPLANTACIÓN Y LOGÍSTICA'),
        _item('Obrador e instalaciones provisorias', 'glb'),
        _item('Movilización y desmovilización', 'glb'),
        _item('Transporte y logística de obra', 'glb'),
        _grupo('SEGURIDAD Y CONTROL'),
        _item('Higiene y seguridad en obra', 'mes'),
        _item('Elementos de protección personal', 'glb'),
        _item('Ensayos y controles de calidad', 'glb'),
    ]),
    ('supervision', 'Inspección y supervisión', [
        _grupo('SUPERVISIÓN TÉCNICA'),
        _item('Inspección de obra', 'mes'),
        _item('Ensayos y verificaciones técnicas', 'glb'),
    ]),
    ('expediente', 'Documentación técnica', [
        _grupo('DOCUMENTACIÓN DE PROYECTO'),
        _item('Documentación ejecutiva', 'glb'),
        _item('Relevamiento y estudios previos', 'glb'),
        _item('Planos conforme a obra', 'glb'),
    ]),
    ('liquidacion', 'Cierre y liquidación', [
        _grupo('CIERRE DE OBRA'),
        _item('Medición y certificación final', 'glb'),
        _item('Documentación de cierre', 'glb'),
    ]),
]


def listar_plantillas_pie() -> list[tuple[str, str, list[dict]]]:
    """Devuelve copias independientes de las plantillas disponibles."""
    return [(k, n, [dict(it) for it in items]) for k, n, items in _PLANTILLAS]


def obtener_plantilla_pie(key: str) -> list[dict]:
    """Devuelve una copia editable, o lista vacía para una clave desconocida."""
    for k, _nombre, items in _PLANTILLAS:
        if k == key:
            return [dict(it) for it in items]
    return []
