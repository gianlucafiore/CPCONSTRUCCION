# SPDX-License-Identifier: GPL-3.0-or-later
"""Mapa de trabajo de un proyecto: etapas y accesos no obligatorios."""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QFrame, QScrollArea, QWidget)


PASOS = (
    ("01", "Presupuestación", "Partidas → cómputos métricos → análisis de costos → determinación del precio.", "presupuesto"),
    ("02", "Contratación", "Condiciones con el comitente, subcontratos, anticipos y retenciones.", "contratos"),
    ("03", "Planificación", "Rendimientos, cronograma y curva de inversión.", "planificacion"),
    ("04", "Ejecución", "Mediciones de avance y seguimiento de recursos y costos.", "ejecucion"),
    ("05", "Certificación", "Certificados del comitente y subcontratistas, con sus propios importes.", "certificacion"),
    ("06", "Actualización contractual", "Índices y fórmulas ponderadas según el contrato.", "ajustes"),
)


class FlujoObraDialog(QDialog):
    def __init__(self, acciones, estados=None, parent=None):
        super().__init__(parent)
        estados = estados or {}
        self.setWindowTitle("Proceso de obra · CPconstruccion")
        self.resize(665, 490)
        root = QVBoxLayout(self)
        titulo = QLabel("Seguimiento del proyecto")
        titulo.setStyleSheet("font-size:16px;font-weight:600;")
        root.addWidget(titulo)
        nota = QLabel(
            "Elegí una etapa para continuar. Son accesos directos, no pasos obligatorios. "
            "Cada instancia debe utilizar los datos del presupuesto y del contrato."
        )
        nota.setWordWrap(True)
        root.addWidget(nota)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        cuerpo = QWidget()
        lay = QVBoxLayout(cuerpo)
        lay.setSpacing(5)
        for numero, titulo, descripcion, clave in PASOS:
            fila = QFrame()
            fila.setStyleSheet(
                "QFrame {background:#F8F9FA;border:1px solid #E3E6E9;border-radius:5px;}"
            )
            horizontal = QHBoxLayout(fila)
            horizontal.setContentsMargins(10, 7, 10, 7)
            etiqueta = QLabel(f"<b>{numero} · {titulo}</b>  ·  {estados.get(clave, 'Sin verificar')}<br>{descripcion}")
            etiqueta.setWordWrap(True)
            etiqueta.setStyleSheet("border:none;")
            horizontal.addWidget(etiqueta, 1)
            btn = QPushButton("Abrir →")
            btn.setFixedWidth(82)
            fn = acciones.get(clave)
            btn.setEnabled(fn is not None)
            if fn:
                btn.clicked.connect(lambda checked=False, accion=fn: (self.accept(), accion()))
            horizontal.addWidget(btn)
            lay.addWidget(fila)
        lay.addStretch()
        scroll.setWidget(cuerpo)
        root.addWidget(scroll, 1)
