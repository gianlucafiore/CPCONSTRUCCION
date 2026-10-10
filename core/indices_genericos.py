# SPDX-License-Identifier: GPL-3.0-or-later
"""Series de índices y actualización contractual independiente del país.

No implica que una fórmula sea legalmente aplicable: corresponde al contrato
definir fuente, series, períodos, pesos y alcance de cada actualización.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from sqlite3 import Connection


def inicializar(conn: Connection) -> None:
    """Crea tablas complementarias sin modificar datos ni tablas legacy."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS fuentes_indices (
            id INTEGER PRIMARY KEY,
            nombre TEXT NOT NULL,
            pais TEXT NOT NULL DEFAULT '',
            sitio_web TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS series_indices (
            id INTEGER PRIMARY KEY,
            fuente_id INTEGER NOT NULL REFERENCES fuentes_indices(id),
            codigo TEXT NOT NULL,
            nombre TEXT NOT NULL,
            base_descripcion TEXT NOT NULL DEFAULT '',
            unidad TEXT NOT NULL DEFAULT 'indice',
            UNIQUE(fuente_id, codigo)
        );
        CREATE TABLE IF NOT EXISTS valores_indices (
            serie_id INTEGER NOT NULL REFERENCES series_indices(id),
            periodo TEXT NOT NULL,
            valor TEXT NOT NULL,
            PRIMARY KEY(serie_id, periodo),
            CHECK(length(periodo)=7)
        );
        CREATE TABLE IF NOT EXISTS formulas_actualizacion (
            id INTEGER PRIMARY KEY,
            proyecto_id INTEGER NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,
            nombre TEXT NOT NULL,
            periodo_base TEXT NOT NULL,
            metodo TEXT NOT NULL DEFAULT 'ponderado',
            CHECK(metodo IN ('ponderado', 'simple'))
        );
        CREATE TABLE IF NOT EXISTS formula_indices (
            formula_id INTEGER NOT NULL REFERENCES formulas_actualizacion(id) ON DELETE CASCADE,
            serie_id INTEGER NOT NULL REFERENCES series_indices(id),
            peso TEXT NOT NULL,
            PRIMARY KEY(formula_id, serie_id)
        );
    """)


def guardar_valor(conn: Connection, serie_id: int, periodo: str, valor) -> None:
    """Los valores son positivos; YYYY-MM es obligatorio."""
    import re
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", periodo):
        raise ValueError("Período inválido (usar AAAA-MM)")
    v = Decimal(str(valor))
    if not v.is_finite() or v <= 0:
        raise ValueError("El índice debe ser positivo y finito")
    conn.execute(
        "INSERT INTO valores_indices(serie_id, periodo, valor) VALUES(?,?,?) "
        "ON CONFLICT(serie_id, periodo) DO UPDATE SET valor=excluded.valor",
        (serie_id, periodo, str(v)),
    )


def calcular_factor(conn: Connection, formula_id: int, periodo_final: str) -> dict:
    """Promedio de las variaciones relativas, no de niveles de índices.

    La fórmula ponderada normaliza los pesos positivos a 1; 'simple'
    asigna peso igual a cada serie. Ningún índice se suma o encadena.
    """
    form = conn.execute(
        "SELECT periodo_base, metodo FROM formulas_actualizacion WHERE id=?",
        (formula_id,),
    ).fetchone()
    if form is None:
        raise ValueError("Fórmula inexistente")
    base, metodo = form[0], form[1]
    componentes = conn.execute(
        """SELECT fi.serie_id, fi.peso, vb.valor, vf.valor
           FROM formula_indices fi
           LEFT JOIN valores_indices vb ON vb.serie_id=fi.serie_id AND vb.periodo=?
           LEFT JOIN valores_indices vf ON vf.serie_id=fi.serie_id AND vf.periodo=?
           WHERE fi.formula_id=? ORDER BY fi.serie_id""",
        (base, periodo_final, formula_id),
    ).fetchall()
    if not componentes:
        raise ValueError("La fórmula no tiene series")
    pesos = []
    razones = []
    for serie_id, peso, vb, vf in componentes:
        if vb is None or vf is None:
            raise ValueError(f"Falta un índice para la serie {serie_id}")
        peso_d = Decimal(str(peso))
        inicial = Decimal(str(vb))
        final = Decimal(str(vf))
        if not all(v.is_finite() for v in (peso_d, inicial, final)):
            raise ValueError("Valores no finitos")
        if peso_d <= 0 or inicial <= 0 or final <= 0:
            raise ValueError("Pesos e índices deben ser positivos")
        pesos.append(peso_d)
        razones.append(final / inicial)
    if metodo not in ('simple', 'ponderado'):
        raise ValueError("Método de actualización desconocido")
    if metodo == 'simple':
        pesos = [Decimal(1) for _ in pesos]
    total_pesos = sum(pesos)
    factor = sum(w * r for w, r in zip(pesos, razones)) / total_pesos
    return {
        "factor": factor,
        "variacion_pct": (factor - 1) * 100,
        "periodo_base": base,
        "periodo_final": periodo_final,
        "componentes": [
            {"serie_id": c[0], "peso_normalizado": w / total_pesos,
             "indice_base": Decimal(str(c[2])),
             "indice_final": Decimal(str(c[3])), "factor": razon}
            for c, w, razon in zip(componentes, pesos, razones)
        ],
    }


def actualizar_importe(importe, factor) -> Decimal:
    monto, f = Decimal(str(importe)), Decimal(str(factor))
    if not monto.is_finite() or not f.is_finite() or monto < 0 or f < 0:
        raise ValueError("Monto o factor inválido")
    return (monto * f).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
