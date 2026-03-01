import sys

import pytest
from app import get_fx_rate

def test_bank_of_canada_live_response():
    """Verify actual data from BoC for a known business day."""
    # Jan 2, 2024 is confirmed as 1.3316
    rate = get_fx_rate("2024-01-02")
    assert rate == 1.3316

def test_weekend_failure():
    """Verify the system correctly identifies a Sunday as no-data."""
    with pytest.raises(Exception) as excinfo:
        get_fx_rate("2024-01-07") # Sunday
    assert "No FX rate found" in str(excinfo.value)

if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-vv", "-s"]))