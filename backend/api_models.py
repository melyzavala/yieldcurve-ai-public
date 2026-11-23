"""Contratos HTTP mínimos para la capa de transporte de Orion."""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExecutionMode(str, Enum):
    DEMO = "DEMO"
    LIVE = "LIVE"


class OriginChannel(str, Enum):
    telegram = "telegram"
    nova = "nova"
    web = "web"
    api = "api"
    manual = "manual"


class OrionRunRequest(BaseModel):
    """Datos de negocio admitidos; no expone controles internos del pipeline."""

    model_config = ConfigDict(extra="forbid")

    caso_id: str = Field(pattern=r"^YC-[A-Z0-9]{8,32}$")
    version_caso: int = Field(ge=1)
    version_curva: str = Field(pattern=r"^CURVA-[A-Z0-9-]{4,64}$")
    fecha_corte: date
    canal_origen: OriginChannel
    solicitud: str = Field(min_length=1, max_length=4_000)
    execution_mode: ExecutionMode
    invocation_id: str = Field(min_length=1, max_length=128)


class OrionRunResponse(BaseModel):
    """Respuesta externa sanitizada; nunca contiene prompts, headers o secretos."""

    model_config = ConfigDict(extra="forbid")

    caso_id: str
    version_caso: int
    version_curva: str | None
    fecha_corte: str
    modo: str
    execution_mode: str
    estado: str
    dictamen_tecnico: str
    requiere_aprobacion_humana: bool
    resultado_curva: dict[str, Any] | None
    auditoria: dict[str, Any] | None
    agentes: dict[str, dict[str, Any] | None]
    fuente_datos: dict[str, Any]
    traza: list[dict[str, Any]]
    advertencias: list[dict[str, Any]]
    errores: list[dict[str, Any]]
    consumo: dict[str, Any]
    telemetria: dict[str, Any]
    cost_trace: dict[str, Any]
    case_artifact: dict[str, Any]
