# SPDX-License-Identifier: GPL-3.0-or-later
"""Vista preliminar de liquidaciones contractuales, sin emitir facturas."""
from __future__ import annotations
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QComboBox, QInputDialog, QFileDialog)
from core.certificados_contratos import certificado_subcontrato
from core.database import get_db
from core.valorizacion import get_valorizacion_detalle
from core.contratos_obra import inicializar, crear_contrato, emitir_certificado
from core.certificados_comitente import resumen_comitente
from core.certificados_comitente_registro import inicializar as iniciar_comitente, registrar_desde_medicion, cambiar_estado


class CertificadosPanel(QWidget):
    """Calculadora de liquidación: avances persistidos solo en valorizaciones."""
    def __init__(self, pid, parent=None):
        super().__init__(parent)
        self.pid = pid
        from PySide6.QtWidgets import QTabWidget
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(4)
        root.addWidget(QLabel("Certificaciones de obra"))
        tabs = QTabWidget(self)
        root.addWidget(tabs, 1)

        cliente = QWidget()
        lay = QVBoxLayout(cliente)
        lay.setContentsMargins(8, 8, 8, 8)
        top = QHBoxLayout()
        top.addWidget(QLabel("Medición del período:"))
        self.periodos = QComboBox()
        top.addWidget(self.periodos, 1)
        btn = QPushButton("Actualizar")
        btn.clicked.connect(self.ver_avance)
        top.addWidget(btn)
        lay.addLayout(top)
        self.tabla = QTableWidget(0, 5)
        self.tabla.setHorizontalHeaderLabels(
            ["Ítem", "Partida", "Anterior ($)", "Período ($)", "Acumulado ($)"])
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        lay.addWidget(self.tabla, 3)
        acciones = QHBoxLayout()
        for nombre, callback in (
            ("Calcular precio", self.ver_precio_comitente),
            ("Registrar certificado", self.registrar_comitente),
            ("Exportar PDF", self.exportar_comitente),
            ("Cambiar estado", self.estado_comitente),
        ):
            boton = QPushButton(nombre)
            boton.clicked.connect(callback)
            acciones.addWidget(boton)
        acciones.addStretch()
        lay.addLayout(acciones)
        self.precio_comitente = QLabel(
            "Seleccioná una medición para obtener el costo directo y la Determinación de Precio.")
        self.precio_comitente.setWordWrap(True)
        lay.addWidget(self.precio_comitente)
        lay.addWidget(QLabel("Certificados registrados al comitente"))
        self.certificados_cliente = QTableWidget(0, 5)
        self.certificados_cliente.setHorizontalHeaderLabels(
            ["ID", "N.º", "Fecha", "Estado", "Importe certificado"])
        self.certificados_cliente.setColumnHidden(0, True)
        self.certificados_cliente.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        lay.addWidget(self.certificados_cliente, 2)
        tabs.addTab(cliente, "Comitente")

        sub = QWidget()
        sl = QVBoxLayout(sub)
        sl.setContentsMargins(8, 8, 8, 8)
        bar = QHBoxLayout()
        self.contratos = QComboBox()
        bar.addWidget(self.contratos, 1)
        for nombre, accion in (
            ("+ Contrato", self.nuevo_contrato),
            ("Emitir certificado", self.certificar),
            ("Exportar PDF", self.exportar_certificado),
            ("Actualizar", self.cargar_contratos),
        ):
            btn = QPushButton(nombre)
            btn.clicked.connect(accion)
            bar.addWidget(btn)
        sl.addLayout(bar)
        sl.addWidget(QLabel(
            "Certificados del subcontratista. Emitir no significa pagar; el anticipo y "
            "el fondo de reparo se liquidan según el contrato."))
        self.historial = QTableWidget(0, 6)
        self.historial.setHorizontalHeaderLabels(
            ["N.º", "Fecha", "Avance acumulado %", "Bruto", "Recupero", "Neto"])
        self.historial.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        sl.addWidget(self.historial, 4)
        self.contratos.currentIndexChanged.connect(self.cargar_historial)
        tabs.addTab(sub, "Subcontratistas")
        self.periodos.currentIndexChanged.connect(self.ver_avance)
        self.cargar()

    def seleccionar_medicion(self, val_id):
        """Usada al preparar un certificado desde Medición de avance."""
        pos = self.periodos.findData(val_id)
        if pos >= 0:
            self.periodos.setCurrentIndex(pos)
        self.ver_avance()

    def nuevo_contrato(self):
        from PySide6.QtWidgets import (QDialog, QFormLayout, QDialogButtonBox,
                                       QLineEdit, QDoubleSpinBox)
        dialogo = QDialog(self)
        dialogo.setWindowTitle("Nuevo subcontrato")
        dialogo.setMinimumWidth(400)
        formulario = QFormLayout(dialogo)
        nombre = QLineEdit()
        rubro = QLineEdit()
        campos = []
        for limite in (1e15, 1e15, 100, 100):
            campo = QDoubleSpinBox()
            campo.setDecimals(2)
            campo.setRange(0, limite)
            campo.setSingleStep(1)
            campos.append(campo)
        campos[0].setMinimum(0.01)
        formulario.addRow("Contratista", nombre)
        formulario.addRow("Rubro", rubro)
        for titulo, campo in zip(
            ("Monto contractual", "Anticipo entregado",
             "Recupero por certificado (%)", "Fondo de reparo (%)"), campos
        ):
            formulario.addRow(titulo, campo)
        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(dialogo.accept)
        botones.rejected.connect(dialogo.reject)
        formulario.addRow(botones)
        if dialogo.exec() != QDialog.Accepted:
            return
        db = get_db()
        try:
            inicializar(db)
            crear_contrato(db, self.pid, nombre.text(), rubro.text(),
                           *(campo.value() for campo in campos))
            db.commit()
        except Exception as exc:
            db.rollback()
            QMessageBox.warning(self, "Contrato", str(exc))
        finally:
            db.close()
        self.cargar_contratos()

    def cargar_contratos(self):
        db = get_db()
        try:
            inicializar(db)
            rows = db.execute(
                "SELECT id,contratista,rubro FROM contratos_subcontrato "
                "WHERE proyecto_id=? ORDER BY id", (self.pid,)
            ).fetchall()
        finally:
            db.close()
        seleccionado = self.contratos.currentData()
        self.contratos.blockSignals(True)
        self.contratos.clear()
        for cid, nombre, rubro in rows:
            self.contratos.addItem(f"{nombre} — {rubro}", cid)
        pos = self.contratos.findData(seleccionado)
        if pos >= 0:
            self.contratos.setCurrentIndex(pos)
        self.contratos.blockSignals(False)
        self.cargar_historial()

    def cargar_historial(self):
        cid = self.contratos.currentData()
        self.historial.setRowCount(0)
        if cid is None:
            return
        db = get_db()
        try:
            rows = db.execute(
                "SELECT numero,fecha,avance_acumulado,bruto,recupero,neto "
                "FROM certificados_subcontrato WHERE contrato_id=? ORDER BY numero",
                (cid,)
            ).fetchall()
        finally:
            db.close()
        self.historial.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, valor in enumerate(row):
                self.historial.setItem(i, j, QTableWidgetItem(str(valor)))

    def certificar(self):
        cid = self.contratos.currentData()
        if cid is None:
            return
        avance, ok = QInputDialog.getDouble(self, "Certificado de avance",
                                           "Avance acumulado (%):", 0, 0, 100, 2)
        if not ok:
            return
        from datetime import date
        db = get_db()
        try:
            numero, r = emitir_certificado(db, cid, avance, date.today().isoformat())
            db.commit()
            QMessageBox.information(self, "Certificado registrado",
                f"Certificado registrado. Neto a liquidar: $ {r['neto']:,.2f}")
        except Exception as exc:
            db.rollback()
            QMessageBox.warning(self, "No se puede certificar", str(exc))
        finally:
            db.close()
        self.cargar_historial()

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
        self.cargar_certificados_comitente()
        self.cargar_contratos()

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

    def exportar_certificado(self):
        """Genera el comprobante del certificado seleccionado, sin editarlo."""
        from html import escape
        from PySide6.QtGui import QTextDocument
        from PySide6.QtPrintSupport import QPrinter
        cid = self.contratos.currentData()
        fila = self.historial.currentRow()
        if cid is None or fila < 0:
            QMessageBox.information(self, "Certificado",
                "Seleccioná una fila del historial para exportar.")
            return
        numero_item = self.historial.item(fila, 0)
        if numero_item is None:
            return
        numero = int(numero_item.text())
        db = get_db()
        try:
            cabecera = db.execute(
                "SELECT contratista,rubro,monto,anticipo,recupero_pct,reparo_pct "
                "FROM contratos_subcontrato WHERE id=? AND proyecto_id=?",
                (cid, self.pid)
            ).fetchone()
            cert = db.execute(
                "SELECT numero,fecha,avance_acumulado,bruto,recupero,reparo,neto "
                "FROM certificados_subcontrato WHERE contrato_id=? AND numero=?",
                (cid, numero)
            ).fetchone()
        finally:
            db.close()
        if not cabecera or not cert:
            QMessageBox.warning(self, "Certificado", "No se encontró el registro.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar certificado",
            f"certificado-subcontrato-{cid}-{numero}.pdf", "PDF (*.pdf)")
        if not path:
            return
        c = [escape(str(x)) for x in cabecera]
        v = [escape(str(x)) for x in cert]
        conceptos = [
            ("Importe bruto del período", v[3]),
            ("Recuperación de anticipo", "- " + v[4]),
            ("Fondo de reparo", "- " + v[5]),
            ("Neto a liquidar", v[6]),
        ]
        tabla = "".join(
            "<tr><td style='padding:7px;border-bottom:1px solid #ddd;'>"
            + escape(nombre) + "</td><td align='right' style='padding:7px;"
            "border-bottom:1px solid #ddd;'>$ " + valor + "</td></tr>"
            for nombre, valor in conceptos
        )
        html = (
            "<html><body style='font-family:sans-serif;font-size:11pt;'>"
            "<h2>Certificado de avance de subcontrato</h2>"
            "<p>Comprobante contractual. No constituye factura ni recibo de pago.</p>"
            f"<p><b>Contratista:</b> {c[0]}<br><b>Rubro:</b> {c[1]}<br>"
            f"<b>Monto del contrato:</b> $ {c[2]}<br>"
            f"<b>Certificado N.º:</b> {v[0]}<br><b>Fecha:</b> {v[1]}<br>"
            f"<b>Avance acumulado:</b> {v[2]} %</p>"
            f"<table width='100%' cellspacing='0'>{tabla}</table>"
            "<p>Los importes son los registrados al emitir el certificado; "
            "verificar contrato, impuestos y documentación respaldatoria.</p>"
            "<br><br><p>Conformidad contratista: ________________________</p>"
            "<p>Conformidad contratante: ________________________</p>"
            "</body></html>"
        )
        try:
            printer = QPrinter(QPrinter.HighResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(path)
            document = QTextDocument()
            document.setHtml(html)
            document.print_(printer)
        except Exception as exc:
            QMessageBox.warning(self, "Error PDF", str(exc))
            return
        QMessageBox.information(self, "Certificado", "PDF generado en:\\n" + path)

    def exportar_comitente(self):
        """Imprime únicamente datos del certificado guardado y seleccionado."""
        from pathlib import Path
        from PySide6.QtGui import QTextDocument
        from PySide6.QtPrintSupport import QPrinter
        from core.certificados_comitente_pdf import html_certificado_comitente
        fila = self.certificados_cliente.currentRow()
        if fila < 0:
            QMessageBox.information(
                self, "Certificado", "Seleccioná un certificado registrado."
            )
            return
        certificado_id = int(self.certificados_cliente.item(fila, 0).text())
        db = get_db()
        try:
            html = html_certificado_comitente(db, certificado_id)
        except Exception as exc:
            QMessageBox.warning(self, "Certificado", str(exc))
            return
        finally:
            db.close()
        destino, _ = QFileDialog.getSaveFileName(
            self, "Guardar certificado al comitente",
            f"certificado-comitente-{certificado_id}.pdf", "PDF (*.pdf)"
        )
        if not destino:
            return
        try:
            printer = QPrinter(QPrinter.HighResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(destino)
            doc = QTextDocument()
            doc.setHtml(html)
            doc.print_(printer)
            if not Path(destino).is_file() or Path(destino).stat().st_size == 0:
                raise OSError("No se generó el archivo PDF")
        except Exception as exc:
            QMessageBox.warning(self, "Error de exportación", str(exc))
            return
        QMessageBox.information(self, "Certificado", "PDF guardado correctamente.")

    def cargar_certificados_comitente(self):
        db = get_db()
        try:
            iniciar_comitente(db)
            registros = db.execute(
                "SELECT id,numero,fecha,estado,total FROM certificados_comitente "
                "WHERE proyecto_id=? ORDER BY numero DESC", (self.pid,)
            ).fetchall()
        finally:
            db.close()
        self.certificados_cliente.setRowCount(len(registros))
        for i, fila in enumerate(registros):
            for col, dato in enumerate(fila):
                item = QTableWidgetItem(str(dato))
                self.certificados_cliente.setItem(i, col, item)

    def registrar_comitente(self):
        val_id = self.periodos.currentData()
        if val_id is None:
            QMessageBox.information(self, "Certificado", "Primero seleccioná una medición.")
            return
        db = get_db()
        try:
            registrar_desde_medicion(db, self.pid, val_id)
            db.commit()
        except Exception as exc:
            db.rollback()
            QMessageBox.warning(self, "Certificado", str(exc))
        finally:
            db.close()
        self.cargar_certificados_comitente()
        self.precio_comitente.setText(
            "Certificado registrado: la medición quedó cerrada para preservar "
            "los importes presentados."
        )

    def estado_comitente(self):
        fila = self.certificados_cliente.currentRow()
        if fila < 0:
            QMessageBox.information(self, "Estado", "Seleccioná un certificado.")
            return
        certificado_id = int(self.certificados_cliente.item(fila, 0).text())
        estados = ["borrador", "presentado", "observado", "aprobado"]
        estado, ok = QInputDialog.getItem(
            self, "Estado del certificado", "Nuevo estado:", estados, 0, False)
        if not ok:
            return
        db = get_db()
        try:
            cambiar_estado(db, certificado_id, estado)
            db.commit()
        except Exception as exc:
            db.rollback()
            QMessageBox.warning(self, "No se pudo actualizar", str(exc))
        finally:
            db.close()
        self.cargar_certificados_comitente()

    def ver_precio_comitente(self):
        vid = self.periodos.currentData()
        if vid is None:
            return
        db = get_db()
        try:
            resultado = resumen_comitente(db, vid)
            texto = " | ".join(
                f"{nombre}: $ {importe:,.2f}"
                for nombre, importe in resultado["adicionales"]
            )
            self.precio_comitente.setText(
                f"CD: $ {resultado['costo_directo']:,.2f} | "
                f"{texto} | TOTAL: $ {resultado['total']:,.2f}"
            )
        except Exception as exc:
            QMessageBox.warning(self, "Determinación de Precio", str(exc))
        finally:
            db.close()

