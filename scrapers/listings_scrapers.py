"""
ILLeadPro - Listings Scrapers
Scrapes ForSaleByOwner.com, HUD Foreclosures, BiggerPockets
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

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

IL_CITIES = [
    'chicago-il', 'naperville-il', 'aurora-il', 'joliet-il',
    'evanston-il', 'schaumburg-il', 'elmhurst-il', 'oak-park-il',
    'bolingbrook-il', 'waukegan-il'
]


def scrape_fsbo():
    """Scrape ForSaleByOwner.com for Illinois listings"""
    print("🔍 Scraping ForSaleByOwner.com...")
    new_leads = 0

    for city in IL_CITIES[:5]:
        try:
            url = f"https://www.forsalebyowner.com/real-estate/{city}/"
            resp = requests.get(url, headers=HEADERS, timeout=10)

            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, 'lxml')
            listings = soup.select('.listing-card, .property-card, article.listing')

            for listing in listings[:10]:
                try:
                    title = listing.select_one('h2, h3, .listing-title')
                    price = listing.select_one('.price, .listing-price')
                    location = listing.select_one('.location, .listing-location, .address')
                    description = listing.select_one('.description, .listing-description')
                    phone = listing.select_one('.phone, .contact-phone, [href^="tel"]')
                    email_el = listing.select_one('a[href^="mailto"]')

                    title_text = title.text.strip() if title else 'FSBO Illinois'
                    price_text = price.text.strip() if price else ''
                    loc_text = location.text.strip() if location else city.replace('-', ' ').title()
                    desc_text = description.text.strip()[:300] if description else ''
                    phone_text = phone.text.strip() if phone else ''
                    email_text = email_el.get('href', '').replace('mailto:', '') if email_el else ''

                    post_text = (
                        f"FOR SALE BY OWNER: {title_text}. "
                        f"Price: {price_text}. Location: {loc_text}. {desc_text}"
                    )

                    analysis = score_lead(post_text, 'ForSaleByOwner', loc_text)

                    if not analysis.get('is_real_estate_lead'):
                        continue

                    lead = {
                        'name': 'FSBO Seller',
                        'phone': phone_text,
                        'email': email_text,
                        'area': loc_text,
                        'source': 'FSBO',
                        'type': '🏠 Seller',
                        'score': analysis.get('score', '🔥 Hot'),
                        'post': post_text,
                        'link': url,
                        'reason': 'For Sale By Owner - actively selling without agent',
                        'estimatedValue': price_text,
                    }

                    if add_lead(lead):
                        new_leads += 1
                        print(f"  ✅ New FSBO lead: {title_text[:50]}...")

                    time.sleep(random.uniform(0.5, 1))

                except Exception:
                    continue

            time.sleep(random.uniform(2, 3))

        except Exception as e:
            print(f"  ❌ FSBO error for {city}: {e}")
            continue

    print(f"  📊 FSBO: {new_leads} new leads found")
    return new_leads


def scrape_foreclosures():
    """Scrape HUD public foreclosure listings for Illinois"""
    print("🔍 Scraping HUD Foreclosure listings...")
    new_leads = 0

    try:
        url = "https://www.hudhomestore.gov/Listing/PropertySearchResult.aspx"
        params = {'sState': 'IL', 'sCity': '', 'sZip': '', 'iPage': 1}

        resp = requests.get(url, headers=HEADERS, params=params, timeout=10)

        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'lxml')
            listings = soup.select('.property-result, tr.listing-row, .hud-property')

            for listing in listings[:15]:
                try:
                    address = listing.select_one('.address, td:first-child')
                    price = listing.select_one('.price, .list-price')

                    if not address:
                        continue

                    addr_text = address.text.strip()
                    price_text = price.text.strip() if price else 'Price TBD'

                    post_text = (
                        f"HUD FORECLOSURE: {addr_text}. "
                        f"Listed at: {price_text}. "
                        f"Motivated bank seller, Illinois property."
                    )

                    lead = {
                        'name': 'HUD/Bank Foreclosure',
                        'phone': '',
                        'email': '',
                        'area': addr_text,
                        'source': 'Foreclosure',
                        'type': '🏠 Seller',
                        'score': '🔥 Hot',
                        'post': post_text,
                        'link': url,
                        'reason': 'Foreclosure listing - bank motivated to sell fast',
                        'estimatedValue': price_text,
                    }

                    if add_lead(lead):
                        new_leads += 1
                        print(f"  ✅ New foreclosure lead: {addr_text[:50]}...")

                except Exception:
                    continue

    except Exception as e:
        print(f"  ❌ Foreclosure scraper error: {e}")

    print(f"  📊 Foreclosures: {new_leads} new leads found")
    return new_leads


def scrape_biggerpockets():
    """Scrape BiggerPockets forums for Illinois investor leads"""
    print("🔍 Scraping BiggerPockets...")
    new_leads = 0

    try:
        url = "https://www.biggerpockets.com/forums/search"
        params = {'utf8': '✓', 'q': 'illinois chicago buy sell', 'commit': 'Search'}

        resp = requests.get(url, headers=HEADERS, params=params, timeout=10)

        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'lxml')
            posts = soup.select('.forum-post, .discussion-item, article.post')

            for post in posts[:10]:
                try:
                    title = post.select_one('h2, h3, .post-title')
                    body = post.select_one('.post-body, .content, p')
                    author = post.select_one('.author, .username')

                    if not title:
                        continue

                    title_text = title.text.strip()
                    body_text = body.text.strip()[:300] if body else ''
                    author_text = author.text.strip() if author else 'BiggerPockets User'

                    combined = (title_text + body_text).lower()
                    if not any(t in combined for t in ['illinois', 'chicago', 'il ']):
                        continue

                    post_text = f"{title_text}\n{body_text}"
                    analysis = score_lead(post_text, 'BiggerPockets', 'Illinois')

                    if not analysis.get('is_real_estate_lead'):
                        continue

                    lead = {
                        'name': author_text,
                        'phone': '',
                        'email': '',
                        'area': 'Illinois',
                        'source': 'BiggerPockets',
                        'type': analysis.get('type', '🏢 Investor'),
                        'score': analysis.get('score', '⚡ Warm'),
                        'post': post_text,
                        'link': 'https://biggerpockets.com/forums',
                        'reason': analysis.get('reason', 'Real estate investor forum'),
                        'estimatedValue': analysis.get('estimated_value', ''),
                    }

                    if add_lead(lead):
                        new_leads += 1
                        print(f"  ✅ New BiggerPockets lead: {title_text[:50]}...")

                    time.sleep(1)

                except Exception:
                    continue

    except Exception as e:
        print(f"  ❌ BiggerPockets error: {e}")

    print(f"  📊 BiggerPockets: {new_leads} new leads found")
    return new_leads
