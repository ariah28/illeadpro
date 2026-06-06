"""
ILLeadPro - Illinois Public Data Scrapers
Replaces Craigslist (blocked from cloud/server IPs) with sources that work reliably:
  1. Cook County Open Data API (Socrata) — free government API, never blocks servers
  2. Fannie Mae HomePath REO — bank-owned foreclosures in IL
  3. Foreclosure listing aggregators
"""
import sys
import os
import re
import time
import random
import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from ai_scorer import score_lead
from database import add_lead

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/121.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/json, text/html, */*',
    'Accept-Language': 'en-US,en;q=0.9',
}


def get_text(el):
    return el.get_text(strip=True) if el else ''


# ---------------------------------------------------------------------------
# Main entry point (keeps same function name so main_scraper.py still works)
# ---------------------------------------------------------------------------

def scrape_craigslist():
    """
    REPLACED: Craigslist blocks all cloud/server IP addresses.
    Now scrapes Cook County open data API + Fannie Mae REO + foreclosure sites.
    """
    print("🔍 Scraping IL public data sources (Craigslist blocked cloud IPs)...")
    new_leads = 0
    new_leads += _scrape_cook_county_api()
    new_leads += _scrape_homepath_reo()
    new_leads += _scrape_foreclosure_sites()
    print(f"  📊 Public data sources: {new_leads} new leads found")
    return new_leads


# ---------------------------------------------------------------------------
# 1. Cook County Open Data (Socrata API) — government data, always accessible
# ---------------------------------------------------------------------------

def _scrape_cook_county_api():
    """Pull recent property data from Cook County's public Socrata API."""
    new_leads = 0

    datasets = [
        {
            'url':  'https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json',
            'name': 'Cook County Assessor Sales',
        },
        {
            'url':  'https://datacatalog.cookcountyil.gov/resource/5pge-nu6u.json',
            'name': 'Cook County Recorder Deeds',
        },
    ]

    addr_keys  = ['addr', 'address', 'property_address', 'prop_address',
                  'site_location', 'location', 'street', 'full_address']
    price_keys = ['sale_price', 'price', 'assessed_value', 'consideration',
                  'amount', 'market_value', 'estimated_market_value']

    for ds in datasets:
        try:
            resp = requests.get(
                ds['url'],
                headers=HEADERS,
                params={'$limit': 30, '$order': ':id DESC'},
                timeout=15,
            )
            if resp.status_code != 200:
                print(f"  ⚠️ {ds['name']}: HTTP {resp.status_code}")
                continue

            records = resp.json()
            if not isinstance(records, list) or not records:
                continue

            print(f"  📡 {ds['name']}: {len(records)} records")

            for rec in records[:20]:
                try:
                    # Find address — check known keys first, then scan all fields
                    addr = next((str(rec[k]) for k in addr_keys if rec.get(k) and len(str(rec[k])) > 4), '')
                    if not addr:
                        # Scan all string fields for something address-like
                        for k, v in rec.items():
                            if isinstance(v, str) and len(v) > 8:
                                if any(t in k.lower() for t in ['addr', 'street', 'prop', 'loc']):
                                    addr = v
                                    break

                    if not addr or len(addr) < 5:
                        continue

                    price = next((str(rec[k]) for k in price_keys
                                  if rec.get(k) and str(rec[k]) not in ('0', '0.0', '')), '')

                    area      = 'Cook County, IL'
                    post_text = (
                        f"COOK COUNTY PROPERTY RECORD: {addr}. "
                        f"Price/Value: {price}. Cook County, IL."
                    )

                    # Skip AI scoring for public records — they're always real estate
                    lead = {
                        'name':           'Cook County Property',
                        'phone':          '',
                        'email':          '',
                        'area':           area,
                        'source':         'Public Records',
                        'type':           '🏠 Seller',
                        'score':          '⚡ Warm',
                        'post':           post_text,
                        'link':           ds['url'],
                        'reason':         'Cook County public property record — potential motivated seller',
                        'estimatedValue': price,
                    }

                    if add_lead(lead):
                        new_leads += 1
                        print(f"  ✅ Cook County API: {addr[:50]}...")

                    time.sleep(random.uniform(0.1, 0.3))

                except Exception:
                    continue

        except Exception as e:
            print(f"  ❌ {ds['name']}: {e}")
            continue

    return new_leads


# ---------------------------------------------------------------------------
# 2. Fannie Mae HomePath REO — bank-owned foreclosures in Illinois
# ---------------------------------------------------------------------------

def _scrape_homepath_reo():
    """Scrape Fannie Mae HomePath for Illinois REO (bank-owned) properties."""
    new_leads = 0

    try:
        url  = 'https://www.homepath.com/il/'
        resp = requests.get(url, headers=HEADERS, timeout=12)

        if resp.status_code == 200:
            soup     = BeautifulSoup(resp.text, 'lxml')
            listings = (
                soup.select('[class*="listing"]') or
                soup.select('[class*="property"]') or
                soup.select('[class*="result"]')   or
                soup.select('article')
            )[:15]

            for listing in listings:
                try:
                    addr_el  = (listing.select_one('[class*="address"]') or
                                listing.select_one('h2, h3, h4'))
                    price_el = listing.select_one('[class*="price"]')

                    if not addr_el:
                        continue

                    addr_text  = get_text(addr_el)
                    price_text = get_text(price_el)

                    if len(addr_text) < 5:
                        continue

                    post_text = (
                        f"FANNIE MAE REO: {addr_text}. "
                        f"Price: {price_text}. Bank-owned foreclosure — must sell."
                    )

                    lead = {
                        'name':           'Fannie Mae REO',
                        'phone':          '',
                        'email':          '',
                        'area':           addr_text,
                        'source':         'Foreclosure',
                        'type':           '🏠 Seller',
                        'score':          '🔥 Hot',
                        'post':           post_text,
                        'link':           url,
                        'reason':         'Fannie Mae bank-owned property — institutional motivated seller',
                        'estimatedValue': price_text,
                    }

                    if add_lead(lead):
                        new_leads += 1
                        print(f"  ✅ HomePath REO: {addr_text[:50]}...")

                except Exception:
                    continue
        else:
            print(f"  ⚠️ HomePath: HTTP {resp.status_code}")

    except Exception as e:
        print(f"  ⚠️ HomePath error: {e}")

    return new_leads


# ---------------------------------------------------------------------------
# 3. Foreclosure listing aggregators
# ---------------------------------------------------------------------------

def _scrape_foreclosure_sites():
    """Scrape public foreclosure listing sites for Illinois properties."""
    new_leads = 0

    sources = [
        {
            'url':  'https://www.allforeclosures.com/foreclosures/il/',
            'name': 'AllForeclosures IL',
        },
        {
            'url':  'https://www.foreclosure.com/listing/list.html?state=IL',
            'name': 'Foreclosure.com IL',
        },
        {
            'url':  'https://www.realtytrac.com/mapsearch/#?s=illinois&t=foreclosure',
            'name': 'RealtyTrac IL Foreclosures',
        },
    ]

    for source in sources:
        try:
            resp = requests.get(source['url'], headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                print(f"  ⚠️ {source['name']}: HTTP {resp.status_code}")
                continue

            soup = BeautifulSoup(resp.text, 'lxml')

            listings = (
                soup.select('[class*="listing"]')     or
                soup.select('[class*="property"]')    or
                soup.select('[class*="foreclosure"]') or
                soup.select('article')
            )[:15]

            for listing in listings:
                try:
                    addr_el  = (listing.select_one('[class*="address"]') or
                                listing.select_one('h2, h3, h4'))
                    price_el = listing.select_one('[class*="price"]')

                    if not addr_el:
                        continue

                    addr_text  = get_text(addr_el)
                    price_text = get_text(price_el)

                    if len(addr_text) < 5:
                        continue

                    post_text = (
                        f"FORECLOSURE: {addr_text}. "
                        f"Price: {price_text}. Illinois — distressed sale."
                    )

                    lead = {
                        'name':           'Foreclosure Property',
                        'phone':          '',
                        'email':          '',
                        'area':           addr_text,
                        'source':         'Foreclosure',
                        'type':           '🏠 Seller',
                        'score':          '🔥 Hot',
                        'post':           post_text,
                        'link':           source['url'],
                        'reason':         'Foreclosure listing — distressed sale, motivated seller',
                        'estimatedValue': price_text,
                    }

                    if add_lead(lead):
                        new_leads += 1
                        print(f"  ✅ {source['name']}: {addr_text[:50]}...")

                except Exception:
                    continue

            time.sleep(random.uniform(1, 2))

        except Exception as e:
            print(f"  ❌ {source['name']}: {e}")
            continue

    return new_leads
