# SPDX-License-Identifier: GPL-3.0-or-later
"""Registro contractual simple de subcontratos y certificados consecutivos."""
from __future__ import annotations
from core.certificados_contratos import certificado_subcontrato


def inicializar(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS contratos_subcontrato (
        id INTEGER PRIMARY KEY,
        proyecto_id INTEGER NOT NULL REFERENCES proyectos(id),
        contratista TEXT NOT NULL,
        rubro TEXT NOT NULL,
        monto TEXT NOT NULL,
        anticipo TEXT NOT NULL DEFAULT '0',
        recupero_pct TEXT NOT NULL DEFAULT '0',
        reparo_pct TEXT NOT NULL DEFAULT '0'
    );
    CREATE TABLE IF NOT EXISTS certificados_subcontrato (
        id INTEGER PRIMARY KEY,
        contrato_id INTEGER NOT NULL REFERENCES contratos_subcontrato(id),
        numero INTEGER NOT NULL,
        fecha TEXT NOT NULL DEFAULT '',
        avance_acumulado TEXT NOT NULL,
        bruto TEXT NOT NULL,
        recupero TEXT NOT NULL,
        reparo TEXT NOT NULL,
        neto TEXT NOT NULL,
        UNIQUE(contrato_id,numero)
    );
    """)


def crear_contrato(conn, proyecto_id, contratista, rubro, monto, anticipo=0,
                   recupero_pct=0, reparo_pct=0):
    from decimal import Decimal
    import math
    valores = [Decimal(str(n)) for n in (monto, anticipo, recupero_pct, reparo_pct)]
    if any(not v.is_finite() for v in valores):
        raise ValueError("Los valores deben ser finitos")
    m, a, r, f = valores
    if m <= 0 or a < 0 or a > m or not (0 <= r <= 100 and 0 <= f <= 100):
        raise ValueError("Importes y porcentajes contractuales inválidos")
    if not contratista.strip() or not rubro.strip():
        raise ValueError("Completá contratista y rubro")
    row = conn.execute("INSERT INTO contratos_subcontrato "
        "(proyecto_id,contratista,rubro,monto,anticipo,recupero_pct,reparo_pct) "
        "VALUES(?,?,?,?,?,?,?)",
        (proyecto_id,contratista.strip(),rubro.strip(),str(m),str(a),str(r),str(f)))
    return row.lastrowid


def emitir_certificado(conn, contrato_id, avance_pct, fecha=''):
    from decimal import Decimal
    contrato = conn.execute(
        "SELECT monto,anticipo,recupero_pct,reparo_pct FROM contratos_subcontrato WHERE id=?",
        (contrato_id,)).fetchone()
    if contrato is None:
        raise ValueError("Contrato inexistente")
    anteriores = conn.execute(
        "SELECT numero,avance_acumulado,recupero FROM certificados_subcontrato "
        "WHERE contrato_id=? ORDER BY numero", (contrato_id,)).fetchall()
    previo = Decimal(str(anteriores[-1][1])) if anteriores else Decimal('0')
    recuperado = sum(Decimal(str(x[2])) for x in anteriores)
    pendiente = Decimal(str(contrato[1])) - recuperado
    datos = certificado_subcontrato(contrato[0], previo, avance_pct, pendiente,
                                    contrato[2], contrato[3])
    if Decimal(str(avance_pct)) <= previo:
        raise ValueError("El avance debe superar el ya certificado")
    numero = len(anteriores) + 1
    cur = conn.execute(
        "INSERT INTO certificados_subcontrato "
        "(contrato_id,numero,fecha,avance_acumulado,bruto,recupero,reparo,neto) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (contrato_id,numero,fecha,str(avance_pct),str(datos['bruto']),
         str(datos['recupero']),str(datos['fondo_reparo']),str(datos['neto'])))
    return cur.lastrowid, datos
