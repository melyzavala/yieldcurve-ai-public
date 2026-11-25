"""Ruta EXCEL_BOOTSTRAP_182D_V1 sin SciPy."""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Callable

METHODOLOGY = "EXCEL_BOOTSTRAP_182D_V1"
PERIOD_DAYS = 182

class ExcelBootstrapError(ValueError): pass

@dataclass(frozen=True)
class ExcelNode:
    instrument_id: str; days: int; spot_rate: float; observed_price: float; recalculated_price: float; iterations: int; converged: bool

def bisection(f: Callable[[float], float], low: float, high: float, tolerance: float=1e-10, max_iterations: int=200) -> tuple[float,int]:
    if not all(math.isfinite(x) for x in (low,high,tolerance)) or low >= high or tolerance <= 0 or max_iterations < 1: raise ExcelBootstrapError("BISECTION_INPUT_INVALID")
    fl, fh = f(low), f(high)
    if not all(math.isfinite(x) for x in (fl,fh)): raise ExcelBootstrapError("BISECTION_NONFINITE")
    if fl == 0: return low,0
    if fh == 0: return high,0
    if fl * fh > 0: raise ExcelBootstrapError("BISECTION_NO_SIGN_CHANGE")
    for i in range(1,max_iterations+1):
        mid=(low+high)/2; fm=f(mid)
        if not math.isfinite(fm): raise ExcelBootstrapError("BISECTION_NONFINITE")
        if abs(fm)<=tolerance: return mid,i
        if fl*fm<0: high,fh=mid,fm
        else: low,fl=mid,fm
    raise ExcelBootstrapError("BISECTION_MAX_ITERATIONS")

def linear_rate(nodes: list[ExcelNode], days: int) -> float:
    ns=sorted(nodes,key=lambda n:n.days)
    for a,b in zip(ns,ns[1:]):
        if a.days<=days<=b.days: return a.spot_rate+(days-a.days)*(b.spot_rate-a.spot_rate)/(b.days-a.days)
    if ns and days==ns[-1].days: return ns[-1].spot_rate
    raise ExcelBootstrapError("LINEAR_INTERPOLATION_OUT_OF_RANGE")

def discount(rate: float, days: int) -> float:
    if not math.isfinite(rate) or days<=0: raise ExcelBootstrapError("DISCOUNT_INPUT_INVALID")
    return (1+rate*PERIOD_DAYS/360)**(-days/PERIOD_DAYS)

def coupon(face: float, coupon_rate: float) -> float:
    if not all(math.isfinite(x) for x in (face,coupon_rate)) or face <= 0: raise ExcelBootstrapError("COUPON_INPUT_INVALID")
    return face*coupon_rate*PERIOD_DAYS/360

def cashflows(maturity_days: int, coupon_rate: float, face: float=100.0) -> list[tuple[int,float]]:
    if not isinstance(maturity_days,int) or maturity_days <= 0: raise ExcelBootstrapError("CASHFLOW_INPUT_INVALID")
    dates=list(range(maturity_days%PERIOD_DAYS or PERIOD_DAYS,maturity_days+1,PERIOD_DAYS))
    if dates[-1] != maturity_days: dates.append(maturity_days)
    c=coupon(face,coupon_rate)
    return [(d,c+(face if d==maturity_days else 0.0)) for d in dates]

def price(flows: list[tuple[int,float]], nodes: list[ExcelNode]) -> float:
    return sum(amount*discount(linear_rate(nodes,days),days) for days,amount in flows)

def _point_type(nodes: list[ExcelNode], days: int) -> str:
    return "PILLAR" if any(node.days == days for node in nodes[1:]) else "INTERPOLATED"

def _interpolation_bounds(nodes: list[ExcelNode], days: int) -> tuple[ExcelNode, ExcelNode] | None:
    ordered = sorted(nodes, key=lambda node: node.days)
    for left, right in zip(ordered, ordered[1:]):
        if left.days < days < right.days:
            return left, right
    return None

def _flow_trace(instrument_id: str, flows: list[tuple[int, float]], nodes: list[ExcelNode]) -> list[dict]:
    """Records the existing 182/360 discount inputs without changing valuation."""
    traced = []
    for days, amount in flows:
        rate = linear_rate(nodes, days)
        point_type = _point_type(nodes, days)
        entry = {
            "days": days, "time_years": days / 360.0, "amount": amount,
            "spot_rate": rate, "discount_factor": discount(rate, days),
            "point_type": point_type, "source_method": "LINEAR_SPOT_RATE",
        }
        if point_type == "INTERPOLATED":
            left, right = _interpolation_bounds(nodes, days) or (None, None)
            if left is None or right is None:
                raise ExcelBootstrapError("LINEAR_INTERPOLATION_OUT_OF_RANGE")
            entry["left_pillar"] = left.instrument_id
            entry["right_pillar"] = right.instrument_id
        traced.append(entry)
    return traced

def _expanded_curve_points(nodes: list[ExcelNode], bonds: list[tuple[str, int, float, float]]) -> list[dict]:
    points = {
        node.days: {
            "instrument_id": node.instrument_id, "days": node.days,
            "time_years": node.days / 360.0, "spot_rate": node.spot_rate,
            "discount_factor": discount(node.spot_rate, node.days), "point_type": "PILLAR",
        }
        for node in nodes[1:]
    }
    for instrument_id, days, _dirty, coupon_rate in bonds:
        for flow in _flow_trace(instrument_id, cashflows(days, coupon_rate), nodes):
            if flow["point_type"] == "INTERPOLATED":
                points.setdefault(flow["days"], {key: value for key, value in flow.items() if key != "amount"})
    return [points[days] for days in sorted(points)]

def bootstrap(cetes: list[tuple[str,int,float]], bonds: list[tuple[str,int,float,float]], overnight_rate: float=.0675, tolerance: float=1e-8, max_iterations: int=200) -> list[ExcelNode]:
    if not math.isfinite(overnight_rate): raise ExcelBootstrapError("OVERNIGHT_RATE_INVALID")
    nodes=[ExcelNode("OVERNIGHT",1,overnight_rate,0,0,0,True)]
    for entry in cetes:
        instrument,days,dirty=entry[:3]
        if not isinstance(days,int) or days<=0 or not math.isfinite(dirty) or dirty<=0: raise ExcelBootstrapError("CETES_INPUT_INVALID")
        rate=entry[3] if len(entry)==4 else (10/dirty-1)*360/days
        nodes.append(ExcelNode(instrument,days,rate,dirty,dirty,0,True))
    for instrument,days,dirty,coupon_rate in bonds:
        flows=cashflows(days,coupon_rate)
        def objective(rate: float) -> float:
            return price(flows,nodes+[ExcelNode(instrument,days,rate,dirty,0,0,False)])-dirty
        rate,it=bisection(objective,0.0,1.0,tolerance,max_iterations)
        calculated=price(flows,nodes+[ExcelNode(instrument,days,rate,dirty,0,it,True)])
        nodes.append(ExcelNode(instrument,days,rate,dirty,calculated,it,True))
    return nodes

def build_from_payload(payload: dict) -> dict:
    """Construye EXCEL_BOOTSTRAP_182D_V1 sin importar SciPy."""
    if payload.get('metodologia') != METHODOLOGY: raise ExcelBootstrapError('METHODOLOGY_INCOMPATIBLE')
    cetes=payload.get('excel_cetes_nodes'); bonds=payload.get('excel_mbonos')
    if not isinstance(cetes,list) or not isinstance(bonds,list): raise ExcelBootstrapError('EXCEL_METADATA_MISSING')
    nodes=bootstrap([tuple(x) for x in cetes],[tuple(x) for x in bonds],payload.get('overnight_rate',.0675),payload.get('tolerance',1e-8),payload.get('max_iterations',200))
    repricing = []
    for node, bond in zip((node for node in nodes if node.instrument_id.startswith("M")), bonds, strict=True):
        instrument_id, days, _dirty, coupon_rate = bond
        repricing.append({**node.__dict__, "cashflows": _flow_trace(instrument_id, cashflows(days, coupon_rate), nodes)})
    return {'case_id':payload['case_id'],'curve_version':payload['curve_version'],'mode':'SIMULADO','valuation_date':payload['valuation_date'],'metodologia':METHODOLOGY,'pillars':[n.__dict__ for n in nodes[1:]],'curve_points':_expanded_curve_points(nodes, bonds),'repricing':repricing,'summary':{'instrument_count':len(nodes)-1,'max_absolute_repricing_error':max(abs(n.recalculated_price-n.observed_price) for n in nodes if n.instrument_id.startswith('M'))}}
