"""
ILLeadPro - Craigslist Scraper
Scrapes Chicago/Illinois Craigslist housing sections for buyer/seller leads
"""
import sys
import os
import requests
from bs4 import BeautifulSoup
import time
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from ai_scorer import score_lead
from database import add_lead

CRAIGSLIST_CITIES = [
    'chicago',
    'chicago/nwc',
    'chicago/nch',
    'chicago/sox',
]

SECTIONS = [
    ('rea', 'Real Estate For Sale'),
    ('reo', 'Real Estate Wanted'),
    ('hsw', 'Housing Wanted'),
]

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    )
}


def scrape_craigslist():
    """Scrape Craigslist for Illinois real estate leads"""
    print("🔍 Scraping Craigslist...")
    new_leads = 0

    for city in CRAIGSLIST_CITIES:
        for section_code, section_name in SECTIONS:
            try:
                url = f"https://{city}.craigslist.org/search/{section_code}"
                params = {
                    'query': 'illinois house home',
                    'sort': 'date',
                    'postedToday': 1
                }

                resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, 'lxml')
                listings = soup.select('li.cl-search-result')

                for listing in listings[:20]:
                    try:
                        title_el = listing.select_one('.titlestring')
                        if not title_el:
                            continue
                        title = title_el.text.strip()

                        link_el = listing.select_one('a.posting-title')
                        if not link_el:
                            continue
                        link = link_el.get('href', '')

                        price_el = listing.select_one('.priceinfo')
                        price = price_el.text.strip() if price_el else ''

                        loc_el = listing.select_one('.meta .separator + span')
                        location = loc_el.text.strip() if loc_el else 'Illinois'

                        post_text = f"{title}. {price} - {location}"
                        phone = ''
                        email = ''

                        # Fetch full post for contact info + body
                        if link:
                            try:
                                post_resp = requests.get(link, headers=HEADERS, timeout=8)
                                if post_resp.status_code == 200:
                                    post_soup = BeautifulSoup(post_resp.text, 'lxml')

                                    body = post_soup.select_one('#postingbody')
                                    if body:
                                        post_text = body.text.strip()[:500]

                                    # Extract phone number if visible
                                    phone_el = post_soup.select_one('.reply-tel-number, [data-number]')
                                    if phone_el:
                                        phone = phone_el.text.strip()

                                    # Extract email if visible
                                    email_el = post_soup.select_one('a[href^="mailto"]')
                                    if email_el:
                                        email = email_el.get('href', '').replace('mailto:', '')

                                time.sleep(random.uniform(1, 2))
                            except Exception:
                                pass

                        analysis = score_lead(post_text, 'Craigslist', location)

                        if not analysis.get('is_real_estate_lead'):
                            continue

                        lead = {
                            'name': 'Craigslist Poster',
                            'phone': phone,
                            'email': email,
                            'area': location or 'Illinois',
                            'source': 'Craigslist',
                            'type': analysis.get('type', '🏠 Seller'),
                            'score': analysis.get('score', '⚡ Warm'),
                            'post': post_text[:400],
                            'link': link,
                            'reason': analysis.get('reason', ''),
                            'estimatedValue': analysis.get('estimated_value', price),
                        }

                        if add_lead(lead):
                            new_leads += 1
                            print(f"  ✅ New Craigslist lead: {title[:50]}...")

                        time.sleep(random.uniform(0.5, 1.5))

                    except Exception as e:
                        print(f"  ⚠️ Error processing listing: {e}")
                        continue

                time.sleep(random.uniform(2, 4))

            except Exception as e:
                print(f"  ❌ Error scraping {city}/{section_code}: {e}")
                continue

    print(f"  📊 Craigslist: {new_leads} new leads found")
    return new_leads
