"""Factorías explícitas de dependencias reales para la ruta LIVE."""

from __future__ import annotations

import os
from typing import Any, Callable

from backend.banxico_client import CURVE_REQUIRED_SERIES
from backend.elara_executor import DEFAULT_MODEL, ElaraExecutor, build_openai_client
from backend.siena_executor import execute_siena


class LiveDependencyError(RuntimeError):
    """Fallo sanitizado de credenciales o configuración LIVE."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def require_live_credentials() -> None:
    """Comprueba presencia sin leer ni exponer valores de variables secretas."""
    if not os.environ.get("OPENAI_API_KEY"):
        raise LiveDependencyError("OPENAI_API_KEY_NO_CONFIGURADA")
    if not os.environ.get("BANXICO_API_TOKEN"):
        raise LiveDependencyError("BANXICO_API_TOKEN_NO_CONFIGURADO")


def build_live_elara() -> ElaraExecutor:
    """Construye Elara real conservando sus límites y guardrails existentes."""
    if not os.environ.get("OPENAI_API_KEY"):
        raise LiveDependencyError("OPENAI_API_KEY_NO_CONFIGURADA")
    return ElaraExecutor(build_openai_client(), model=DEFAULT_MODEL)


def build_live_siena_provider() -> Callable[[str], dict[str, Any]]:
    """Entrega un provider LIVE sin fallback a snapshots ni datos sintéticos."""
    if not os.environ.get("BANXICO_API_TOKEN"):
        raise LiveDependencyError("BANXICO_API_TOKEN_NO_CONFIGURADO")

    def provider(fecha_corte: str) -> dict[str, Any]:
        return execute_siena(fecha_corte, list(CURVE_REQUIRED_SERIES))

    return provider
