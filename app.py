from flask import Flask, request, jsonify, render_template
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


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/sync', methods=['POST'])
def sync():
    transactions = request.json
    tank = []  # Shares < 30 days old
    pool_shares = 0  # Shares > 30 days old
    pool_acb_cad = 0.0
    processed = []

    # Chronological sort is mandatory for Tank/Pool logic
    transactions.sort(key=lambda x: x['date'] if x['date'] else '9999-12-31')

    for tx in transactions:
        if not tx['date']: continue

        date_obj = datetime.strptime(tx['date'], '%Y-%m-%d')
        fx = get_fx_rate(tx['date'])

        # --- CONVERT BOTH PRICE AND FEE TO CAD ---
        price_cad = tx['price'] * fx
        fee_usd = float(tx.get('fee', 0) or 0)
        fee_cad = fee_usd * fx

        tx['fx'] = fx  # Send FX back to UI

        # 1. MOVE AGED SHARES FROM TANK TO POOL
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
            # VEST fees (CAD) increase the cost basis of these shares
            total_vest_cost_cad = (tx['shares'] * price_cad) + fee_cad
            unit_cost_cad = total_vest_cost_cad / tx['shares'] if tx['shares'] > 0 else 0

            tank.append({
                'date': date_obj,
                'shares': tx['shares'],
                'price_cad': unit_cost_cad
            })
            tx['notes'] = f"Vested {tx['shares']} @ {fx:.4f} FX"
            tx['gain'] = 0
            tx['proceeds'] = 0
            tx['acb'] = 0

        elif tx['type'] in ['SALE', 'AUTO_SALE']:
            req_shares = tx['shares']
            total_cost_cad = 0.0
            notes = []

            # Step A: Drain Tank First (FIFO)
            for unit in tank:
                if req_shares <= 0: break
                take = min(unit['shares'], req_shares)
                total_cost_cad += take * unit['price_cad']
                unit['shares'] -= take
                req_shares -= take
                notes.append(f"Matched {take} from Tank")

            tank = [u for u in tank if u['shares'] > 0]

            # Step B: Drain Pool
            if req_shares > 0:
                if pool_shares > 0:
                    avg_cost = pool_acb_cad / pool_shares
                    take = min(pool_shares, req_shares)
                    total_cost_cad += take * avg_cost
                    pool_shares -= take
                    pool_acb_cad -= take * avg_cost
                    req_shares -= take
                    notes.append(f"Took {take} from Pool")

            if req_shares > 0:
                notes.append(f"!!! SHORT {req_shares} SHARES")

            proceeds_cad = tx['shares'] * price_cad
            tx['proceeds'] = round(proceeds_cad, 2)
            tx['acb'] = round(total_cost_cad, 2)

            # CRA GAIN = PROCEEDS (CAD) - ACB (CAD) - FEE (CAD)
            tx['gain'] = round(proceeds_cad - total_cost_cad - fee_cad, 2)
            tx['notes'] = " | ".join(notes)

        processed.append(tx)

    # Return summary for Dashboard Cards
    summary = {
        "pool_shares": pool_shares,
        "pool_avg_cad": (pool_acb_cad / pool_shares) if pool_shares > 0 else 0,
        "pool_avg_usd": 0,
        "tank_shares": sum(u['shares'] for u in tank),
        "total_shares": pool_shares + sum(u['shares'] for u in tank)
    }

    return jsonify({"transactions": processed, "summary": summary})


if __name__ == '__main__':
    app.run(debug=True, port=5001)