"""Adaptador auditable para cargar y aplicar la skill build-spot-curve."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.spot_curve import SpotCurveValidationError, build_spot_curve
from backend.excel_bootstrap import ExcelBootstrapError, METHODOLOGY, build_from_payload


ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = ROOT / "skills" / "build_spot_curve" / "SKILL.md"


def _skill_version(text: str) -> str:
    match = re.search(r"^version:\s*([^\s]+)\s*$", text, re.MULTILINE)
    if not match:
        raise ValueError("SKILL_VERSION_FALTANTE")
    return match.group(1)


def apply_build_spot_curve(payload: dict[str, Any], invocation_id: str) -> dict[str, Any]:
    """Carga el documento de la skill, aplica el motor y devuelve una traza sanitizada."""
    if not isinstance(invocation_id, str) or not invocation_id.strip():
        raise ValueError("invocation_id es obligatorio.")
    skill_text = SKILL_PATH.read_text(encoding="utf-8")
    trace = {
        "invocation_id": invocation_id,
        "skill_name": "build-spot-curve",
        "skill_path": "skills/build_spot_curve/SKILL.md",
        "skill_version": _skill_version(skill_text),
        "skill_sha256": hashlib.sha256(skill_text.encode("utf-8")).hexdigest(),
        "mode": payload.get("mode") if isinstance(payload, dict) else None,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        result = build_from_payload(payload) if payload.get("metodologia") == METHODOLOGY else build_spot_curve(payload)
    except (SpotCurveValidationError, ExcelBootstrapError) as error:
        trace.update(skill_status="REJECTED", status="REJECTED", error_code=str(error).split(":", 1)[0])
        return {"status": "REJECTED", "trace": trace, "error": str(error)}
    trace.update(skill_status="COMPLETED", status="COMPLETED", instrument_count=result["summary"]["instrument_count"])
    return {"status": "COMPLETED", "trace": trace, "result": result}
