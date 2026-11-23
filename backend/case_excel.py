"""In-memory Excel evidence built only from a sanitized case artifact."""
from __future__ import annotations
from io import BytesIO
from copy import deepcopy
from typing import Any
from openpyxl import Workbook
from openpyxl.chart import LineChart, Reference
from openpyxl.styles import Font, PatternFill

FORBIDDEN = ("telegram_user_id", "telegram_chat_id", "api_key", "x-yieldcurve-key", "prompt", "access_code", "authorization", "credential", "stack trace")
HEAD = PatternFill("solid", fgColor="17365D")

def _safe(value: Any) -> Any:
    return "N/D" if value is None else value

def validate_case_artifact(artifact: dict[str, Any]) -> None:
    if not isinstance(artifact, dict) or not artifact.get("caso_id") or not isinstance(artifact.get("curva"), (dict, type(None))):
        raise ValueError("CASE_ARTIFACT_INVALIDO")
    if any(token in str(artifact).lower() for token in FORBIDDEN):
        raise ValueError("CASE_ARTIFACT_SENSIBLE")

def _title(ws: Any, title: str) -> None:
    ws["A1"] = title; ws["A1"].font = Font(bold=True, color="FFFFFF", size=14); ws["A1"].fill = HEAD
    ws.freeze_panes = "A3"

def _table(ws: Any, headers: list[str], rows: list[list[Any]], start: int = 3) -> None:
    for col, value in enumerate(headers, 1):
        cell=ws.cell(start,col,value); cell.font=Font(bold=True,color="FFFFFF"); cell.fill=HEAD
    for row in rows:
        ws.append([_safe(value) for value in row])
    ws.auto_filter.ref = f"A{start}:{chr(64+len(headers))}{start+len(rows)}"
    for column in ws.columns: ws.column_dimensions[column[0].column_letter].width = min(max(14, max(len(str(c.value or '')) for c in column)+2), 42)

def build_case_workbook(case_artifact: dict[str, Any], *, include_private_decision: bool = True) -> bytes:
    validate_case_artifact(case_artifact); a=deepcopy(case_artifact); wb=Workbook(); wb.properties.creator="YieldCurve AI"
    summary=wb.active; summary.title="Resumen"; _title(summary,"Expediente YieldCurve AI")
    decision=a.get("decision_humana",{}); curve=a.get("curva") or {}; audit=a.get("auditoria") or {}
    summary_fields=[("caso_id",a.get("caso_id")),("version_caso",a.get("version_caso")),("version_curva",a.get("version_curva")),("fecha_corte",a.get("fecha_corte")),("execution_mode",a.get("execution_mode")),("estado",a.get("estado")),("source_mode",a.get("fuente_datos",{}).get("source_mode")),("metodología",curve.get("metodologia")),("instrument_count",curve.get("instrument_count")),("max_absolute_repricing_error",curve.get("max_absolute_repricing_error")),("auditoría técnicamente válida",audit.get("tecnicamente_valida")),("Resultado técnico",a.get("estado"))]
    if include_private_decision:
        summary_fields.extend([("invocation_id",a.get("trazabilidad",{}).get("invocation_id")),("Decisión humana",decision.get("approval_status") or "Pendiente / No disponible"),("decision_at",decision.get("decision_at") or "Pendiente / No disponible")])
    _table(summary,["Campo","Valor"],[[k,_safe(v)] for k,v in summary_fields])
    ws=wb.create_sheet("Curva_Spot"); _title(ws,"Curva spot"); pillars=curve.get("pillars",[]); fields=sorted({key for p in pillars for key in p}); _table(ws,fields,[[p.get(f) for f in fields] for p in pillars]);
    if pillars and "spot_rate" in fields:
        x=fields.index("days")+1 if "days" in fields else 1; y=fields.index("spot_rate")+1; chart=LineChart(); chart.title=f"Curva spot · {a.get('fecha_corte')} · {a.get('execution_mode')}"; chart.y_axis.title="Tasa spot (%)"; chart.x_axis.title="Plazo"; chart.add_data(Reference(ws,min_col=y,min_row=3,max_row=3+len(pillars)),titles_from_data=True); chart.set_categories(Reference(ws,min_col=x,min_row=4,max_row=3+len(pillars))); ws.add_chart(chart,"J3")
    agents=wb.create_sheet("Agentes"); _title(agents,"Agentes"); _table(agents,["Agente","Estado","Decisión/dictamen"],[[name,(data or {}).get("estado"),(data or {}).get("decision") or (data or {}).get("dictamen")] for name,data in a.get("agentes",{}).items()])
    au=wb.create_sheet("Auditoria"); _title(au,"Auditoría"); _table(au,["Campo","Valor"],[["tecnicamente_valida",audit.get("tecnicamente_valida")],["metodología",curve.get("metodologia")],["instrument_count",curve.get("instrument_count")],["max_absolute_repricing_error",curve.get("max_absolute_repricing_error")],["source_mode",a.get("fuente_datos",{}).get("source_mode")]])
    co=wb.create_sheet("Costos"); _title(co,"Costo variable medido/estimado"); trace=a.get("cost_trace",{}); columns=["component","type","provider","model","api_calls","input_tokens","output_tokens","total_tokens","request_count","estimated_cost_usd","pricing_status","pricing_version","pricing_effective_date"]; _table(co,columns,[[c.get(x) for x in columns] for c in trace.get("components",[])]); co.append([]); co.append(["Costos fijos de plataforma","Render/n8n/hosting se administran por separado"]); co.append(["total_variable_cost_usd",_safe(trace.get("total_variable_cost_usd"))])
    trace_rows=[["caso_id",a.get("caso_id")],["version_caso",a.get("version_caso")],["version_curva",a.get("version_curva")],["fecha_corte",a.get("fecha_corte")],["execution_mode",a.get("execution_mode")],["source_mode",a.get("fuente_datos",{}).get("source_mode")],["estado",a.get("estado")]]
    if include_private_decision:
        trace_rows.extend([["invocation_id",a.get("trazabilidad",{}).get("invocation_id")],["approval_status",decision.get("approval_status")],["decision_at",decision.get("decision_at")]])
    tr=wb.create_sheet("Trazabilidad"); _title(tr,"Trazabilidad"); _table(tr,["Campo","Valor"],trace_rows); tr.append([]); tr.append(["Nota","Este expediente se genera desde el case_artifact sanitizado. No recalcula la curva ni modifica el resultado técnico."])
    out=BytesIO(); wb.save(out); return out.getvalue()
