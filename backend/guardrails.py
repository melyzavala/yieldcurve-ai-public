"""Controles deterministas comunes para YieldCurve AI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math
import re
from typing import Any


MAX_USER_MESSAGE_CHARS = 4_000


@dataclass(frozen=True)
class RequestGuardrail:
    status: str
    code: str | None = None


_UNSAFE_PATTERNS = (
    r"ignora(?:r)?\s+(?:las?\s+)?instrucciones",
    r"ignore\s+(?:all\s+)?(?:previous|prior|system)\s+instructions",
    r"(?:system\s+prompt|prompt\s+interno|instrucciones\s+internas)",
    r"(?:api\s*key|api_key|token|credential|credencial|secreto|secret)",
    r"(?:act[úu]a|actua)\s+como\s+(?:administrador|admin)",
    r"(?:omite|omitir|bypass|salt[ae])\s+(?:a\s+)?atenea",
    r"(?:usa|acepta)\s+(?:estos?\s+)?datos?\s+aunque\s+sean\s+falsos",
    r"(?:p[aá]gina|web|archivo|fuente\s+externa).{0,80}(?:instrucciones|obedecer)",
)
_OUT_OF_SCOPE_PATTERNS = (
    r"\b(?:compra|comprar|vende|vender|venta|operar|operaci[oó]n|ejecuta\s+una\s+transacci[oó]n)\b",
    r"\b(?:recomienda|recomendaci[oó]n)\b.{0,60}\b(?:inversi[oó]n|comprar|vender)\b",
)
_SCOPE_PATTERNS = (r"\b(?:curva|tasas?|cetes|m-?bonos?|mbonos|repricing|valuaci[oó]n|riesgo)\b",)
_DATE_TOKEN = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


def preflight_user_request(message: Any) -> RequestGuardrail:
    """Clasifica una solicitud sin ejecutar LLM, red ni herramientas externas."""
    if not isinstance(message, str) or not message.strip() or len(message) > MAX_USER_MESSAGE_CHARS:
        return RequestGuardrail("INVALID_FORMAT", "FORMATO_SOLICITUD_INVALIDO")
    if "\x00" in message:
        return RequestGuardrail("INVALID_FORMAT", "CARACTER_NO_PERMITIDO")
    normalized = " ".join(message.casefold().split())
    if any(re.search(pattern, normalized, flags=re.IGNORECASE | re.DOTALL) for pattern in _UNSAFE_PATTERNS):
        return RequestGuardrail("UNSAFE_REQUEST", "SOLICITUD_NO_CONFIABLE")
    if any(re.search(pattern, normalized, flags=re.IGNORECASE | re.DOTALL) for pattern in _OUT_OF_SCOPE_PATTERNS):
        return RequestGuardrail("OUT_OF_SCOPE", "SOLICITUD_FUERA_DE_ALCANCE")
    if not any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in _SCOPE_PATTERNS):
        return RequestGuardrail("OUT_OF_SCOPE", "SOLICITUD_FUERA_DE_ALCANCE")
    for year, month, day in _DATE_TOKEN.findall(message):
        try:
            date(int(year), int(month), int(day))
        except ValueError:
            return RequestGuardrail("INVALID_FORMAT", "FECHA_INVALIDA")
    if not _DATE_TOKEN.search(message) and not re.search(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b|\b\d{1,2}\s+de\s+[a-záéíóú]+\s+de\s+\d{4}\b", normalized):
        return RequestGuardrail("INCOMPLETE", "FECHA_CORTE_FALTANTE")
    return RequestGuardrail("VALID")


def first_nonfinite(value: Any) -> str | None:
    """Devuelve una causa sanitizada para NaN/inf."""
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return None
    if isinstance(value, (int, float)):
        return None if math.isfinite(float(value)) else "VALOR_NO_FINITO"
    if isinstance(value, list):
        return next((issue for item in value if (issue := first_nonfinite(item))), None)
    if isinstance(value, dict):
        return next((issue for item in value.values() if (issue := first_nonfinite(item))), None)
    return "TIPO_NO_PERMITIDO"


def validate_quantitative_payload(payload: Any) -> str | None:
    """Controles mínimos previos al motor, sin duplicar su validación financiera."""
    if not isinstance(payload, dict):
        return "PAYLOAD_CUANTITATIVO_INVALIDO"
    issue = first_nonfinite(payload)
    if issue:
        return issue
    valuation = payload.get("valuation_date")
    try:
        valuation_date = date.fromisoformat(valuation) if isinstance(valuation, str) else None
    except ValueError:
        return "FECHA_VALUACION_INVALIDA"
    if valuation_date is None:
        return "FECHA_VALUACION_INVALIDA"
    for instrument in payload.get("instruments", []):
        if not isinstance(instrument, dict):
            return "INSTRUMENTO_INVALIDO"
        price = instrument.get("dirty_price")
        if price is not None and (not isinstance(price, (int, float)) or isinstance(price, bool) or price <= 0):
            return "PRECIO_INVALIDO"
        maturity = instrument.get("maturity_date")
        if maturity is not None:
            try:
                if date.fromisoformat(maturity) <= valuation_date:
                    return "VENCIMIENTO_NO_POSTERIOR"
            except (TypeError, ValueError):
                return "VENCIMIENTO_INVALIDO"
    return None


def valid_siena_for_downstream(siena: Any, expected_date: str) -> bool:
    """Impide que Orion promueva datos rechazados o incompletos."""
    if not isinstance(siena, dict) or siena.get("estado") != "DATOS_VALIDOS":
        return False
    if siena.get("fecha_corte") != expected_date or siena.get("errores"):
        return False
    observations = siena.get("observaciones")
    if not isinstance(observations, list) or not observations:
        return False
    return all(
        isinstance(item, dict) and item.get("fecha") == expected_date and item.get("valida") is True
        and isinstance(item.get("valor"), (int, float)) and not isinstance(item.get("valor"), bool)
        and math.isfinite(float(item["valor"]))
        for item in observations
    )
