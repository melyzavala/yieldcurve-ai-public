from backend.security_cost_loop import run_security_cost_loop


def case(ident="YC-SECURITY20260414", approval="RECHAZADO"):
    return {"caso_id": ident, "modo": "SIMULADO", "aprobacion_humana": {"estado": approval}}


def test_rejected_and_pending_authorizations_remain_blocked():
    for approval in ("RECHAZADO", "PENDIENTE"):
        result = run_security_cost_loop(case(approval=approval), {"budget_usd": 0.0})
        assert result["estado"] == "BLOQUEADO_SEGURIDAD_O_PRESUPUESTO"
        assert result["traza"][0]["autorizada"] is False


def test_v2_is_explicitly_authorized_with_the_same_case_id():
    v1 = run_security_cost_loop(case(), {"budget_usd": 0.0})
    v2 = run_security_cost_loop(case(approval="APROBADO"), {"budget_usd": 0.0})
    assert v1["estado"] == "BLOQUEADO_SEGURIDAD_O_PRESUPUESTO"
    assert v2["estado"] == "COMPLETADO_SIMULADO"
    assert v1["traza"][0]["caso_id"] == v2["traza"][0]["caso_id"]
    assert v2["consumo_api_real_usd"] == 0.0


def test_negative_budget_malformed_input_and_disallowed_action_are_rejected():
    assert run_security_cost_loop(case(approval="APROBADO"), {"budget_usd": -0.01})["estado"] == "RECHAZADO_ENTRADA"
    assert run_security_cost_loop(None, {"budget_usd": 0.0})["estado"] == "RECHAZADO_ENTRADA"
    assert run_security_cost_loop(case(approval="APROBADO"), {"budget_usd": 0.0}, "EXPORT_PRIVATE_DATA")["estado"] == "BLOQUEADO_SEGURIDAD_O_PRESUPUESTO"


def test_scoped_technical_authorization_does_not_change_human_approval():
    pending = case(approval="PENDIENTE")
    result = run_security_cost_loop(pending, {"budget_usd": 0.0, "authorization_scope": "ORCHESTRATION_SIMULATED", "execution_authorized": True, "authorization_source": "TRUSTED_LOCAL_CONFIG"})
    assert result["estado"] == "COMPLETADO_SIMULADO"
    assert pending["aprobacion_humana"]["estado"] == "PENDIENTE"


def test_non_finite_budget_time_and_untrusted_technical_authorization_are_rejected():
    valid = {"budget_usd": 0.0, "time_limit_seconds": 30.0, "authorization_scope": "ORCHESTRATION_SIMULATED", "execution_authorized": True}
    assert run_security_cost_loop(case(approval="PENDIENTE"), {**valid, "budget_usd": float("inf")})["estado"] == "RECHAZADO_ENTRADA"
    assert run_security_cost_loop(case(approval="PENDIENTE"), {**valid, "time_limit_seconds": float("nan")})["estado"] == "RECHAZADO_ENTRADA"
    assert run_security_cost_loop(case(approval="PENDIENTE"), valid)["estado"] == "BLOQUEADO_SEGURIDAD_O_PRESUPUESTO"
