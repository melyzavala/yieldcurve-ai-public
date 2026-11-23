import copy,json
from pathlib import Path
from jsonschema import Draft202012Validator
from backend.atenea_executor import execute_atenea
from backend.nash_executor import execute_nash
ROOT=Path(__file__).resolve().parents[1]
def payload(): return json.loads((ROOT/'skills/build_spot_curve/examples/caso_valido.json').read_text())
def case(p): return {"contrato_version":"1.0.0","caso_id":p["case_id"],"version_caso":1,"version_curva":p["curve_version"],"fecha_corte":p["valuation_date"],"canal_origen":"manual","modo":"SIMULADO","estado":"EN_CALCULO","objetivo":"Curva ficticia.","agente_responsable":"Nash","referencias":{"datos":[],"calculos":[],"validaciones":[]},"advertencias":[],"errores":[],"marcas_tiempo":{"creado_en":"2026-04-14T00:00:00Z","actualizado_en":"2026-04-14T00:00:00Z"},"trazabilidad":{"correlation_id":"C","traza_id":"T","referencias_consumo":[]},"salidas_especializadas":{}}
def test_schema_examples():
 s=json.loads((ROOT/'agents/contracts/atenea.output.schema.json').read_text()); Draft202012Validator.check_schema(s); [Draft202012Validator(s).validate(x['salida_esperada']) for x in json.loads((ROOT/'agents/examples/atenea/cases.json').read_text())]
def test_valid_curve():
 p=payload(); c=case(p); n=execute_nash(c,p,'n1'); assert execute_atenea(c,n,p,'a1')['estado']=='DICTAMEN_TECNICO_VALIDADO'
def test_altered_price_and_inconsistent_date_rejected():
 p=payload(); c=case(p); n=execute_nash(c,p,'n2'); n['resultado_curva']['pillars'][-1]['discount_factor']*=.9; assert execute_atenea(c,n,p,'a2')['estado']=='DICTAMEN_TECNICO_RECHAZADO'; bad=copy.deepcopy(c); bad['fecha_corte']='2026-04-15'; assert execute_atenea(bad,n,p,'a3')['estado']=='DICTAMEN_TECNICO_RECHAZADO'
def test_incomplete_or_inconsistent_repricing_rejected():
 p=payload(); c=case(p); n=execute_nash(c,p,'n3'); n['resultado_curva']['repricing'][0]['dirty_price_theoretical']+=1; assert execute_atenea(c,n,p,'a4')['estado']=='DICTAMEN_TECNICO_RECHAZADO'
