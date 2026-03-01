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
    """Force FX to 1.5 for easy math: $1 USD = $1.5 CAD."""
    requests_mock.get(re.compile("bankofcanada.ca"), json={"observations": [{"FXUSDCAD": {"v": "1.5"}}]})


# --- ORIGINAL TESTS (Updated for 1.5 FX) ---

def test_30_day_rule_logic(client):
    payload = [
        {"id": "v1", "date": "2024-01-01", "type": "VEST", "price": 10.0, "shares": 100, "fee": 0},
        {"id": "s1", "date": "2024-02-15", "type": "SALE", "price": 20.0, "shares": 100, "fee": 0}
    ]
    response = client.post('/sync', json=payload).get_json()
    sale = response['transactions'][1]
    # Proceeds: (100 * 20 * 1.5) = 3000
    # Cost: (100 * 10 * 1.5) = 1500
    # Gain: 1500
    assert sale['gain'] == 1500.0
    assert "Took 100 from Pool" in sale['notes']


# --- NEW FEE LOGIC TESTS ---

def test_sale_fee_with_forex(client):
    """
    Test that a $10 USD fee on a sale is converted to $15 CAD (at 1.5 FX)
    and reduces the final gain.
    """
    payload = [
        {"id": "v1", "date": "2023-01-01", "type": "VEST", "price": 10.0, "shares": 100, "fee": 0},
        {"id": "s1", "date": "2024-02-01", "type": "SALE", "price": 20.0, "shares": 100, "fee": 10.0}
    ]
    response = client.post('/sync', json=payload).get_json()
    sale = response['transactions'][1]

    # Proceeds = 100 * 20 * 1.5 = 3000 CAD
    # Cost = 100 * 10 * 1.5 = 1500 CAD
    # Fee = 10 * 1.5 = 15 CAD
    # Gain = 3000 - 1500 - 15 = 1485 CAD
    assert sale['gain'] == 1485.0


def test_vest_fee_impacts_acb(client):
    """
    Test that a $10 USD fee on a VEST increases the ACB of those shares.
    """
    payload = [
        # Vest with $10 USD fee ($15 CAD)
        {"id": "v1", "date": "2023-01-01", "type": "VEST", "price": 10.0, "shares": 100, "fee": 10.0},
        # Sale with $0 fee
        {"id": "s1", "date": "2024-02-01", "type": "SALE", "price": 20.0, "shares": 100, "fee": 0}
    ]
    response = client.post('/sync', json=payload).get_json()
    sale = response['transactions'][1]

    # Vest Cost = (100 * 10 * 1.5) + (10 * 1.5) = 1515 CAD
    # Proceeds = 100 * 20 * 1.5 = 3000 CAD
    # Gain = 3000 - 1515 = 1485 CAD
    assert sale['acb'] == 1515.0
    assert sale['gain'] == 1485.0


def test_mixed_fees_vest_and_sale(client):
    """
    Double whammy: Fee on buy, fee on sell.
    """
    payload = [
        {"id": "v1", "date": "2023-01-01", "type": "VEST", "price": 10.0, "shares": 100, "fee": 10.0},  # +$15 CAD cost
        {"id": "s1", "date": "2024-02-01", "type": "SALE", "price": 20.0, "shares": 100, "fee": 10.0}  # -$15 CAD gain
    ]
    response = client.post('/sync', json=payload).get_json()
    sale = response['transactions'][1]

    # ACB = 1515
    # Proceeds = 3000
    # Sell Fee = 15
    # Gain = 3000 - 1515 - 15 = 1470
    assert sale['gain'] == 1470.0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-vv", "-s"]))