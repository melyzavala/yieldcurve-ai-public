import json
from pathlib import Path
from backend.curve_quality_loop import run_curve_quality_loop
from test_atenea import case
ROOT=Path(__file__).resolve().parents[1]
def load(name): return json.loads((ROOT/'skills/build_spot_curve/examples'/name).read_text())
def test_v1_rejected_v2_corrected_same_case():
 p=load('caso_valido.json'); r=run_curve_quality_loop(case(p),p,'loop-1'); assert r['estado']=='VALIDADA'; assert len(r['iterations'])==2; assert r['iterations'][0]['atenea']=='DICTAMEN_TECNICO_RECHAZADO'; assert r['iterations'][1]['atenea']=='DICTAMEN_TECNICO_VALIDADO'; assert r['iterations'][0]['caso_id']==r['iterations'][1]['caso_id']; assert r['costo_adicional_usd']==0.0
def test_second_case_reuse():
 p=load('caso_reutilizacion.json'); r=run_curve_quality_loop(case(p),p,'loop-2'); assert r['estado']=='VALIDADA'; assert len(r['iterations'])==2

def test_nash_rejection_is_sanitized_without_running_atenea():
    p=load('caso_invalido_metadatos.json'); r=run_curve_quality_loop(case(p),p,'loop-rejected')
    assert r['estado']=='RECHAZADA_NASH'; assert r['iterations'][0]['atenea']=='NO_EJECUTADA'
