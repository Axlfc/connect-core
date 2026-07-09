import pytest
from app.core.uncertainty import aggregate_uncertainty

def test_aggregate_uncertainty():
    assert aggregate_uncertainty([]) is None
    assert aggregate_uncertainty([0.1, 0.2, 0.3]) == pytest.approx(0.2)
    assert aggregate_uncertainty([0.5]) == 0.5
