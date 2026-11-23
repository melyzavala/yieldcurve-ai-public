from __future__ import annotations
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.yieldcurve_pipeline import run_yieldcurve_case
from backend.api import sanitize_pipeline_result
from backend.public_artifacts import build_public_case_artifact
def generate():
 result=run_yieldcurve_case(caso_id="YC-PUBLICDEMO01",version_caso=1,version_curva="CURVA-PUBLIC-DEMO-01",fecha_corte="2026-11-11",canal_origen="web",solicitud="Construye una curva CETES y M-Bonos para 2026-11-11 para un portafolio ficticio.",budget_config={"budget_usd":0.0,"time_limit_seconds":30.0,"authorization_scope":"ORCHESTRATION_SIMULATED","execution_authorized":True,"authorization_source":"TRUSTED_LOCAL_CONFIG","max_llm_calls":1},invocation_id="public-demo-build",execution_mode="DEMO")
 public=build_public_case_artifact(sanitize_pipeline_result(result,"public-demo-build")["case_artifact"],"2026-11-19T00:00:00+00:00")
 target=ROOT/"data/public/cases/YC-PUBLICDEMO01.json";target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(public,ensure_ascii=False,indent=2),encoding="utf-8");return target
if __name__=="__main__":print(generate())
