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
 cases=json.loads((dist/"data/cases.json").read_text(encoding="utf-8"));assert cases
 by_id={case["case_id"]:case for case in cases};case=by_id["YC-NV01R0XFRU01"]
 assert case["execution_mode"]=="DEMO" and case["publication_status"]=="PUBLISHED" and case["publication_authorized"] is True
 assert case["auditoria"]["tecnicamente_valida"] is True and case["curva"]["instrument_count"]==10 and len(case["curva"]["pillars"])==10
 for case in cases:
  validate_public_case(case);assert not any(field in json.dumps(case).lower() for field in FORBIDDEN)
  assert (dist/"downloads"/f"YieldCurve_{case['case_id']}.xlsx").exists()
 live=by_id.get("YC-TG177652682")
 assert live is None or (live["execution_mode"]=="LIVE" and live["publication_status"]=="PUBLISHED")
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
 assert "curve_points" in js and "no interpola ni recalcula" in js and "fetch('data/cases.json')" in js
 for weight in ("400","500","600","700"): assert (source/f"fonts/poppins-{weight}.ttf").exists()
 assert not any(token in (html+css+js).lower() for token in FORBIDDEN)
def test_nova_widget_embed_is_public_and_contains_no_credentials():
 html=(ROOT/"web/src/index.html").read_text(encoding="utf-8")
 for required in ("elevenlabs-convai","agent_7101m7tg0v24frcrz2prz18ya72n","https://unpkg.com/@elevenlabs/convai-widget-embed"): assert required in html
 for forbidden in ("xi-api-key","X-YieldCurve-Voice-Key","X-YieldCurve-Key","Authorization: Bearer"): assert forbidden not in html
def test_vizdata_history_filters_and_three_kpis_are_static_public_presentation():
 source=build();html=(source/"index.html").read_text(encoding="utf-8");js=(source/"app.js").read_text(encoding="utf-8");workflow=(Path(".github/workflows/pages.yml").read_text(encoding="utf-8"))
 assert 'id="kpiTitle"' in html and "Indicadores de desempeño" in html
 for identifier in ("instrument_count","max_absolute_repricing_error","known_cost_usd","costDisplay","auditBadge","historyRows","modeFilter","dateFrom","dateTo","resetFilters"): assert identifier in js or identifier in html
 assert "Auditoría técnica válida" in js and "No se encontraron casos con los filtros seleccionados." in js and "Restablecer filtros" in html
 assert "filteredCases" in js and "renderHistory" in js and "selectCase" in js
 assert "enablement:" not in workflow and "actions/configure-pages@v5" in workflow and "web/generate_demo.py" not in workflow

def test_cost_and_kpi_presentation_uses_published_semantics_and_human_labels():
 source=build();js=(source/"app.js").read_text(encoding="utf-8");html=(source/"index.html").read_text(encoding="utf-8")
 assert "known_cost_usd" in js and "Pricing parcial" in js and "No tarifado" in js and "No aplica" in js
 assert "tolerancia:'Tolerancia'" in js and "requiere_aprobacion_humana:'Aprobación humana requerida'" in js and "value===true?'Sí'" in js
 assert "mape_repricing_pct" in js and "Evidencia insuficiente" in js
 assert "kpi__info" in js and "aria-expanded" in js and "type=\"button\"" in js

def test_interactive_curve_uses_all_published_pillars_and_human_utc_dates():
 source=build();js=(source/"app.js").read_text(encoding="utf-8");html=(source/"index.html").read_text(encoding="utf-8");css=(source/"curve.css").read_text(encoding="utf-8")
 cases=json.loads((source/"data/cases.json").read_text(encoding="utf-8"));pillars=cases[0]["curva"]["pillars"]
 assert len(pillars)==10 and all("instrument_id" in pillar for pillar in pillars)
 assert ".sort((a,b)=>a.days-b.days)" in js and ".join(' ')" in js
 assert "const published=c.curva?.curve_points?.length?c.curva.curve_points" in js
 assert "data-point-index" in js and "data-case-index" in js and "mouseenter" in js and "keydown" in js and "pillarDetail" in js
 assert "formatDate" in js and "timeZone:'UTC'" in js and "${formatDate(c.published_at)}" in js
 assert "aria-live=\"polite\"" in html and "La visualización usa exclusivamente puntos publicados; no interpola ni recalcula las tasas." in html
 assert ".chart-point:focus-visible" in css and not any(token in (html+js+css).lower() for token in FORBIDDEN)

def test_clean_restore_adds_only_published_curve_extensions_and_cache_busting():
 source=build();html=(source/'index.html').read_text(encoding='utf-8');js=(source/'app.js').read_text(encoding='utf-8');curve=(source/'curve.css').read_text(encoding='utf-8');cases=json.loads((source/'data/cases.json').read_text(encoding='utf-8'))
 assert 'app.js?v=' in html and 'styles.css?v=' in html and 'curve.css?v=' in html
 for token in ('decision-supported','decision-supported__lead','decision-supported__flow','Cómo leer este dashboard','Cómo funciona YieldCurve AI','elevenlabs-convai'): assert token in html
 for token in ('curve_points?.length','pillars||[]','left_pillar','right_pillar','lectura_curva','sort((a,b)=>String(b.published_at)','technical_valid_curves_pct','technical_processing_minutes'): assert token in js
 assert 'fill="none"' in js and '.chart-line{fill:none;stroke:var(--coral)}' in curve
 assert cases and all((source/'downloads'/f"YieldCurve_{case['case_id']}.xlsx").exists() for case in cases)
 assert next(case for case in cases if case['case_id']=='YC-TG177652684')['published_at']=='2026-11-26T07:04:14.893074+00:00'

def test_kpis_have_spacious_accessible_explanations_for_interpretation():
 source=build();js=(source/'app.js').read_text(encoding='utf-8');css=(source/'styles.css').read_text(encoding='utf-8')
 assert 'Un valor menor indica mayor consistencia de repricing' in js
 assert 'aria-expanded' in js and 'aria-controls' in js and 'kpi__popover' in js
 assert 'closeKpiPopovers' in js and "event.key==='Escape'" in js
 assert 'position:absolute' in css and '.kpi{overflow:visible}' in css
 assert 'min-height:148px' in css and 'max-width:calc(100% - 38px)' in css

def test_final_polish_keeps_nova_contextual_and_preserves_published_curve_logic():
 source=build();html=(source/'index.html').read_text(encoding='utf-8');js=(source/'app.js').read_text(encoding='utf-8');css=(source/'styles.css').read_text(encoding='utf-8')
 assert "['elara','siena','nash','atenea','orion']" in js and "'nova'" not in js[js.index("get('agents').innerHTML"):js.index("const facts=")]
 assert 'Nova · asistente de voz' in html and 'Consulta la evidencia pública de este caso mediante voz.' in html and 'elevenlabs-convai' in html
 assert '.dashboard-grid--primary,.dashboard-grid--secondary{align-items:stretch}' in css and '.panel--agents,.panel--audit{display:flex;flex-direction:column}' in css and '.nova-context{margin-top:auto' in css
 assert 'useCriterion' in html and 'Datos de mercado validados' in js and 'curve.max_absolute_repricing_error<=audit.tolerancia' in js
 assert 'Bootstrap 182 días · V1' in js and 'Banxico SIE · Datos en vivo' in js and 'Snapshot DEMO 11/11/2026' in js
 assert "const published=c.curva?.curve_points?.length?c.curva.curve_points" in js and 'fill="none"' in js
