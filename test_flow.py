import sys

import pytest
import re
from app import app as flask_app

@pytest.fixture
def client():
    flask_app.config['TESTING'] = True
    return flask_app.test_client()

@pytest.fixture(autouse=True)
def mock_fx(requests_mock):
    """Force FX to 1.0 for logic testing."""
    requests_mock.get(re.compile("bankofcanada.ca"), json={"observations": [{"FXUSDCAD": {"v": "1.0"}}]})

def test_30_day_rule_logic(client):
    """Test that shares older than 30 days move to Pool."""
    payload = [
        {"id": "v1", "date": "2024-01-01", "type": "VEST", "price": 10.0, "shares": 100},
        {"id": "s1", "date": "2024-02-15", "type": "SALE", "price": 20.0, "shares": 100}
    ]
    response = client.post('/sync', json=payload)
    note = response.get_json()['transactions'][1]['notes']
    assert "Took 100 from Pool" in note

def test_mixed_tank_and_pool(client):
    """Test selling more than the tank holds draws from pool."""
    payload = [
        {"id": "old", "date": "2023-01-01", "type": "VEST", "price": 10.0, "shares": 50},
        {"id": "new", "date": "2024-01-01", "type": "VEST", "price": 100.0, "shares": 50},
        {"id": "sale", "date": "2024-01-05", "type": "SALE", "price": 110.0, "shares": 75}
    ]
    response = client.post('/sync', json=payload).get_json()
    sale = response['transactions'][2]
    # Cost = (50 Tank * 100) + (25 Pool * 10) = 5250
    # Proceeds = 75 * 110 = 8250. Gain = 3000
    assert sale['gain'] == 3000.0


def test_user_scenario_1(client):
    """
    Scenario:
    1. June 2023: 100 shares @ $90 (Aged into Pool)
    2. May 15, 2025: Vest 200, Auto-Sell 150 @ $120 (50 remain in Tank)
    3. June 10, 2025: Sell 55 @ $140
       - 50 should come from Tank @ $120 cost
       - 5 should come from Pool @ $90 cost
    """
    payload = [
        # Legacy Pool
        {"id": "legacy", "date": "2023-06-03", "type": "VEST", "price": 90.0, "shares": 100},
        # New Vest + Auto-Sale (Leaves 50 in Tank)
        {"id": "vest_2025", "date": "2025-05-15", "type": "VEST", "price": 120.0, "shares": 200},
        {"id": "auto_2025", "date": "2025-05-15", "type": "AUTO_SALE", "price": 120.0, "shares": 150},
        # The Big Sale
        {"id": "sale_june", "date": "2025-06-10", "type": "SALE", "price": 140.0, "shares": 55}
    ]

    response = client.post('/sync', json=payload)
    data = response.get_json()['transactions']

    # Find our specific sale
    sale = next(t for t in data if t['id'] == "sale_june")

    # Calculation Check:
    # (50 * 140) - (50 * 120) = 1000
    # (5 * 140) - (5 * 90) = 250
    # Total Gain = 1250
    assert sale['gain'] == 1250.0
    assert "Matched 50 from Tank" in sale['notes']
    assert "Took 5 from Pool" in sale['notes']


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-vv", "-s"]))