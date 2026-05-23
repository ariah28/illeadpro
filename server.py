"""
ILLeadPro - Web Dashboard Server
Serves your lead dashboard with live data from scrapers
"""
from flask import Flask, jsonify, request, send_from_directory
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from database import load_leads, save_leads, add_lead, get_stats

app = Flask(__name__, static_folder=os.path.dirname(__file__))


# ----------------------------------------
# API ROUTES
# ----------------------------------------

@app.route('/api/leads', methods=['GET'])
def get_leads():
    leads = load_leads()
    return jsonify(leads)


@app.route('/api/leads', methods=['POST'])
def create_lead():
    data = request.json
    success = add_lead(data)
    return jsonify({'success': success})


@app.route('/api/leads/<int:lead_id>', methods=['PUT'])
def update_lead(lead_id):
    leads = load_leads()
    data = request.json

    for i, lead in enumerate(leads):
        if lead.get('id') == lead_id:
            leads[i].update(data)
            save_leads(leads)
            return jsonify({'success': True, 'lead': leads[i]})

    return jsonify({'success': False, 'error': 'Lead not found'}), 404


@app.route('/api/stats', methods=['GET'])
def get_statistics():
    return jsonify(get_stats())


@app.route('/api/logs', methods=['GET'])
def get_logs():
    log_file = os.path.join(os.path.dirname(__file__), 'logs', 'scraper.log')
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            lines = f.readlines()
        return jsonify({'logs': lines[-50:]})
    return jsonify({'logs': []})


# ----------------------------------------
# SERVE DASHBOARD
# ----------------------------------------

@app.route('/')
def dashboard():
    return send_from_directory(os.path.dirname(__file__), 'ILLeadPro.html')


@app.route('/health')
def health():
    stats = get_stats()
    return jsonify({'status': 'running', 'stats': stats})


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
