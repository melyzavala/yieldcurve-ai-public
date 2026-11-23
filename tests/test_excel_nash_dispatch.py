from backend.excel_bootstrap import build_from_payload
from tests.fixtures_excel_bootstrap import PAYLOAD,BENCHMARK
from backend.nash_executor import execute_nash
from test_nash import case_for
def test_excel_fixture_matches_benchmark_without_scipy():
 r=build_from_payload(PAYLOAD); rates=[x['spot_rate'] for x in r['pillars'][-5:]]
 assert all(abs(a-b)<=1e-6 for a,b in zip(rates,BENCHMARK))
 assert r['metodologia']=='EXCEL_BOOTSTRAP_182D_V1'

def test_nash_end_to_end_excel_dispatch():
 p=dict(PAYLOAD); p['case_id']=p.pop('case_id'); p['curve_version']=p.pop('curve_version')
 output=execute_nash(case_for(p),p,'excel-nash-001')
 assert output['estado']=='CALCULO_COMPLETADO'
 assert output['resultado_curva']['metodologia']=='EXCEL_BOOTSTRAP_182D_V1'
