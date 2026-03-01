from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta

app = Flask(__name__)


def get_fx_rate(date_str):
    """Fetches USD/CAD for the EXACT date. Raises Exception if unavailable."""
    url = f"https://www.bankofcanada.ca/valet/observations/FXUSDCAD/json?start_date={date_str}&end_date={date_str}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not data.get('observations'):
            raise ValueError(f"No FX rate found for {date_str} (Weekend/Holiday).")
        return float(data['observations'][0]['FXUSDCAD']['v'])
    except Exception as e:
        raise Exception(f"FX Fetch Failed for {date_str}: {str(e)}")


@app.route('/sync', methods=['POST'])
def sync():
    transactions = request.json
    tank = []  # Shares < 30 days old (Tracked individually)
    pool_shares = 0  # Shares > 30 days old (Pooled)
    pool_acb_cad = 0.0
    processed = []

    # Sort by date to ensure chronological processing
    transactions.sort(key=lambda x: x['date'])

    for tx in transactions:
        date_obj = datetime.strptime(tx['date'], '%Y-%m-%d')
        fx = get_fx_rate(tx['date'])
        price_cad = tx['price'] * fx

        # 1. MOVE AGED SHARES FROM TANK TO POOL
        # Any share in the tank older than 30 days relative to THIS transaction moves to Pool
        remaining_tank = []
        for unit in tank:
            age = (date_obj - unit['date']).days
            if age > 30:
                pool_shares += unit['shares']
                pool_acb_cad += unit['shares'] * unit['price_cad']
            else:
                remaining_tank.append(unit)
        tank = remaining_tank

        # 2. PROCESS TRANSACTION
        if tx['type'] == 'VEST':
            tank.append({
                'date': date_obj,
                'shares': tx['shares'],
                'price_cad': price_cad
            })
            tx['notes'] = f"Added {tx['shares']} to Tank. FX: {fx}"
            tx['gain'] = 0

        elif tx['type'] in ['SALE', 'AUTO_SALE']:
            req_shares = tx['shares']
            total_cost_cad = 0.0
            notes = []

            # Step A: Drain Tank First (FIFO within the 30-day window)
            for unit in tank:
                if req_shares <= 0: break
                take = min(unit['shares'], req_shares)
                total_cost_cad += take * unit['price_cad']
                unit['shares'] -= take
                req_shares -= take
                notes.append(f"Matched {take} from Tank (Vest {unit['date'].date()})")

            tank = [u for u in tank if u['shares'] > 0]

            # Step B: Drain Pool if Tank is empty
            if req_shares > 0:
                if pool_shares > 0:
                    avg_cost = pool_acb_cad / pool_shares
                    take = min(pool_shares, req_shares)
                    total_cost_cad += take * avg_cost
                    pool_shares -= take
                    pool_acb_cad -= take * avg_cost
                    req_shares -= take
                    notes.append(f"Took {take} from Pool (Avg Cost: ${avg_cost:.4f})")

            if req_shares > 0:
                notes.append(f"!!! INSUFFICIENT SHARES: Missing {req_shares}")

            proceeds_cad = tx['shares'] * price_cad
            tx['gain'] = round(proceeds_cad - total_cost_cad, 2)
            tx['notes'] = " | ".join(notes)

        processed.append(tx)

    return jsonify({"transactions": processed})


if __name__ == '__main__':
    app.run(debug=True)