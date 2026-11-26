import json
from pathlib import Path
from web.build import build

ROOT=Path(__file__).resolve().parents[1]

def test_dashboard_uses_published_data_with_historical_fallback_and_accessibility_hooks():
 d=build(); html=(d/'index.html').read_text(encoding='utf-8'); js=(d/'app.js').read_text(encoding='utf-8'); css=(d/'styles.css').read_text(encoding='utf-8')
 for token in ('caseSelect','latestPublication','curveReading','historyRows','Indicadores de desempeño','Cómo leer este dashboard'): assert token in html
 for token in ('curve_points?.length','published_at','localeCompare','point_type','left_pillar','right_pillar','role="button"','known_cost_usd','lectura_curva'): assert token in js
 assert 'prefers-reduced-motion:reduce' in css and '.hero-art' in css and '@media(max-width:540px)' in css

def test_latest_case_sort_is_independent_of_filename_order():
 cases=json.loads((build()/'data/cases.json').read_text(encoding='utf-8'))
 ordered=sorted(cases,key=lambda c:(str(c.get('published_at')),str(c.get('case_id'))),reverse=True)
 assert ordered[0]['case_id']=='YC-TG177652684'

def test_historical_cases_are_not_reconstructed():
 cases=json.loads((build()/'data/cases.json').read_text(encoding='utf-8'))
 live=next(c for c in cases if c['case_id']=='YC-TG177652684')
 assert 'curve_points' not in live['curva'] and 'lectura_curva' not in (live.get('auditoria') or {})
