import numpy as np
from scipy import optimize


def test_numpy_and_scipy_are_available() -> None:
    root = optimize.brentq(lambda value: value**2 - 2, 1, 2)

    assert np.isclose(root, np.sqrt(2))
