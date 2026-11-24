"""Capa única de aplicación para casos simulados de YieldCurve AI.

No implementa cálculos financieros ni aprobaciones humanas. Orquesta los
ejecutores versionados y conserva sus contratos como fuente de verdad.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from backend.banxico_client import CF300_SERIES, CURVE_REQUIRED_SERIES, SERIES_CATALOG
from backend.elara_executor import ElaraResult, InvocationRecord
from backend.guardrails import preflight_user_request, valid_siena_for_downstream
from backend.orion_executor import execute_orion
from backend.security_cost_loop import run_security_cost_loop
from backend.siena_to_excel_adapter import SienaToExcelAdapterError, build_excel_payload_from_siena
from backend.cost_estimator import CostEstimationError, estimate_cost_usd, model_rates


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEMO_DATA = ROOT / "data" / "demo_banxico_2026-11-11.json"
DEMO_DATE = "2026-11-11"
SienaProvider = Callable[[str], dict[str, Any]]


def _issue(code: str, message: str) -> dict[str, str]:
    return {"codigo": code, "mensaje": message}


class _DemoElaraExecutor:
    """Dependencia local determinista para DEMO; no crea clientes ni usa red."""

    def __init__(self, fecha_corte: str) -> None:
        self.fecha_corte = fecha_corte

    def run(self, message: str, trusted_context: dict[str, str] | None = None) -> ElaraResult:
        guardrail = preflight_user_request(message)
        if guardrail.status != "VALID":
            return ElaraResult(
                output=None,
                record=InvocationRecord("DEMO_LOCAL", None, None, None, 0, guardrail.status, guardrail.code),
            )
        return ElaraResult(
            output={
                "schema_version": "1.0.0", "decision": "ACEPTAR",
                "fecha_corte_normalizada": self.fecha_corte,
                "instrumentos_solicitados": ["CETES", "MBONOS"],
                "proposito": "Valuación y análisis de riesgo de un portafolio ficticio.",
                "datos_faltantes": [], "motivos_rechazo": [], "advertencias": [],
                "seguridad": {"inyeccion_prompt_detectada": False, "instrucciones_no_confiables_ignoradas": False},
            },
            record=InvocationRecord("DEMO_LOCAL", None, None, None, 0, "VALID"),
        )


def _case(
    *, caso_id: str, version_caso: int, version_curva: str, fecha_corte: str,
    canal_origen: str, solicitud: str,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "contrato_version": "1.0.0", "caso_id": caso_id, "version_caso": version_caso,
        "version_curva": version_curva, "fecha_corte": fecha_corte, "canal_origen": canal_origen,
        "modo": "SIMULADO", "estado": "RECIBIDO", "objetivo": solicitud,
        "agente_responsable": "Orion", "referencias": {"datos": [], "calculos": [], "validaciones": []},
        "advertencias": [], "errores": [], "marcas_tiempo": {"creado_en": now, "actualizado_en": now},
        "trazabilidad": {"correlation_id": f"CORR-{caso_id}", "traza_id": f"TRAZA-{caso_id}", "referencias_consumo": []},
        "aprobacion_humana": {"estado": "PENDIENTE"}, "salidas_especializadas": {},
    }


def _resources() -> list[dict[str, Any]]:
    return [
        {"tipo": "CUADRO_SIE", "identificador": "CF300", "series": [item for item in CURVE_REQUIRED_SERIES if item in CF300_SERIES]},
        {"tipo": "SERIE_SIE", "identificador": "SF43774", "series": ["SF43774"]},
    ]


def load_demo_siena(fecha_corte: str, data_path: Path = DEFAULT_DEMO_DATA) -> dict[str, Any]:
    """Crea una salida contractual Siena desde un snapshot estático, sin red."""
    try:
        snapshot = json.loads(data_path.read_text(encoding="utf-8"))
        values = snapshot["observaciones"]
    except (OSError, ValueError, KeyError, TypeError):
        return _demo_error(fecha_corte, "DEMO_SNAPSHOT_INVALIDO")
    if snapshot.get("fecha_corte") != fecha_corte or fecha_corte != DEMO_DATE or not isinstance(values, dict):
        return _demo_error(fecha_corte, "DEMO_FECHA_NO_SOPORTADA")
    observations = []
    for serie_id in CURVE_REQUIRED_SERIES:
        if serie_id not in values:
            return _demo_error(fecha_corte, "DEMO_SERIE_FALTANTE")
        observations.append({"serie_id": serie_id, "fecha": fecha_corte, "valor": values[serie_id], "unidad": SERIES_CATALOG[serie_id]["unidad"], "valida": True})
    return {
        "estado": "DATOS_VALIDOS", "fecha_corte": fecha_corte, "modo": "SIMULADO",
        "fuente": {"proveedor": "Banco de México", "cuadro": "CF300", "recursos": _resources(), "api_base": "https://www.banxico.org.mx/SieAPIRest/service", "consultada_en": None, "datos_mercado": "REALES"},
        "series": [{"serie_id": item, **SERIES_CATALOG[item], "estado": "DISPONIBLE", **({"requiere_flujos_individuales": True} if SERIES_CATALOG[item]["instrumento"] == "MBONOS" else {})} for item in CURVE_REQUIRED_SERIES],
        "observaciones": observations,
        "resumen_validacion": {"series_solicitadas": 26, "series_con_observacion": 26, "observaciones_validas": 26, "observaciones_rechazadas": 0},
        "advertencias": [{"codigo": "MBONOS_RANGO", "severidad": "ADVERTENCIA", "mensaje": "Los Bonos M de CF300 son representativos por rango; no proporcionan flujos de una emisión individual."}],
        "errores": [],
    }


def _demo_error(fecha_corte: str, code: str) -> dict[str, Any]:
    return {
        "estado": "DATOS_RECHAZADOS", "fecha_corte": fecha_corte, "modo": "SIMULADO",
        "fuente": {"proveedor": "Banco de México", "cuadro": "CF300", "recursos": _resources(), "api_base": "https://www.banxico.org.mx/SieAPIRest/service", "consultada_en": None, "datos_mercado": "NO_CONSULTADOS"},
        "series": [], "observaciones": [],
        "resumen_validacion": {"series_solicitadas": 26, "series_con_observacion": 0, "observaciones_validas": 0, "observaciones_rechazadas": 0},
        "advertencias": [], "errores": [{"codigo": code, "severidad": "ERROR", "mensaje": "El snapshot DEMO no puede usarse para construir la curva."}],
    }


def _source(execution_mode: str, siena_consultada: bool) -> dict[str, str]:
    return {
        "execution_mode": execution_mode,
        "source_mode": (
            "FIXTURE_BANXICO_2026-11-11" if execution_mode == "DEMO" else "BANXICO_SIE_LIVE"
        ) if siena_consultada else "NOT_QUERIED",
    }


def _output(case: dict[str, Any], execution_mode: str, *, estado: str, dictamen: str, elara: Any = None, siena: Any = None, nash: Any = None, atenea: Any = None, traza: list[dict[str, Any]] | None = None, errores: list[dict[str, str]] | None = None, advertencias: list[dict[str, Any]] | None = None, consumo: dict[str, Any] | None = None, telemetria: dict[str, Any] | None = None, version_curva: str | None = None, siena_consultada: bool = False) -> dict[str, Any]:
    return {
        "caso_id": case["caso_id"], "version_caso": case["version_caso"], "version_curva": version_curva or case["version_curva"],
        "modo": "SIMULADO", "execution_mode": execution_mode, "fecha_corte": case["fecha_corte"],
        "estado": estado, "dictamen_tecnico": dictamen, "requiere_aprobacion_humana": True,
        "elara": elara, "siena": siena, "nash": nash, "atenea": atenea,
        "traza": traza or [], "fuente_datos": _source(execution_mode, siena_consultada), "errores": errores or [],
        "advertencias": advertencias or [],
        "consumo": consumo or {"consumo_api_real_usd": 0.0, "costo_estimado_usd": None, "costo_infraestructura_usd": None},
        "telemetria": telemetria or {},
    }


def _siena_is_usable(siena: dict[str, Any], fecha_corte: str) -> bool:
    summary = siena.get("resumen_validacion", {}) if isinstance(siena, dict) else {}
    return valid_siena_for_downstream(siena, fecha_corte) and summary == {
        "series_solicitadas": 26, "series_con_observacion": 26, "observaciones_validas": 26, "observaciones_rechazadas": 0,
    }


def _case_is_valid(case: dict[str, Any]) -> bool:
    """Valida el contrato común antes de habilitar cualquier ejecutor."""
    try:
        schema = json.loads((ROOT / "agents" / "contracts" / "case.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(case)
        return True
    except (ValidationError, OSError, ValueError, TypeError):
        return False


def _elara_telemetry(record: InvocationRecord, execution_mode: str, consumption: dict[str, Any]) -> dict[str, Any]:
    """Expone únicamente telemetría de uso que no contiene credenciales."""
    total_tokens = record.input_tokens + record.output_tokens if isinstance(record.input_tokens, int) and isinstance(record.output_tokens, int) else None
    estimate = consumption.get("componentes_estimados_usd") if isinstance(consumption, dict) else None
    return {
        "agente": "Elara", "proveedor": "OpenAI", "modelo": record.model, "model": record.model,
        "response_id": record.response_id, "input_tokens": record.input_tokens,
        "cached_input_tokens": record.cached_input_tokens,
        "output_tokens": record.output_tokens, "total_tokens": total_tokens,
        "cache_write_tokens": record.cache_write_tokens, "ttl_30m_tokens": record.ttl_30m_tokens,
        "ttl_12h_tokens": record.ttl_12h_tokens, "duracion_ms": record.duration_ms,
        "cost_usd": float(estimate["total_usd"]) if isinstance(estimate, dict) and estimate.get("total_usd") is not None else None,
        "cost_status": "ESTIMATED_FROM_VERIFIED_RATE" if isinstance(estimate, dict) else consumption.get("cost_status", "NOT_OBSERVED_DEMO" if execution_mode == "DEMO" else "USAGE_UNAVAILABLE"),
        "status": record.status, "error_code": record.error_code,
        "diagnostico_validacion": record.validation_diagnostic,
    }


def _consumption(execution_mode: str, record: InvocationRecord) -> dict[str, Any]:
    if execution_mode == "DEMO":
        return {"consumo_api_real_usd": 0.0, "costo_estimado_usd": None, "costo_infraestructura_usd": None, "cost_status": "NOT_OBSERVED_DEMO"}
    measured = {
        "modelo": record.model, "input_tokens": record.input_tokens,
        "cached_input_tokens": record.cached_input_tokens,
        "output_tokens": record.output_tokens,
        "total_tokens": record.input_tokens + record.output_tokens if isinstance(record.input_tokens, int) and isinstance(record.output_tokens, int) else None,
        "cache_write_tokens": record.cache_write_tokens,
        "ttl_30m_tokens": record.ttl_30m_tokens,
        "ttl_12h_tokens": record.ttl_12h_tokens,
    }
    estimate: dict[str, str] | None = None
    try:
        if record.status == "VALID":
            estimate = estimate_cost_usd(record.to_dict(), model_rates(ROOT / "costs" / "tarifas.csv", record.model))
    except CostEstimationError as error:
        return {"consumo_api_real_usd": None, "costo_estimado_usd": None, "costo_infraestructura_usd": None,
                "consumo_medido": measured, "componentes_estimados_usd": None, "cost_status": error.code}
    except (OSError, ValueError):
        estimate = None
    return {
        "consumo_api_real_usd": None,
        "costo_estimado_usd": estimate["total_usd"] if estimate else None,
        "costo_infraestructura_usd": None,
        "consumo_medido": measured,
        "componentes_estimados_usd": estimate,
        "cost_status": "ESTIMATED_FROM_VERIFIED_RATE" if estimate else "PRICING_UNAVAILABLE",
    }


def _live_budget_is_valid(config: dict[str, Any]) -> bool:
    """Impide invocar un LLM LIVE sin un tope explícito de una llamada."""
    return config.get("max_llm_calls") == 1


def _siena_error_code(siena: Any) -> str:
    if isinstance(siena, dict):
        errors = siena.get("errores")
        if isinstance(errors, list) and errors and isinstance(errors[0], dict):
            code = errors[0].get("codigo")
            if code in {"CREDENCIAL_BANXICO_NO_CONFIGURADA", "DATOS_BANXICO_NO_DISPONIBLES", "CONSULTA_BANXICO_FALLIDA"}:
                return code
    return "SIENA_DATOS_NO_VALIDOS"


def _trusted_elara_context(case: dict[str, Any]) -> dict[str, str]:
    """Deriva sólo el contexto permitido de un caso ya validado internamente."""
    return {field: case[field] for field in ("modo", "fecha_corte", "canal_origen")}


def run_yieldcurve_case(
    *, caso_id: str, version_caso: int, version_curva: str, fecha_corte: str,
    canal_origen: str, solicitud: str, budget_config: dict[str, Any], invocation_id: str,
    execution_mode: str = "DEMO", elara_executor: Any | None = None,
    siena_provider: SienaProvider | None = None,
    demo_data_path: Path = DEFAULT_DEMO_DATA,
) -> dict[str, Any]:
    """Ejecuta una ruta DEMO o LIVE sin fallback entre ambas ni aprobación humana."""
    case = _case(caso_id=caso_id, version_caso=version_caso, version_curva=version_curva,
                 fecha_corte=fecha_corte, canal_origen=canal_origen, solicitud=solicitud)
    if execution_mode not in {"DEMO", "LIVE"}:
        return _output(case, execution_mode, estado="RECHAZADO", dictamen="NO_EMITIDO", errores=[_issue("EXECUTION_MODE_INVALIDO", "El modo de ejecución no está autorizado.")])
    if not _case_is_valid(case):
        return _output(case, execution_mode, estado="RECHAZADO", dictamen="NO_EMITIDO", errores=[_issue("CASO_INVALIDO", "El caso no cumple el contrato común.")])
    if execution_mode == "LIVE" and not _live_budget_is_valid(budget_config):
        return _output(case, execution_mode, estado="DETENIDO", dictamen="NO_EMITIDO", errores=[_issue("LIMITE_LLM_INVALIDO", "LIVE requiere un límite explícito de una llamada de Elara.")])
    security = run_security_cost_loop(case, budget_config)
    trace = [{"etapa": "seguridad_costos", "estado": security["estado"]}]
    if security["estado"] != "COMPLETADO_SIMULADO":
        return _output(case, execution_mode, estado="DETENIDO", dictamen="NO_EMITIDO", traza=trace, errores=[_issue("PERMISO_O_PRESUPUESTO_INSUFICIENTE", "La ejecución no está autorizada.")], consumo={key: security[key] for key in ("consumo_api_real_usd", "costo_infraestructura_usd") } | {"costo_estimado_usd": None})

    executor = elara_executor
    if executor is None and execution_mode == "DEMO":
        executor = _DemoElaraExecutor(fecha_corte)
    if executor is None:
        return _output(case, execution_mode, estado="DETENIDO", dictamen="NO_EMITIDO", traza=trace, errores=[_issue("DEPENDENCIA_ELARA_REQUERIDA", "LIVE requiere un ejecutor de Elara inyectado por una interfaz autenticada.")])
    result: ElaraResult = executor.run(solicitud, trusted_context=_trusted_elara_context(case))
    elara = result.output
    consumo_elara = _consumption(execution_mode, result.record)
    telemetria = {"elara": _elara_telemetry(result.record, execution_mode, consumo_elara)}
    trace.append({"etapa": "elara", "estado": result.record.status})
    if not isinstance(elara, dict):
        code = "ELARA_API_ERROR" if result.record.status == "API_ERROR" else "ELARA_NO_DISPONIBLE"
        return _output(case, execution_mode, estado="RECHAZADO", dictamen="NO_EMITIDO", elara=None, traza=trace, errores=[_issue(code, "Elara no entregó una salida válida.")], telemetria=telemetria, consumo=consumo_elara)
    if elara.get("decision") != "ACEPTAR":
        state = "PENDIENTE_ACLARACION" if elara.get("decision") == "SOLICITAR_ACLARACION" else "RECHAZADO"
        return _output(case, execution_mode, estado=state, dictamen="NO_EMITIDO", elara=elara, traza=trace, errores=[_issue("ELARA_NO_ACEPTO", "Elara no autorizó el avance del caso.")], telemetria=telemetria, consumo=consumo_elara)
    if elara.get("fecha_corte_normalizada") != fecha_corte:
        return _output(case, execution_mode, estado="RECHAZADO", dictamen="NO_EMITIDO", elara=elara, traza=trace, errores=[_issue("ELARA_FECHA_INCONSISTENTE", "La fecha aceptada por Elara no coincide con el caso.")], telemetria=telemetria, consumo=consumo_elara)

    if execution_mode == "DEMO":
        siena = load_demo_siena(fecha_corte, demo_data_path)
    elif siena_provider is not None:
        siena = siena_provider(fecha_corte)
    else:
        return _output(case, execution_mode, estado="DETENIDO", dictamen="NO_EMITIDO", elara=elara, traza=trace, errores=[_issue("DEPENDENCIA_SIENA_REQUERIDA", "LIVE requiere un proveedor de Siena inyectado por una interfaz autenticada.")], telemetria=telemetria, consumo=consumo_elara)
    trace.append({"etapa": "siena", "estado": siena.get("estado") if isinstance(siena, dict) else "ERROR"})
    if not _siena_is_usable(siena, fecha_corte):
        return _output(case, execution_mode, estado="RECHAZADO", dictamen="NO_EMITIDO", elara=elara, siena=siena, traza=trace, errores=[_issue(_siena_error_code(siena), "Siena no entregó datos completos y verificables.")], telemetria=telemetria, consumo=consumo_elara, siena_consultada=True)
    try:
        curve_payload = build_excel_payload_from_siena(case, siena)
    except SienaToExcelAdapterError:
        return _output(case, execution_mode, estado="RECHAZADO", dictamen="NO_EMITIDO", elara=elara, siena=siena, traza=trace, errores=[_issue("ADAPTADOR_SIENA_RECHAZADO", "La adaptación cuantitativa fue rechazada por controles deterministas.")], telemetria=telemetria, consumo=consumo_elara, siena_consultada=True)
    trace.append({"etapa": "adaptador_siena_excel", "estado": "COMPLETADO"})
    orion = execute_orion(case, elara, siena, curve_payload, budget_config, invocation_id)
    trace.extend(orion.get("traza", []))
    return _output(
        case, execution_mode, estado=orion["estado"], dictamen=orion["dictamen_tecnico"], elara=elara,
        siena=siena, nash=orion["expediente"].get("nash"), atenea=orion["expediente"].get("atenea"),
        traza=trace, errores=orion.get("errores", []), advertencias=siena.get("advertencias", []),
        consumo=consumo_elara if execution_mode == "LIVE" else orion.get("consumo"), telemetria=telemetria,
        version_curva=orion.get("version_curva"), siena_consultada=True,
    )
