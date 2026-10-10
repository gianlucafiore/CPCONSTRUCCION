# SPDX-License-Identifier: GPL-3.0-or-later
"""Herramientas seguras para copiar, crear y verificar bases SQLite."""
from __future__ import annotations

import sqlite3
from pathlib import Path


def verificar_base(ruta: str | Path) -> dict:
    path = Path(ruta).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"No existe la base: {path}")
    # mode=ro evita crear accidentalmente una base SQLite vacía.
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    try:
        estado = db.execute("PRAGMA integrity_check").fetchone()[0]
        if estado != "ok":
            raise ValueError(f"Base SQLite dañada: {estado}")
        tablas = {r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        if "proyectos" not in tablas:
            raise ValueError("No parece una base compatible con CPconstruccion")
        return {"ruta": str(path), "tablas": len(tablas), "integridad": estado}
    finally:
        db.close()


def copiar_base(origen: str | Path, destino: str | Path) -> Path:
    """Backup consistente con SQLite; nunca sobrescribe el destino."""
    src = Path(origen).expanduser().resolve()
    dst = Path(destino).expanduser().resolve()
    verificar_base(src)
    if src == dst or dst.exists():
        raise FileExistsError("El destino ya existe; elegí otro nombre")
    if not dst.parent.is_dir():
        raise FileNotFoundError("La carpeta destino no existe")
    db = sqlite3.connect(src.as_uri() + "?mode=ro", uri=True)
    try:
        with sqlite3.connect(dst) as target:
            db.backup(target)
        verificar_base(dst)
        return dst
    except Exception:
        if dst.exists():
            dst.unlink()
        raise
    finally:
        db.close()
