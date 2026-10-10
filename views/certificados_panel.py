# SPDX-License-Identifier: GPL-3.0-or-later
"""Vista preliminar de liquidaciones contractuales, sin emitir facturas."""
from __future__ import annotations
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QComboBox)
from core.certificados_contratos import certificado_subcontrato
from core.database import get_db
from core.valorizacion import get_valorizacion_detalle


class CertificadosPanel(QWidget):
    """Calculadora de liquidación: avances persistidos solo en valorizaciones."""
    def __init__(self, pid, parent=None):
        super().__init__(parent)
        self.pid = pid
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        top = QHBoxLayout()
        top.addWidget(QLabel("Certificación al comitente"))
        self.periodos = QComboBox()
        top.addWidget(self.periodos, 1)
        b = QPushButton("Ver avance")
        b.clicked.connect(self.ver_avance)
        top.addWidget(b)
        lay.addLayout(top)
        lay.addWidget(QLabel(
            "Mediciones de la valorización del período. Los importes "
            "son costo directo: la Determinación de Precio debe incorporarse "
            "antes de emitir un certificado de cobro."
        ))
        self.tabla = QTableWidget(0, 5)
        self.tabla.setHorizontalHeaderLabels(
            ["Ítem", "Partida", "Avance anterior", "Este período", "Acumulado"]
        )
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        lay.addWidget(self.tabla, 1)
        lay.addWidget(QLabel("Simulador de certificado de subcontrato (sin guardar)"))
        self.subtabla = QTableWidget(1, 6)
        self.subtabla.setHorizontalHeaderLabels(
            ["Contrato $", "Anterior %", "Acumulado %", "Anticipo pendiente $",
             "Recupero %", "Reparo %"]
        )
        for col, value in enumerate(("1000000", "0", "0", "0", "0", "0")):
            self.subtabla.setItem(0, col, QTableWidgetItem(value))
        lay.addWidget(self.subtabla)
        actions = QHBoxLayout()
        btn = QPushButton("Calcular liquidación")
        btn.clicked.connect(self.liquidar)
        actions.addWidget(btn)
        self.resultado = QLabel("Resultado sin calcular")
        actions.addWidget(self.resultado, 1)
        lay.addLayout(actions)
        self.cargar()

    def cargar(self):
        db = get_db()
        try:
            rows = db.execute(
                "SELECT id, numero, periodo_desde, periodo_hasta "
                "FROM valorizaciones WHERE proyecto_id=? ORDER BY numero DESC",
                (self.pid,)
            ).fetchall()
        finally:
            db.close()
        current = self.periodos.currentData()
        self.periodos.clear()
        for id_, num, desde, hasta in rows:
            self.periodos.addItem(f"#{num}  {desde} – {hasta}", id_)
        ix = self.periodos.findData(current)
        if ix >= 0:
            self.periodos.setCurrentIndex(ix)
        self.ver_avance()

    def ver_avance(self):
        val_id = self.periodos.currentData()
        self.tabla.setRowCount(0)
        if val_id is None:
            return
        filas, _ = get_valorizacion_detalle(val_id)
        self.tabla.setRowCount(len(filas))
        for i, fila in enumerate(filas):
            values = (
                fila.get("item", ""),
                fila.get("descripcion", ""),
                fila.get("ant_val", 0),
                fila.get("act_val", 0),
                fila.get("acu_val", 0),
            )
            for j, value in enumerate(values):
                it = QTableWidgetItem(str(value if value is not None else ""))
                it.setFlags(it.flags() & ~__import__('PySide6.QtCore', fromlist=['Qt']).Qt.ItemIsEditable)
                self.tabla.setItem(i, j, it)

    def liquidar(self):
        try:
            values = [self.subtabla.item(0, i).text().replace(",", ".")
                      for i in range(6)]
            r = certificado_subcontrato(*values)
            self.resultado.setText(
                f"Bruto: $ {r['bruto']:,.2f}  ·  Recupero: $ {r['recupero']:,.2f}"
                f"  ·  Reparo: $ {r['fondo_reparo']:,.2f}  ·  Neto: $ {r['neto']:,.2f}"
            )
        except Exception as exc:
            QMessageBox.warning(self, "Liquidación inválida", str(exc))
