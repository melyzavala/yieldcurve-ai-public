import pytest
import math
from backend.excel_bootstrap import *

def test_discount_coupon_and_bisection():
    assert discount(.1,182)==pytest.approx((1+.1*182/360)**-1)
    assert coupon(100,.08)==pytest.approx(4.0444444444)
    assert bisection(lambda x:x-.2,0,1)[0]==pytest.approx(.2)
    with pytest.raises(ExcelBootstrapError): bisection(lambda x:x*x+1,0,1)

def test_excel_benchmark_bootstrap():
    cetes=[('C28',23,9.957762,.06533696172627175),('C91',86,9.842592,.06587299997480589),('C182',170,9.681792,.06844217035811637),('C364',352,9.345717,.07037585376054685),('C2Y',674,8.709819,.077630163677176)]
    bonds=[('M3Y',688,102.751479,.085),('M5Y',2193,101.133101,.08),('M10Y',3600,95.121217,.08),('M20Y',6057,88.767725,.0775),('M30Y',10607,88.300057,.08)]
    result=bootstrap(cetes,bonds); expected=[.074785406,.087281647,.090786621,.099623763,.099576804]
    assert [n.spot_rate for n in result[-5:]]==pytest.approx(expected,abs=1e-6)
    assert all(n.converged and abs(n.recalculated_price-n.observed_price)<=1e-8 for n in result[-5:])

def test_excel_cetes_price_transformation_reproduces_the_five_fixture_rates():
    inputs=[(23,9.957762,.06533696172627175),(86,9.842592,.06587299997480589),(170,9.681792,.06844217035811637),(352,9.345717,.07037585376054685),(674,8.709819,.077630163677176)]
    for days, price, expected_rate_182 in inputs:
        ytm_from_price=(10/price-1)*360/days
        rate_182=(math.pow(1+ytm_from_price,182/360)-1)*(360/182)
        assert rate_182 == pytest.approx(expected_rate_182, abs=5e-9)
