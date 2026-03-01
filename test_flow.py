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

if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-vv", "-s"]))