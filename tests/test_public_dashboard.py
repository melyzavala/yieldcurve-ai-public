import json,zipfile
from io import BytesIO
import pytest
from pathlib import Path
from jsonschema import Draft202012Validator
from backend.public_artifacts import build_public_case_artifact,validate_public_case,FORBIDDEN
from backend.case_excel import build_case_workbook
from web.build import adapt,build

ROOT=Path(__file__).resolve().parents[1]

def approved_demo():
 return {"caso_id":"YC-SYNTHETIC-DEMO","version_caso":1,"version_curva":"CURVA-SYNTHETIC-DEMO-V1","fecha_corte":"2026-11-11","execution_mode":"DEMO","estado":"APROBADA_HUMANAMENTE","agentes":{},"fuente_datos":{"source_mode":"FIXTURE"},"curva":{"metodologia":"TEST","instrument_count":1,"max_absolute_repricing_error":0.0,"pillars":[{"days":28,"spot_rate":.08}]},"auditoria":{"tecnicamente_valida":True},"cost_trace":{}}

def test_public_projection_requires_approved_demo_with_valid_audit_and_copies_pillars():
 source=approved_demo();public=build_public_case_artifact(source,"2026-01-01T00:00:00Z")
 assert public["execution_mode"]=="DEMO" and public["publication_authorized"] is True
 assert public["curva"]["pillars"]==source["curva"]["pillars"] and public["curva"]["pillars"] is not source["curva"]["pillars"]
 validate_public_case(public)
 for field,value in (("execution_mode","LIVE"),("estado","PENDIENTE_APROBACION")):
  rejected=approved_demo();rejected[field]=value
  with pytest.raises(ValueError,match="PUBLIC_CASE_NOT_AUTHORIZED"): build_public_case_artifact(rejected,"2026-01-01T00:00:00Z")
 rejected=approved_demo();rejected["auditoria"]={"tecnicamente_valida":False}
 with pytest.raises(ValueError,match="PUBLIC_CASE_NOT_AUTHORIZED"): build_public_case_artifact(rejected,"2026-01-01T00:00:00Z")

def test_public_schema_and_validation_fail_closed_for_live_unapproved_or_sensitive_data():
 public=build_public_case_artifact(approved_demo(),"2026-01-01T00:00:00Z");schema=json.loads((ROOT/"web/public_case.schema.json").read_text(encoding="utf-8"))
 assert not list(Draft202012Validator(schema).iter_errors(public))
 for key,value in (("execution_mode","LIVE"),("publication_authorized",False),("approval_status","APPROVED")):
  invalid=dict(public);invalid[key]=value;assert list(Draft202012Validator(schema).iter_errors(invalid))
 sensitive=dict(public);sensitive["invocation_id"]="private"
 with pytest.raises(ValueError,match="PUBLIC_CASE_SCHEMA"): validate_public_case(sensitive)
 assert not any(token in json.dumps(public).lower() for token in FORBIDDEN)

def test_public_build_uses_existing_authorized_artifacts_only_and_public_excel_is_sanitized():
 workflow=(ROOT/".github/workflows/pages.yml").read_text(encoding="utf-8")
 assert "web/generate_demo.py" not in workflow and "python web/build.py" in workflow and "{path: web/dist}" in workflow
 dist=build();assert (dist/"index.html").exists() and (dist/"data/cases.json").exists()
 cases=json.loads((dist/"data/cases.json").read_text(encoding="utf-8"));assert len(cases)==1
 case=cases[0];validate_public_case(case)
 assert case["case_id"]=="YC-NV01R0XFRU01" and case["execution_mode"]=="DEMO" and case["publication_status"]=="PUBLISHED" and case["publication_authorized"] is True
 assert case["auditoria"]["tecnicamente_valida"] is True and case["curva"]["instrument_count"]==10 and len(case["curva"]["pillars"])==10
 assert not any(field in json.dumps(case).lower() for field in FORBIDDEN)
 assert (dist/"downloads"/"YieldCurve_YC-NV01R0XFRU01.xlsx").exists()
 book=build_case_workbook(adapt(build_public_case_artifact(approved_demo(),"2026-01-01T00:00:00Z")),include_private_decision=False)
 with zipfile.ZipFile(BytesIO(book)) as z: text=" ".join(z.read(n).decode("utf-8","ignore").lower() for n in z.namelist() if n.endswith(".xml"));assert not any(x in text for x in FORBIDDEN)

def test_public_build_fails_closed_for_invalid_source():
 invalid=ROOT/"data/public/cases/_invalid_public_case.json";invalid.write_text(json.dumps({"execution_mode":"LIVE"}),encoding="utf-8")
 try:
  with pytest.raises(ValueError): build()
 finally:
  invalid.unlink(missing_ok=True)
def test_dashboard_visual_structure_is_present_and_static():
 source=build();html=(source/"index.html").read_text(encoding="utf-8");css=(source/"styles.css").read_text(encoding="utf-8");js=(source/"app.js").read_text(encoding="utf-8")
 for required in ("@font-face","Poppins,Arial,sans-serif","context-bar","kpi-grid","dashboard-grid--primary","agent-list","fact-list","cost-summary","@media(max-width:540px)"): assert required in css or required in html
 for required in ("caseSelect","kpis","chart","agents","audit","costs","download"): assert f'id=\"{required}\"' in html
 assert "curva?.pillars" in js and "sin interpolación" in js and "fetch('data/cases.json')" in js
 for weight in ("400","500","600","700"): assert (source/f"fonts/poppins-{weight}.ttf").exists()
 assert not any(token in (html+css+js).lower() for token in FORBIDDEN)
def test_nova_widget_embed_is_public_and_contains_no_credentials():
 html=(ROOT/"web/src/index.html").read_text(encoding="utf-8")
 for required in ("elevenlabs-convai","agent_7101m7tg0v24frcrz2prz18ya72n","https://unpkg.com/@elevenlabs/convai-widget-embed"): assert required in html
 for forbidden in ("xi-api-key","X-YieldCurve-Voice-Key","X-YieldCurve-Key","Authorization: Bearer"): assert forbidden not in html
def test_vizdata_history_filters_and_three_kpis_are_static_public_presentation():
 source=build();html=(source/"index.html").read_text(encoding="utf-8");js=(source/"app.js").read_text(encoding="utf-8");workflow=(Path(".github/workflows/pages.yml").read_text(encoding="utf-8"))
 assert html.count('class="kpi"')==3
 for identifier in ("instrument_count","max_absolute_repricing_error","total_variable_cost_usd","auditBadge","historyRows","modeFilter","dateFrom","dateTo","resetFilters"): assert identifier in js or identifier in html
 assert "Auditoría técnica válida" in js and "No se encontraron casos con los filtros seleccionados." in js and "Restablecer filtros" in html
 assert "filteredCases" in js and "renderHistory" in js and "selectCase" in js
 assert "enablement:" not in workflow and "actions/configure-pages@v5" in workflow and "web/generate_demo.py" not in workflow

def test_interactive_curve_uses_all_published_pillars_and_human_utc_dates():
 source=build();js=(source/"app.js").read_text(encoding="utf-8");html=(source/"index.html").read_text(encoding="utf-8");css=(source/"curve.css").read_text(encoding="utf-8")
 cases=json.loads((source/"data/cases.json").read_text(encoding="utf-8"));pillars=cases[0]["curva"]["pillars"]
 assert len(pillars)==10 and all("instrument_id" in pillar for pillar in pillars)
 assert ".sort((a,b)=>a.days-b.days)" in js and ".join(' ')" in js
 assert "points=p.map(v=>`${sx(v.days)},${sy(v.spot_rate*100)}`).join(' ')" in js
 assert "data-pillar" in js and "mouseenter" in js and "keydown" in js and "pillarDetail" in js
 assert "formatDate" in js and "timeZone:'UTC'" in js and "${formatDate(c.published_at)}" in js
 assert "aria-live=\"polite\"" in html and "Pilares publicados; la visualización no interpola ni recalcula las tasas." in html
 assert ".chart-point:focus-visible" in css and not any(token in (html+js+css).lower() for token in FORBIDDEN)
