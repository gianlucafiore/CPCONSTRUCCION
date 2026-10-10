# SPDX-License-Identifier: GPL-3.0-or-later
"""Catálogo universal de índices: carga manual auditada de series y períodos."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QInputDialog, QMessageBox, QHeaderView, QAbstractItemView,
)
from core.database import get_db
from core.indices_genericos import inicializar, guardar_valor


class IndicesGenericosView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("vista_nombre", "indices_genericos")
        self._serie_id = None
        root = QVBoxLayout(self)
        root.addWidget(QLabel("Índices y actualización de costos"))
        root.addWidget(QLabel(
            "Series configurables. Los índices se cargan manualmente; "
            "ninguna fuente se considera oficial sin verificar sus publicaciones."
        ))
        actions = QHBoxLayout()
        for name, callback in (
            ("Nueva fuente", self.nueva_fuente),
            ("Nueva serie", self.nueva_serie),
            ("Agregar valor mensual", self.nuevo_valor),
            ("Actualizar vista", self.cargar),
        ):
            btn = QPushButton(name)
            btn.clicked.connect(callback)
            actions.addWidget(btn)
        actions.addStretch()
        root.addLayout(actions)
        self.fuentes = QTableWidget(0, 3)
        self.fuentes.setHorizontalHeaderLabels(["ID", "País", "Fuente"])
        self.fuentes.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.fuentes.setSelectionMode(QAbstractItemView.SingleSelection)
        self.fuentes.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.series = QTableWidget(0, 3)
        self.series.setHorizontalHeaderLabels(["ID", "Fuente", "Serie"])
        self.series.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.series.setSelectionMode(QAbstractItemView.SingleSelection)
        self.series.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.series.itemSelectionChanged.connect(self.cargar_valores)
        self.valores = QTableWidget(0, 2)
        self.valores.setHorizontalHeaderLabels(["Período", "Valor"])
        root.addWidget(QLabel("Fuentes"))
        root.addWidget(self.fuentes)
        root.addWidget(QLabel("Series"))
        root.addWidget(self.series)
        root.addWidget(QLabel("Histórico mensual de la serie seleccionada"))
        root.addWidget(self.valores)
        self.cargar()

    def _texto(self, titulo, etiqueta):
        text, ok = QInputDialog.getText(self, titulo, etiqueta)
        return text.strip() if ok else ""

    def _seleccion(self, tabla):
        rows = tabla.selectionModel().selectedRows()
        if not rows:
            return None
        item = tabla.item(rows[0].row(), 0)
        return int(item.text()) if item else None

    def cargar(self):
        db = get_db()
        try:
            inicializar(db)
            fuentes = db.execute(
                "SELECT id,pais,nombre FROM fuentes_indices ORDER BY nombre"
            ).fetchall()
            series = db.execute(
                "SELECT s.id,f.nombre,s.nombre FROM series_indices s "
                "JOIN fuentes_indices f ON f.id=s.fuente_id "
                "ORDER BY f.nombre,s.nombre"
            ).fetchall()
        finally:
            db.close()
        for table, rows in ((self.fuentes, fuentes), (self.series, series)):
            table.setRowCount(len(rows))
            for i, row in enumerate(rows):
                for j, value in enumerate(row):
                    table.setItem(i, j, QTableWidgetItem(str(value)))
        self.cargar_valores()

    def cargar_valores(self):
        self._serie_id = self._seleccion(self.series)
        self.valores.setRowCount(0)
        if self._serie_id is None:
            return
        db = get_db()
        try:
            rows = db.execute(
                "SELECT periodo,valor FROM valores_indices "
                "WHERE serie_id=? ORDER BY periodo DESC", (self._serie_id,)
            ).fetchall()
        finally:
            db.close()
        self.valores.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, value in enumerate(row):
                self.valores.setItem(i, j, QTableWidgetItem(str(value)))

    def nueva_fuente(self):
        nombre = self._texto("Nueva fuente", "Nombre (ej.: CAC, INDEC):")
        if not nombre:
            return
        pais = self._texto("País", "Código de país (ej.: AR):").upper()
        if not pais:
            return
        db = get_db()
        try:
            db.execute("INSERT INTO fuentes_indices(nombre,pais) VALUES(?,?)",
                       (nombre, pais))
            db.commit()
        finally:
            db.close()
        self.cargar()

    def nueva_serie(self):
        fid = self._seleccion(self.fuentes)
        if fid is None:
            QMessageBox.information(self, "Fuente", "Seleccioná una fuente primero.")
            return
        nombre = self._texto("Nueva serie", "Nombre de la serie:")
        codigo = self._texto("Código", "Código identificador de la serie:")
        if not nombre or not codigo:
            return
        db = get_db()
        try:
            db.execute(
                "INSERT INTO series_indices(fuente_id,codigo,nombre) VALUES(?,?,?)",
                (fid, codigo, nombre))
            db.commit()
        except Exception as e:
            db.rollback()
            QMessageBox.warning(self, "No se pudo guardar", str(e))
        finally:
            db.close()
        self.cargar()

    def nuevo_valor(self):
        sid = self._seleccion(self.series)
        if sid is None:
            QMessageBox.information(self, "Serie", "Seleccioná una serie primero.")
            return
        periodo = self._texto("Período", "Período AAAA-MM:")
        valor = self._texto("Valor", "Valor publicado del índice:")
        if not periodo or not valor:
            return
        db = get_db()
        try:
            guardar_valor(db, sid, periodo, valor.replace(",", "."))
            db.commit()
        except Exception as e:
            db.rollback()
            QMessageBox.warning(self, "Valor inválido", str(e))
        finally:
            db.close()
        self.cargar()
