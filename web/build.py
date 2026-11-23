from __future__ import annotations
import json, shutil, sys, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from backend.case_excel import build_case_workbook
from backend.public_artifacts import validate_public_case

def adapt(public):
 return {"caso_id":public["case_id"],"version_caso":public.get("version_caso"),"version_curva":public.get("version_curva"),"fecha_corte":public.get("fecha_corte"),"execution_mode":public.get("execution_mode"),"estado":"Publicado","requiere_aprobacion_humana":False,"agentes":public.get("agentes",{}),"fuente_datos":public.get("fuente",{}),"curva":public.get("curva"),"auditoria":public.get("auditoria"),"cost_trace":public.get("costos",{}),"trazabilidad":{},"decision_humana":{}}
def build():
 src=ROOT/"data/public/cases"; dist=ROOT/"web/dist"; shutil.rmtree(dist,ignore_errors=True); (dist/"data").mkdir(parents=True,exist_ok=True); (dist/"downloads").mkdir(exist_ok=True)
 cases=[]
 for path in sorted(src.glob("*.json")):
  case=json.loads(path.read_text(encoding="utf-8")); validate_public_case(case); cases.append(case); (dist/"downloads"/f"YieldCurve_{case['case_id']}.xlsx").write_bytes(build_case_workbook(adapt(case),include_private_decision=False))
 (dist/"data/cases.json").write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding="utf-8")
 for name in ("index.html","styles.css","vizdata.css","app.js"): shutil.copy2(ROOT/"web/src"/name,dist/name)
 shutil.copytree(ROOT/"web/src/fonts",dist/"fonts",dirs_exist_ok=True)
 shutil.copy2(ROOT/"web/public_case.schema.json",dist/"data/public_case.schema.json")
 text=" ".join(p.read_text(encoding="utf-8",errors="ignore").lower() for p in dist.rglob("*") if p.is_file() and p.suffix!=".xlsx")
 from backend.public_artifacts import FORBIDDEN
 if any(x in text for x in FORBIDDEN): raise ValueError("SENSITIVE_BUILD")
 for book in (dist/"downloads").glob("*.xlsx"):
  with zipfile.ZipFile(book) as archive: excel_text=" ".join(archive.read(n).decode("utf-8",errors="ignore").lower() for n in archive.namelist() if n.endswith(".xml"))
  if any(x in excel_text for x in FORBIDDEN): raise ValueError("SENSITIVE_EXCEL")
 return dist
if __name__=="__main__": print(build())
