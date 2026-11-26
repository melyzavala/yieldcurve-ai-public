import json
from pathlib import Path
from web.build import build

ROOT=Path(__file__).resolve().parents[1]

def test_dashboard_uses_published_data_with_historical_fallback_and_accessibility_hooks():
 d=build(); html=(d/'index.html').read_text(encoding='utf-8'); js=(d/'app.js').read_text(encoding='utf-8'); css=(d/'styles.css').read_text(encoding='utf-8')
 for token in ('hero','context','kpis','chart','agents','audit','costs','historyRows','Indicadores de desempeño','Cómo leer este dashboard','elevenlabs-convai','download'): assert token in html
 for token in ('published_at','localeCompare','data-point-index','data-case-index','chart-line','curve_points?.length','pillars||[]','indicadores||{}','known_cost_usd','lectura_curva','modeFilter','dateFrom','dateTo','No fue posible cargar','downloads/YieldCurve_'): assert token in js
 assert 'prefers-reduced-motion:reduce' in css and '.hero-art' in css and '@media(max-width:540px)' in css

def test_built_dashboard_uses_cache_busted_assets_and_only_published_curve_evidence():
 d=build(); html=(d/'index.html').read_text(encoding='utf-8'); cases=json.loads((d/'data/cases.json').read_text(encoding='utf-8'))
 assert 'app.js?v=' in html and 'styles.css?v=' in html and 'curve.css?v=' in html
 assert cases and all('curve_points' not in (case.get('curva') or {}) for case in cases)
 assert all((d/'downloads'/f"YieldCurve_{case['case_id']}.xlsx").exists() for case in cases)

def test_latest_case_sort_is_independent_of_filename_order():
 cases=json.loads((build()/'data/cases.json').read_text(encoding='utf-8'))
 ordered=sorted(cases,key=lambda c:(str(c.get('published_at')),str(c.get('case_id'))),reverse=True)
 assert ordered[0]['case_id']=='YC-TG177652684'

def test_historical_cases_are_not_reconstructed():
 cases=json.loads((build()/'data/cases.json').read_text(encoding='utf-8'))
 live=next(c for c in cases if c['case_id']=='YC-TG177652684')
 assert 'curve_points' not in live['curva'] and 'lectura_curva' not in (live.get('auditoria') or {})
