# SPDX-License-Identifier: GPL-3.0-or-later
"""Fórmulas contractuales ponderadas en una grilla compacta."""
from __future__ import annotations
from decimal import Decimal
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QTableWidget, QTableWidgetItem, QInputDialog,
    QMessageBox, QHeaderView)
from core.database import get_db
from core.indices_genericos import calcular_factor


class FormulasIndicesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Fórmulas de actualización contractual")
        self.resize(760, 540)
        self._loading = False
        v = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.proyectos = QComboBox()
        self.formulas = QComboBox()
        self.metodo = QComboBox()
        self.metodo.addItem("Promedio ponderado", "ponderado")
        self.metodo.addItem("Promedio simple", "simple")
        for x in (self.proyectos, self.formulas, self.metodo):
            bar.addWidget(x)
        v.addLayout(bar)
        tools = QHBoxLayout()
        for label, callback in (("+ Fórmula", self.nueva),
                                ("+ Índice", self.agregar),
                                ("Quitar índice", self.quitar),
                                ("Calcular", self.calcular)):
            b = QPushButton(label)
            b.clicked.connect(callback)
            tools.addWidget(b)
        tools.addStretch()
        v.addLayout(tools)
        self.base = QLabel("Período base: —")
        v.addWidget(self.base)
        self.tabla = QTableWidget(0, 4)
        self.tabla.setHorizontalHeaderLabels(["ID serie", "Fuente / Serie", "Peso (%)", "Código"])
        self.tabla.setColumnHidden(0, True)
        self.tabla.setColumnHidden(3, True)
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tabla.itemChanged.connect(self.guardar_peso)
        v.addWidget(self.tabla)
        self.periodo = QLabel("El período final se solicita al calcular.")
        v.addWidget(self.periodo)
        self.proyectos.currentIndexChanged.connect(self.cargar_formulas)
        self.formulas.currentIndexChanged.connect(self.cargar_componentes)
        self.metodo.currentIndexChanged.connect(self.guardar_metodo)
        self.cargar_proyectos()

    def cargar_proyectos(self):
        db = get_db()
        try:
            rows = db.execute("SELECT id,nombre FROM proyectos ORDER BY nombre").fetchall()
        finally:
            db.close()
        self.proyectos.blockSignals(True)
        self.proyectos.clear()
        for pid, nombre in rows:
            self.proyectos.addItem(nombre, pid)
        self.proyectos.blockSignals(False)
        self.cargar_formulas()

    def cargar_formulas(self):
        pid = self.proyectos.currentData()
        db = get_db()
        try:
            rows = db.execute(
                "SELECT id,nombre FROM formulas_actualizacion WHERE proyecto_id=? "
                "ORDER BY id", (pid,)
            ).fetchall() if pid is not None else []
        finally:
            db.close()
        self.formulas.blockSignals(True)
        self.formulas.clear()
        for fid, nombre in rows:
            self.formulas.addItem(nombre, fid)
        self.formulas.blockSignals(False)
        self.cargar_componentes()

    def cargar_componentes(self):
        fid = self.formulas.currentData()
        self._loading = True
        self.tabla.setRowCount(0)
        db = get_db()
        try:
            if fid is None:
                self.base.setText("Período base: —")
                return
            f = db.execute("SELECT periodo_base,metodo FROM formulas_actualizacion WHERE id=?",
                           (fid,)).fetchone()
            self.base.setText("Período base: " + f[0])
            self.metodo.blockSignals(True)
            self.metodo.setCurrentIndex(max(0, self.metodo.findData(f[1])))
            self.metodo.blockSignals(False)
            rows = db.execute(
                "SELECT s.id, f.nombre || ' / ' || s.nombre, fi.peso,s.codigo "
                "FROM formula_indices fi JOIN series_indices s ON s.id=fi.serie_id "
                "JOIN fuentes_indices f ON f.id=s.fuente_id "
                "WHERE fi.formula_id=? ORDER BY s.id", (fid,)
            ).fetchall()
            self.tabla.setRowCount(len(rows))
            for i, row in enumerate(rows):
                for j, value in enumerate(row):
                    it = QTableWidgetItem(str(value))
                    if j != 2:
                        from PySide6.QtCore import Qt
                        it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                    self.tabla.setItem(i, j, it)
        finally:
            db.close()
            self._loading = False

    def nueva(self):
        pid = self.proyectos.currentData()
        if pid is None:
            QMessageBox.information(self, "Proyecto", "Primero creá un proyecto.")
            return
        nombre, ok = QInputDialog.getText(self, "Nueva fórmula", "Nombre:")
        if not ok or not nombre.strip():
            return
        base, ok = QInputDialog.getText(self, "Período base", "AAAA-MM:")
        if not ok:
            return
        import re
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", base):
            QMessageBox.warning(self, "Período", "Ingresá AAAA-MM.")
            return
        db = get_db()
        try:
            db.execute(
                "INSERT INTO formulas_actualizacion(proyecto_id,nombre,periodo_base) "
                "VALUES(?,?,?)", (pid, nombre.strip(), base)
            )
            db.commit()
        finally:
            db.close()
        self.cargar_formulas()

    def agregar(self):
        fid = self.formulas.currentData()
        if fid is None:
            return
        db = get_db()
        try:
            rows = db.execute(
                "SELECT s.id,f.nombre || ' / ' || s.nombre FROM series_indices s "
                "JOIN fuentes_indices f ON f.id=s.fuente_id ORDER BY 2"
            ).fetchall()
        finally:
            db.close()
        if not rows:
            QMessageBox.information(self, "Índices", "Creá una serie primero.")
            return
        labels = [r[1] for r in rows]
        label, ok = QInputDialog.getItem(self, "Agregar índice", "Serie:", labels, 0, False)
        if not ok:
            return
        peso, ok = QInputDialog.getDouble(self, "Ponderación", "Peso relativo (%):",
                                           100.0, 0.01, 100000, 2)
        if not ok:
            return
        db = get_db()
        try:
            db.execute(
                "INSERT INTO formula_indices(formula_id,serie_id,peso) VALUES(?,?,?) "
                "ON CONFLICT(formula_id,serie_id) DO UPDATE SET peso=excluded.peso",
                (fid, rows[labels.index(label)][0], str(peso))
            )
            db.commit()
        finally:
            db.close()
        self.cargar_componentes()

    def quitar(self):
        fid = self.formulas.currentData()
        fila = self.tabla.currentRow()
        if fid is None or fila < 0:
            return
        sid = int(self.tabla.item(fila, 0).text())
        db = get_db()
        try:
            db.execute("DELETE FROM formula_indices WHERE formula_id=? AND serie_id=?",
                       (fid, sid))
            db.commit()
        finally:
            db.close()
        self.cargar_componentes()

    def guardar_peso(self, item):
        if self._loading or item.column() != 2:
            return
        fid = self.formulas.currentData()
        sid = int(self.tabla.item(item.row(), 0).text())
        try:
            valor = Decimal(item.text().replace(",", "."))
            if not valor.is_finite() or valor <= 0:
                raise ValueError("La ponderación debe ser positiva.")
            db = get_db()
            try:
                db.execute("UPDATE formula_indices SET peso=? "
                           "WHERE formula_id=? AND serie_id=?", (str(valor), fid, sid))
                db.commit()
            finally:
                db.close()
        except Exception as e:
            QMessageBox.warning(self, "Peso", str(e))
        self.cargar_componentes()

    def guardar_metodo(self):
        fid = self.formulas.currentData()
        if fid is None:
            return
        db = get_db()
        try:
            db.execute("UPDATE formulas_actualizacion SET metodo=? WHERE id=?",
                       (self.metodo.currentData(), fid))
            db.commit()
        finally:
            db.close()

    def calcular(self):
        fid = self.formulas.currentData()
        if fid is None:
            return
        fecha, ok = QInputDialog.getText(self, "Período final", "AAAA-MM:")
        if not ok:
            return
        db = get_db()
        try:
            r = calcular_factor(db, fid, fecha.strip())
        except Exception as e:
            QMessageBox.warning(self, "No se puede calcular", str(e))
            return
        finally:
            db.close()
        QMessageBox.information(
            self, "Actualización calculada",
            f"Período base: {r['periodo_base']}\nPeríodo final: {r['periodo_final']}\n"
            f"Variación: {r['variacion_pct']:.3f}%\nFactor: {r['factor']:.8f}"
        )
