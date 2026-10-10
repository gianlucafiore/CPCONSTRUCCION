# SPDX-License-Identifier: GPL-3.0-or-later
"""Gestor de índices en grilla editable, sin formularios permanentes."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QInputDialog, QMessageBox, QHeaderView, QComboBox,
    QFileDialog, QAbstractItemView,
)
from core.database import get_db
from core.indices_genericos import guardar_valor, importar_csv, calcular_factor


class IndicesGenericosView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("vista_nombre", "indices_genericos")
        self._loading = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)
        title = QHBoxLayout()
        title.addWidget(QLabel("Índices económicos  ·  Series mensuales"))
        self.serie = QComboBox()
        self.serie.setMinimumWidth(250)
        self.serie.currentIndexChanged.connect(self.cargar_tabla)
        title.addWidget(self.serie, 1)
        lay.addLayout(title)
        bar = QHBoxLayout()
        for label, handler in (
            ("+ Fuente", self.nueva_fuente),
            ("+ Serie", self.nueva_serie),
            ("+ Mes", self.nuevo_mes),
            ("Importar CSV", self.importar_archivo),
            ("Fórmulas", self.abrir_formulas),
            ("Actualizar", self.cargar),
        ):
            b = QPushButton(label)
            b.clicked.connect(handler)
            bar.addWidget(b)
        bar.addStretch()
        lay.addLayout(bar)
        self.info = QLabel("Seleccioná una serie. Doble clic para editar valores; Enter confirma.")
        lay.addWidget(self.info)
        self.tabla = QTableWidget(0, 2)
        self.tabla.setHorizontalHeaderLabels(["Período (AAAA-MM)", "Valor del índice"])
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.tabla.setEditTriggers(QAbstractItemView.DoubleClicked |
                                   QAbstractItemView.EditKeyPressed |
                                   QAbstractItemView.AnyKeyPressed)
        self.tabla.itemChanged.connect(self._celda_modificada)
        lay.addWidget(self.tabla, 1)
        lay.addWidget(QLabel(
            "Los valores cargados deben corresponder a publicaciones verificadas. "
            "Las fórmulas no sustituyen las condiciones del contrato."
        ))
        self.cargar()

    def cargar(self):
        anterior = self.serie.currentData()
        db = get_db()
        try:
            rows = db.execute(
                "SELECT s.id, f.nombre, s.nombre, f.pais FROM series_indices s "
                "JOIN fuentes_indices f ON f.id=s.fuente_id "
                "ORDER BY f.nombre,s.nombre"
            ).fetchall()
        finally:
            db.close()
        self.serie.blockSignals(True)
        self.serie.clear()
        for sid, fuente, nombre, pais in rows:
            self.serie.addItem(f"{fuente} / {nombre} ({pais})", sid)
        ix = self.serie.findData(anterior)
        if ix >= 0:
            self.serie.setCurrentIndex(ix)
        self.serie.blockSignals(False)
        self.cargar_tabla()

    def cargar_tabla(self):
        sid = self.serie.currentData()
        self._loading = True
        self.tabla.setRowCount(0)
        if sid is not None:
            db = get_db()
            try:
                rows = db.execute(
                    "SELECT periodo,valor FROM valores_indices WHERE serie_id=? "
                    "ORDER BY periodo DESC", (sid,)
                ).fetchall()
            finally:
                db.close()
            self.tabla.setRowCount(len(rows))
            for row, (periodo, valor) in enumerate(rows):
                a = QTableWidgetItem(periodo)
                a.setFlags(a.flags() & ~Qt.ItemIsEditable)
                self.tabla.setItem(row, 0, a)
                self.tabla.setItem(row, 1, QTableWidgetItem(str(valor)))
        self._loading = False
        self.info.setText(
            f"{self.serie.currentText()}  ·  {self.tabla.rowCount()} períodos  ·  "
            "Doble clic en el valor para editar"
        )

    def _celda_modificada(self, item):
        if self._loading or item.column() != 1:
            return
        sid = self.serie.currentData()
        periodo_item = self.tabla.item(item.row(), 0)
        if sid is None or periodo_item is None:
            return
        db = get_db()
        try:
            guardar_valor(db, sid, periodo_item.text(), item.text().replace(",", "."))
            db.commit()
        except Exception as exc:
            db.rollback()
            QMessageBox.warning(self, "Valor no guardado", str(exc))
        finally:
            db.close()
        self.cargar_tabla()

    def _pedir(self, titulo, etiqueta):
        valor, ok = QInputDialog.getText(self, titulo, etiqueta)
        return valor.strip() if ok else ""

    def nueva_fuente(self):
        nombre = self._pedir("Nueva fuente", "Organismo o fuente:")
        if not nombre:
            return
        pais = self._pedir("País", "Código del país (AR, UY, etc.):").upper()
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
        db = get_db()
        try:
            fuentes = db.execute(
                "SELECT id,nombre,pais FROM fuentes_indices ORDER BY nombre"
            ).fetchall()
        finally:
            db.close()
        if not fuentes:
            QMessageBox.information(self, "Fuentes", "Creá una fuente primero.")
            return
        etiquetas = [f"{n} ({p})" for _, n, p in fuentes]
        elegido, ok = QInputDialog.getItem(
            self, "Fuente", "Seleccionar fuente:", etiquetas, 0, False
        )
        if not ok:
            return
        nombre = self._pedir("Nueva serie", "Nombre de la serie:")
        if not nombre:
            return
        codigo = self._pedir("Código", "Código único dentro de la fuente:")
        if not codigo:
            return
        db = get_db()
        try:
            db.execute(
                "INSERT INTO series_indices(fuente_id,codigo,nombre) VALUES(?,?,?)",
                (fuentes[etiquetas.index(elegido)][0], codigo, nombre)
            )
            db.commit()
        except Exception as exc:
            db.rollback()
            QMessageBox.warning(self, "No se pudo crear", str(exc))
        finally:
            db.close()
        self.cargar()

    def nuevo_mes(self):
        sid = self.serie.currentData()
        if sid is None:
            QMessageBox.information(self, "Serie", "Primero creá o seleccioná una serie.")
            return
        periodo = self._pedir("Agregar período", "Mes AAAA-MM:")
        if not periodo:
            return
        valor = self._pedir("Valor mensual", "Valor del índice:")
        if not valor:
            return
        db = get_db()
        try:
            guardar_valor(db, sid, periodo, valor.replace(",", "."))
            db.commit()
        except Exception as exc:
            db.rollback()
            QMessageBox.warning(self, "Dato inválido", str(exc))
        finally:
            db.close()
        self.cargar_tabla()

    def importar_archivo(self):
        sid = self.serie.currentData()
        if sid is None:
            QMessageBox.information(self, "Serie", "Seleccioná una serie.")
            return
        ruta, _ = QFileDialog.getOpenFileName(self, "Importar histórico", "", "CSV (*.csv)")
        if not ruta:
            return
        db = get_db()
        try:
            n = importar_csv(db, sid, ruta)
            db.commit()
        except Exception as exc:
            db.rollback()
            QMessageBox.warning(self, "Error CSV", str(exc))
            return
        finally:
            db.close()
        self.cargar_tabla()
        QMessageBox.information(self, "Importación completa", f"{n} períodos importados.")

    def abrir_formulas(self):
        from views.formulas_indices_dialog import FormulasIndicesDialog
        dlg = FormulasIndicesDialog(self)
        dlg.exec()
