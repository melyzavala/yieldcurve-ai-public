"""PNG view of existing Nash pillars; no financial calculation occurs here."""
from __future__ import annotations
from io import BytesIO
import math
from typing import Any
import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
from backend.case_excel import validate_case_artifact

def build_curve_png(case_artifact: dict[str, Any]) -> bytes:
    validate_case_artifact(case_artifact)
    pillars=(case_artifact.get("curva") or {}).get("pillars")
    if not isinstance(pillars,list) or not 1 <= len(pillars) <= 500: raise ValueError("PILLARS_INVALIDOS")
    x=[p.get("time_years",p.get("days")) for p in pillars]; y=[p.get("spot_rate") for p in pillars]
    if not all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in x+y): raise ValueError("PILLARS_INVALIDOS")
    fig,ax=plt.subplots(figsize=(9,5)); ax.plot(x,[v*100 for v in y],marker="o",linewidth=1.8); ax.grid(True,alpha=.25); ax.set_xlabel("Plazo (años)" if all("time_years" in p for p in pillars) else "Plazo (días)"); ax.set_ylabel("Tasa spot (%)"); ax.set_title(f"Curva spot · {case_artifact.get('fecha_corte')} · {case_artifact.get('execution_mode')}"); fig.tight_layout(); out=BytesIO(); fig.savefig(out,format="png",dpi=150); plt.close(fig); return out.getvalue()
