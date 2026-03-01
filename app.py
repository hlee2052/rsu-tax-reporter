import requests
from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)

# Cache for FX rates to avoid redundant API calls
fx_cache = {}


def get_fx_rate(date_str):
    if not date_str or date_str in fx_cache:
        return fx_cache.get(date_str)

    target_date = datetime.strptime(date_str, '%Y-%m-%d')
    # CRA Rule: Use the rate from the nearest preceding business day for weekends/holidays
    for i in range(5):
        check_date = (target_date - timedelta(days=i)).strftime('%Y-%m-%d')
        try:
            url = f"https://www.bankofcanada.ca/valet/observations/FXUSDCAD/json?start_date={check_date}&end_date={check_date}"
            response = requests.get(url, timeout=5).json()
            if response.get('observations'):
                rate = float(response['observations'][0]['FXUSDCAD']['v'])
                fx_cache[date_str] = rate
                return rate
        except Exception:
            continue
    return None


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/sync', methods=['POST'])
def sync():
    data = request.json
    transactions = sorted([t for t in data if t.get('date')], key=lambda x: x['date'])

    holding_tank = []  # Shares < 30 days old
    pool_shares = 0
    pool_total_cost_cad = 0.0
    pool_total_cost_usd = 0.0

    results = []

    for item in transactions:
        date_obj = datetime.strptime(item['date'], '%Y-%m-%d')
        shares = int(item.get('shares') or 0)
        usd_price = float(item.get('price') or 0)

        # 1. Fetch/Update FX
        fx = get_fx_rate(item['date'])
        item['fx'] = fx
        if fx is None:
            item['notes'] = "ERROR: FX Rate not found."
            results.append({**item, "proceeds": 0, "acb": 0, "gain": 0})
            continue

        cad_price = usd_price * fx

        # 2. Graduation: Move shares >30 days old from Tank to Pool
        new_tank = []
        for v in holding_tank:
            if (date_obj - v['date']).days > 30:
                pool_shares += v['shares']
                pool_total_cost_cad += (v['shares'] * v['price_cad'])
                pool_total_cost_usd += (v['shares'] * v['price_usd'])
            else:
                new_tank.append(v)
        holding_tank = new_tank

        res = {**item, "proceeds": 0, "acb": 0, "gain": 0, "notes": ""}

        if item['type'] == 'VEST':
            holding_tank.append({
                'date': date_obj, 'shares': shares,
                'price_cad': cad_price, 'price_usd': usd_price
            })
            res['notes'] = "Added to 30-day isolation tank."
        else:
            # SALE Logic: Match Tank first (1:1 cost), then Pool (Weighted Average)
            to_sell = shares
            total_acb = 0
            res['proceeds'] = round(cad_price * shares, 2)

            # Match against Tank (Subsection 7(1.31))
            for v in holding_tank:
                if to_sell <= 0: break
                if 0 <= (date_obj - v['date']).days <= 30:
                    taken = min(to_sell, v['shares'])
                    total_acb += (taken * v['price_cad'])
                    v['shares'] -= taken
                    to_sell -= taken
                    res['notes'] += f"Matched {taken} shs to {v['date'].strftime('%m/%d')} vest. "

            # Match against Pool
            if to_sell > 0:
                if pool_shares > 0:
                    avg_cad = pool_total_cost_cad / pool_shares
                    total_acb += (to_sell * avg_cad)
                    # Proportionally reduce pool totals
                    pool_total_cost_usd -= (to_sell * (pool_total_cost_usd / pool_shares))
                    pool_total_cost_cad -= (to_sell * avg_cad)
                    pool_shares -= to_sell
                    res['notes'] += f"Used {to_sell} shs from Pool."
                else:
                    res['notes'] = "ERROR: No shares available in Pool or Tank!"

            res['acb'] = round(total_acb, 2)
            res['gain'] = round(res['proceeds'] - res['acb'], 2)

        results.append(res)

    summary = {
        "pool_shares": pool_shares,
        "pool_avg_cad": round(pool_total_cost_cad / pool_shares, 2) if pool_shares > 0 else 0,
        "pool_avg_usd": round(pool_total_cost_usd / pool_shares, 2) if pool_shares > 0 else 0,
        "tank_shares": sum(v['shares'] for v in holding_tank),
        "total_shares": pool_shares + sum(v['shares'] for v in holding_tank)
    }

    return jsonify({"transactions": results, "summary": summary})


if __name__ == '__main__':
    app.run(debug=True, port=5000)