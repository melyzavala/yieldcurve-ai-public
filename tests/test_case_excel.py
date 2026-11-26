from io import BytesIO
from openpyxl import load_workbook
from fastapi.testclient import TestClient
import backend.api as api
from backend.case_excel import build_case_workbook

ARTIFACT={"caso_id":"YC-EXCEL123","version_caso":1,"version_curva":"CURVA-EXCEL123","fecha_corte":"2026-11-11","execution_mode":"DEMO","estado":"PENDIENTE_APROBACION","requiere_aprobacion_humana":True,"agentes":{"elara":{"estado":"VALID"},"nash":{"estado":"CALCULO_COMPLETADO"}},"fuente_datos":{"source_mode":"FIXTURE"},"curva":{"metodologia":"TEST","instrument_count":2,"max_absolute_repricing_error":1e-8,"pillars":[{"instrument_id":"C28","days":28,"spot_rate":.08},{"instrument_id":"C91","days":91,"spot_rate":.09}]},"auditoria":{"tecnicamente_valida":True},"cost_trace":{"components":[{"component":"ELARA","type":"LLM","provider":"OpenAI","model":"gpt-6-luna","api_calls":1,"input_tokens":10,"output_tokens":5,"total_tokens":15,"estimated_cost_usd":None,"pricing_status":"NOT_AVAILABLE"}],"total_variable_cost_usd":None},"trazabilidad":{"invocation_id":"inv-1"},"decision_humana":{"approval_status":None,"decision_at":None}}
def test_workbook_copies_pillars_and_chart_without_calculation():
    wb=load_workbook(BytesIO(build_case_workbook(ARTIFACT))); assert wb.sheetnames==["Resumen","Curva_Spot","Curva completa","Agentes","Auditoria","Costos","Trazabilidad"]; ws=wb["Curva_Spot"]; headers=[c.value for c in ws[3]]; assert ws.max_row==5 and ws.cell(4,headers.index("instrument_id")+1).value=="C28" and len(ws._charts)==1; assert "N/D" in [c.value for row in wb["Costos"].iter_rows() for c in row]
def test_excel_endpoint_auth_and_content(monkeypatch):
 monkeypatch.setenv("YIELDCURVE_API_KEY","key"); c=TestClient(api.app); assert c.post("/v1/artifacts/excel",json=ARTIFACT).status_code==401; r=c.post("/v1/artifacts/excel",json=ARTIFACT,headers={"X-YieldCurve-Key":"key"}); assert r.status_code==200 and r.headers["content-type"].startswith("application/vnd.openxmlformats") and "YieldCurve_YC-EXCEL123_2026-11-11.xlsx" in r.headers["content-disposition"]
def test_sensitive_input_is_rejected():
 bad={**ARTIFACT,"telegram_user_id":"secret"};
 try: build_case_workbook(bad); assert False
 except ValueError: assert True
