from io import BytesIO
from fastapi.testclient import TestClient
from backend.curve_visualization import build_curve_png
import backend.api as api
from tests.test_case_excel import ARTIFACT
def test_png_is_valid_and_uses_existing_pillars():
 data=build_curve_png(ARTIFACT); assert data.startswith(b"\x89PNG\r\n\x1a\n") and len(data)>1000
def test_png_rejects_empty_invalid_and_sensitive():
 for a in ({**ARTIFACT,"curva":{"pillars":[]}}, {**ARTIFACT,"telegram_user_id":"x"}):
  try: build_curve_png(a); assert False
  except ValueError: assert True
def test_png_endpoint_requires_auth(monkeypatch):
 monkeypatch.setenv("YIELDCURVE_API_KEY","key"); c=TestClient(api.app); assert c.post("/v1/artifacts/curve.png",json=ARTIFACT).status_code==401; r=c.post("/v1/artifacts/curve.png",json=ARTIFACT,headers={"X-YieldCurve-Key":"key"}); assert r.status_code==200 and r.headers["content-type"]=="image/png"
