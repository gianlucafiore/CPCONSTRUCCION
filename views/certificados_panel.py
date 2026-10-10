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


class CertificadosPanel(QWidget):
    """Calculadora de liquidación: avances persistidos solo en valorizaciones."""
    def __init__(self, pid, parent=None):
        super().__init__(parent)
        self.pid = pid
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        top = QHBoxLayout()
        top.addWidget(QLabel("Comitente · avance medido del período"))
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
            ["Ítem", "Partida", "Anterior ($)", "Período ($)", "Acumulado ($)"]
        )
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        lay.addWidget(self.tabla, 1)
        boton_precio = QPushButton('Calcular Determinación de Precio')
        boton_precio.clicked.connect(self.ver_precio_comitente)
        lay.addWidget(boton_precio)
        self.precio_comitente = QLabel('Sin calcular')
        lay.addWidget(self.precio_comitente)
        lay.addWidget(QLabel("Simulador de liquidación · no registra pagos"))
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
        lay.addWidget(QLabel("Subcontratistas · contratos y certificados emitidos"))
        aviso_sub = QLabel(
            "Cada subcontrato tiene sus precios propios y su avance certificado. "
            "Los recuperos de anticipos y fondos de reparo son contractuales. "
            "Emitir un certificado no equivale a realizar un pago."
        )
        aviso_sub.setWordWrap(True)
        lay.addWidget(aviso_sub)
        bar = QHBoxLayout()
        self.contratos = QComboBox()
        bar.addWidget(self.contratos, 1)
        for nombre, accion in (("+ Contrato", self.nuevo_contrato),
                              ("Emitir certificado", self.certificar),
                              ("Exportar PDF", self.exportar_certificado),
                              ("Actualizar", self.cargar_contratos)):
            btn = QPushButton(nombre)
            btn.clicked.connect(accion)
            bar.addWidget(btn)
        lay.addLayout(bar)
        self.historial = QTableWidget(0, 6)
        self.historial.setHorizontalHeaderLabels(
            ["N.º", "Fecha", "Avance acumulado %", "Bruto", "Recupero", "Neto"]
        )
        self.historial.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        lay.addWidget(self.historial, 1)
        self.contratos.currentIndexChanged.connect(self.cargar_historial)
        self.cargar()

    def nuevo_contrato(self):
        nombre, ok = QInputDialog.getText(self, "Subcontrato", "Contratista:")
        if not ok or not nombre.strip():
            return
        rubro, ok = QInputDialog.getText(self, "Subcontrato", "Rubro:")
        if not ok or not rubro.strip():
            return
        monto, ok = QInputDialog.getDouble(self, "Subcontrato",
                                           "Monto contractual:", 0, 0.01, 1e15, 2)
        if not ok:
            return
        anticipo, ok = QInputDialog.getDouble(self, "Subcontrato",
                                             "Anticipo entregado:", 0, 0, monto, 2)
        if not ok:
            return
        recupero, ok = QInputDialog.getDouble(self, "Subcontrato",
                                             "Recupero por certificado (%):", 0, 0, 100, 2)
        if not ok:
            return
        reparo, ok = QInputDialog.getDouble(self, "Subcontrato",
                                           "Fondo de reparo (%):", 0, 0, 100, 2)
        if not ok:
            return
        db = get_db()
        try:
            inicializar(db)
            crear_contrato(db, self.pid, nombre, rubro, monto, anticipo, recupero, reparo)
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
