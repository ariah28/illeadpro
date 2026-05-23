"""
ILLeadPro - Data Storage
Handles saving and loading leads from JSON file
"""
import json
import os
from datetime import datetime

DATA_FILE = os.path.join(os.path.dirname(__file__), 'data', 'leads.json')


def load_leads():
    """Load all leads from storage"""
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return []


def save_leads(leads):
    """Save all leads to storage"""
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, 'w') as f:
        json.dump(leads, f, indent=2)


def add_lead(lead):
    """Add a new lead if not a duplicate"""
    leads = load_leads()

    # Deduplicate: same source + same first 100 chars of post
    for existing in leads:
        if (existing.get('source') == lead.get('source') and
                existing.get('post', '')[:100] == lead.get('post', '')[:100]):
            return False

    # Assign ID
    max_id = max([l.get('id', 0) for l in leads], default=0)
    lead['id'] = max_id + 1
    lead['dateFound'] = datetime.now().strftime('%Y-%m-%d %H:%M')

    # Default empty fields
    lead.setdefault('forwarded', '❌ Not Yet')
    lead.setdefault('partner', '')
    lead.setdefault('method', 'Email')
    lead.setdefault('status', 'new')
    lead.setdefault('dateClosed', '')
    lead.setdefault('dealValue', '')
    lead.setdefault('agentPct', '')
    lead.setdefault('yourPct', '')
    lead.setdefault('payRcvd', '❌ Pending')
    lead.setdefault('payDate', '')
    lead.setdefault('payMethod', '')
    lead.setdefault('notes', '')

    leads.insert(0, lead)
    save_leads(leads)
    return True


def get_stats():
    """Get summary statistics"""
    leads = load_leads()

    earned = 0
    pending = 0
    for l in leads:
        if l.get('dealValue') and l.get('agentPct') and l.get('yourPct'):
            try:
                fee = (float(l['dealValue']) *
                       float(l['agentPct']) / 100 *
                       float(l['yourPct']) / 100)
                if l.get('payRcvd') == '✅ Yes':
                    earned += fee
                elif l.get('status') == '✅ Closed':
                    pending += fee
            except (ValueError, TypeError):
                pass

    return {
        'total': len(leads),
        'hot': sum(1 for l in leads if '🔥' in l.get('score', '')),
        'forwarded': sum(1 for l in leads if l.get('forwarded') == '✅ Yes'),
        'closed': sum(1 for l in leads if l.get('status') == '✅ Closed'),
        'earned': round(earned, 2),
        'pending': round(pending, 2),
    }
