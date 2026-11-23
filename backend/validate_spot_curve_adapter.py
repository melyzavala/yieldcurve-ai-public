"""Adaptador con traza para la skill validate-spot-curve."""
from __future__ import annotations
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from backend.spot_curve_validator import CurveValidationError, validate_spot_curve
ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "skills" / "validate_spot_curve" / "SKILL.md"


def _skill_version(text: str) -> str:
    match = re.search(r"^version:\s*([^\s]+)\s*$", text, re.MULTILINE)
    if not match:
        raise ValueError("SKILL_VERSION_FALTANTE")
    return match.group(1)

def apply_validate_spot_curve(payload: dict[str, Any], curve: dict[str, Any], invocation_id: str) -> dict[str, Any]:
    text = PATH.read_text(encoding="utf-8")
    trace = {"invocation_id": invocation_id, "skill_name": "validate-spot-curve", "skill_path": "skills/validate_spot_curve/SKILL.md", "skill_version": _skill_version(text), "skill_sha256": hashlib.sha256(text.encode()).hexdigest(), "started_at": datetime.now(timezone.utc).isoformat()}
    try:
        result = validate_spot_curve(payload, curve)
    except CurveValidationError as error:
        trace["status"] = "REJECTED"; trace["skill_status"] = "REJECTED"; trace["error_code"] = str(error)
        return {"status": "REJECTED", "trace": trace}
    trace["status"] = "COMPLETED"; trace["skill_status"] = "COMPLETED"
    return {"status": "COMPLETED", "trace": trace, "result": result}
