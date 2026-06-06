"""
ILLeadPro - Listings Scrapers
Sources with contact info:
  - FSBO: fizber.com + fsbo.com + byowner.com (JSON-LD extraction for JS-rendered sites)
  - Realtor.com FSBO (with rate-limit protection)
  - HUD Foreclosures
  - BiggerPockets Illinois forum
"""
import sys
import os
import re
import time
import json
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
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept':          'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection':      'keep-alive',
}

PHONE_RE = re.compile(
    r'(\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4})'
)

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
]


def get_text(el):
    return el.get_text(strip=True) if el else ''


def find_phone(soup_or_text):
    """Extract first phone number from HTML or text."""
    text = soup_or_text if isinstance(soup_or_text, str) else str(soup_or_text)
    m = PHONE_RE.search(text)
    return m.group(1) if m else ''


def rand_headers():
    """Return headers with a random User-Agent to avoid rate limits."""
    h = dict(HEADERS)
    h['User-Agent'] = random.choice(USER_AGENTS)
    return h


def extract_jsonld(soup):
    """
    Extract RealEstateListing / Product schema from JSON-LD <script> tags.
    Many listing sites embed this even when the visual content is JavaScript-rendered.
    Returns list of dicts with keys: addr, phone, price.
    """
    results = []
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            raw = script.string or ''
            data = json.loads(raw)
            items = data if isinstance(data, list) else [data]
            for item in items:
                t = str(item.get('@type', ''))
                if not any(k in t for k in ['RealEstate', 'House', 'Residence', 'Property', 'Product']):
                    continue
                # Extract address
                addr_raw = item.get('address', '')
                if isinstance(addr_raw, dict):
                    addr_str = ' '.join(filter(None, [
                        addr_raw.get('streetAddress', ''),
                        addr_raw.get('addressLocality', ''),
                        addr_raw.get('addressRegion', ''),
                        addr_raw.get('postalCode', ''),
                    ]))
                else:
                    addr_str = str(addr_raw)

                # Extract phone
                phone = (item.get('telephone', '') or
                         item.get('phone', '') or
                         find_phone(raw))

                # Extract price
                price = ''
                offers = item.get('offers', {})
                if isinstance(offers, dict):
                    price = str(offers.get('price', ''))
                elif isinstance(offers, list) and offers:
                    price = str(offers[0].get('price', ''))
                if not price:
                    price = str(item.get('price', ''))

                if addr_str and len(addr_str) > 5:
                    results.append({'addr': addr_str, 'phone': phone, 'price': price})
        except Exception:
            continue
    return results


# ---------------------------------------------------------------------------
# FSBO — multiple sites with contact info
# ---------------------------------------------------------------------------

def scrape_fsbo():
    """Scrape multiple FSBO sites for Illinois listings with contact info."""
    print("🔍 Scraping FSBO sites (fizber, fsbo.com, byowner, realtor)...")
    new_leads = 0
    new_leads += _scrape_fizber()
    new_leads += _scrape_fsbo_com()
    new_leads += _scrape_byowner()
    new_leads += _scrape_realtor_fsbo()
    print(f"  📊 FSBO: {new_leads} new leads found")
    return new_leads


def _scrape_fizber():
    """Fizber.com — FSBO listings. Uses JSON-LD fallback for JS-rendered pages."""
    new_leads = 0
    urls = [
        ('https://www.fizber.com/illinois/', 'Illinois'),
        ('https://www.fizber.com/illinois/chicago/', 'Chicago IL'),
        ('https://www.fizber.com/illinois/cook-county/', 'Cook County IL'),
    ]

    for url, area in urls:
        try:
            resp = requests.get(url, headers=rand_headers(), timeout=12)
            if resp.status_code != 200:
                print(f"  ⚠️ Fizber {area}: HTTP {resp.status_code}")
                continue

            soup = BeautifulSoup(resp.text, 'lxml')

            # Strategy 1: JSON-LD structured data (works even on JS-rendered pages)
            jsonld_items = extract_jsonld(soup)
            for item in jsonld_items[:12]:
                try:
                    addr_text  = item['addr']
                    price_text = item['price']
                    phone_text = item['phone']

                    if len(addr_text) < 5:
                        continue

                    lead = {
                        'name':           'FSBO Seller',
                        'phone':          phone_text,
                        'email':          '',
                        'area':           area,
                        'source':         'FSBO',
                        'type':           '🏠 Seller',
                        'score':          '🔥 Hot',
                        'post':           f"FIZBER FSBO: {addr_text}. Price: {price_text}. {area}. For sale by owner — no agent.",
                        'link':           url,
                        'reason':         'FSBO on Fizber — selling without agent, motivated seller',
                        'estimatedValue': price_text,
                    }
                    if add_lead(lead):
                        new_leads += 1
                        print(f"  ✅ Fizber FSBO (JSON-LD): {addr_text[:50]}...")
                except Exception:
                    continue

            # Strategy 2: HTML selectors (for static pages)
            if not jsonld_items:
                listings = (
                    soup.select('.listing-item')       or
                    soup.select('.property-item')      or
                    soup.select('[class*="listing"]')  or
                    soup.select('[class*="property"]') or
                    soup.select('article')
                )[:12]

                for listing in listings:
                    try:
                        addr_el  = (listing.select_one('[class*="address"]') or
                                    listing.select_one('h2, h3, h4'))
                        price_el = listing.select_one('[class*="price"]')
                        phone_el = listing.select_one('[href^="tel"]')

                        addr_text  = get_text(addr_el)
                        price_text = get_text(price_el)
                        phone_text = (phone_el['href'].replace('tel:', '')
                                      if phone_el and phone_el.get('href')
                                      else find_phone(listing))

                        if len(addr_text) < 5:
                            continue

                        lead = {
                            'name':           'FSBO Seller',
                            'phone':          phone_text,
                            'email':          '',
                            'area':           area,
                            'source':         'FSBO',
                            'type':           '🏠 Seller',
                            'score':          '🔥 Hot',
                            'post':           f"FIZBER FSBO: {addr_text}. Price: {price_text}. {area}. For sale by owner — no agent.",
                            'link':           url,
                            'reason':         'FSBO on Fizber — selling without agent, motivated seller',
                            'estimatedValue': price_text,
                        }
                        if add_lead(lead):
                            new_leads += 1
                            print(f"  ✅ Fizber FSBO: {addr_text[:50]}...")
                        time.sleep(random.uniform(0.3, 0.7))
                    except Exception:
                        continue

            time.sleep(random.uniform(1, 2))

        except Exception as e:
            print(f"  ❌ Fizber error ({area}): {e}")

    return new_leads


def _scrape_fsbo_com():
    """FSBO.com — dedicated FSBO marketplace. Uses JSON-LD fallback."""
    new_leads = 0
    urls = [
        ('https://www.fsbo.com/listings/il/', 'Illinois'),
        ('https://www.fsbo.com/listings/il/cook/', 'Cook County IL'),
        ('https://www.fsbo.com/listings/il/chicago/', 'Chicago IL'),
    ]

    for url, area in urls:
        try:
            resp = requests.get(url, headers=rand_headers(), timeout=12)
            if resp.status_code != 200:
                print(f"  ⚠️ FSBO.com {area}: HTTP {resp.status_code}")
                continue

            soup = BeautifulSoup(resp.text, 'lxml')

            # Strategy 1: JSON-LD
            jsonld_items = extract_jsonld(soup)
            for item in jsonld_items[:12]:
                try:
                    addr_text  = item['addr']
                    price_text = item['price']
                    phone_text = item['phone']
                    if len(addr_text) < 5:
                        continue
                    lead = {
                        'name':           'FSBO Seller',
                        'phone':          phone_text,
                        'email':          '',
                        'area':           area,
                        'source':         'FSBO',
                        'type':           '🏠 Seller',
                        'score':          '🔥 Hot',
                        'post':           f"FSBO.COM: {addr_text}. Price: {price_text}. {area}. For sale by owner.",
                        'link':           url,
                        'reason':         'FSBO on FSBO.com — motivated seller, no agent',
                        'estimatedValue': price_text,
                    }
                    if add_lead(lead):
                        new_leads += 1
                        print(f"  ✅ FSBO.com (JSON-LD): {addr_text[:50]}...")
                except Exception:
                    continue

            # Strategy 2: HTML selectors
            if not jsonld_items:
                listings = (
                    soup.select('.listing')            or
                    soup.select('.property')           or
                    soup.select('[class*="listing"]')  or
                    soup.select('[class*="property"]') or
                    soup.select('article')
                )[:12]

                for listing in listings:
                    try:
                        addr_el  = (listing.select_one('[class*="address"]') or
                                    listing.select_one('[class*="location"]') or
                                    listing.select_one('h2, h3, h4'))
                        price_el = listing.select_one('[class*="price"]')
                        phone_el = listing.select_one('[href^="tel"]')

                        addr_text  = get_text(addr_el)
                        price_text = get_text(price_el)
                        phone_text = (phone_el['href'].replace('tel:', '')
                                      if phone_el and phone_el.get('href')
                                      else find_phone(listing))

                        if len(addr_text) < 5:
                            continue

                        lead = {
                            'name':           'FSBO Seller',
                            'phone':          phone_text,
                            'email':          '',
                            'area':           area,
                            'source':         'FSBO',
                            'type':           '🏠 Seller',
                            'score':          '🔥 Hot',
                            'post':           f"FSBO.COM: {addr_text}. Price: {price_text}. {area}. For sale by owner.",
                            'link':           url,
                            'reason':         'FSBO on FSBO.com — motivated seller, no agent',
                            'estimatedValue': price_text,
                        }
                        if add_lead(lead):
                            new_leads += 1
                            print(f"  ✅ FSBO.com: {addr_text[:50]}...")
                        time.sleep(random.uniform(0.3, 0.7))
                    except Exception:
                        continue

            time.sleep(random.uniform(1, 2))

        except Exception as e:
            print(f"  ❌ FSBO.com error: {e}")

    return new_leads


def _scrape_byowner():
    """ByOwner.com — FSBO listings for Illinois. Tries multiple URL patterns."""
    new_leads = 0
    candidate_urls = [
        'https://www.byowner.com/illinois-homes-for-sale-by-owner.html',
        'https://www.byowner.com/real-estate/illinois/',
        'https://www.byowner.com/homes/illinois/',
        'https://www.byowner.com/sell/fsbo/illinois/',
        'https://www.byowner.com/for-sale/illinois/',
    ]

    for url in candidate_urls:
        try:
            resp = requests.get(url, headers=rand_headers(), timeout=12)
            if resp.status_code == 404:
                continue  # Try next URL silently
            if resp.status_code != 200:
                print(f"  ⚠️ ByOwner ({url}): HTTP {resp.status_code}")
                continue

            soup = BeautifulSoup(resp.text, 'lxml')

            # JSON-LD first
            jsonld_items = extract_jsonld(soup)
            for item in jsonld_items[:12]:
                try:
                    addr_text  = item['addr']
                    price_text = item['price']
                    phone_text = item['phone']
                    if len(addr_text) < 5:
                        continue
                    lead = {
                        'name':           'FSBO Seller',
                        'phone':          phone_text,
                        'email':          '',
                        'area':           addr_text,
                        'source':         'FSBO',
                        'type':           '🏠 Seller',
                        'score':          '🔥 Hot',
                        'post':           f"BYOWNER.COM FSBO: {addr_text}. Price: {price_text}. Illinois FSBO.",
                        'link':           url,
                        'reason':         'FSBO on ByOwner — selling without agent',
                        'estimatedValue': price_text,
                    }
                    if add_lead(lead):
                        new_leads += 1
                        print(f"  ✅ ByOwner FSBO (JSON-LD): {addr_text[:50]}...")
                except Exception:
                    continue

            # HTML fallback
            if not jsonld_items:
                listings = (
                    soup.select('.listing-item')       or
                    soup.select('[class*="listing"]')  or
                    soup.select('[class*="property"]') or
                    soup.select('article')
                )[:12]

                for listing in listings:
                    try:
                        addr_el  = (listing.select_one('[class*="address"]') or
                                    listing.select_one('h2, h3, h4'))
                        price_el = listing.select_one('[class*="price"]')
                        phone_el = listing.select_one('[href^="tel"]')

                        addr_text  = get_text(addr_el)
                        price_text = get_text(price_el)
                        phone_text = (phone_el['href'].replace('tel:', '')
                                      if phone_el and phone_el.get('href')
                                      else find_phone(listing))

                        if len(addr_text) < 5:
                            continue

                        lead = {
                            'name':           'FSBO Seller',
                            'phone':          phone_text,
                            'email':          '',
                            'area':           addr_text,
                            'source':         'FSBO',
                            'type':           '🏠 Seller',
                            'score':          '🔥 Hot',
                            'post':           f"BYOWNER.COM FSBO: {addr_text}. Price: {price_text}. Illinois FSBO.",
                            'link':           url,
                            'reason':         'FSBO on ByOwner — selling without agent',
                            'estimatedValue': price_text,
                        }
                        if add_lead(lead):
                            new_leads += 1
                            print(f"  ✅ ByOwner FSBO: {addr_text[:50]}...")
                        time.sleep(random.uniform(0.3, 0.7))
                    except Exception:
                        continue

            # Found a working URL — stop trying others
            if new_leads > 0 or jsonld_items or listings:
                break

        except Exception as e:
            print(f"  ❌ ByOwner error: {e}")
            continue

    return new_leads


def _scrape_realtor_fsbo():
    """Realtor.com FSBO — with rate-limit protection (30s+ delays)."""
    new_leads = 0
    urls = [
        ('https://www.realtor.com/realestateandhomes-search/Illinois/type-single-family-home/sby-fsbo', 'Illinois'),
        ('https://www.realtor.com/realestateandhomes-search/Chicago_IL/type-single-family-home/sby-fsbo', 'Chicago IL'),
    ]

    for url, area in urls:
        try:
            # Long delay to avoid 429 rate limit
            time.sleep(random.uniform(30, 45))

            resp = requests.get(url, headers=rand_headers(), timeout=20)
            if resp.status_code == 429:
                print(f"  ⚠️ Realtor FSBO {area}: rate limited (429) — skipping")
                time.sleep(60)
                continue
            if resp.status_code != 200:
                print(f"  ⚠️ Realtor FSBO {area}: HTTP {resp.status_code}")
                continue

            soup = BeautifulSoup(resp.text, 'lxml')

            # JSON-LD first
            jsonld_items = extract_jsonld(soup)
            for item in jsonld_items[:12]:
                try:
                    addr_text  = item['addr']
                    price_text = item['price']
                    phone_text = item['phone']
                    if len(addr_text) < 5:
                        continue
                    lead = {
                        'name':           'FSBO Seller',
                        'phone':          phone_text,
                        'email':          '',
                        'area':           area,
                        'source':         'FSBO',
                        'type':           '🏠 Seller',
                        'score':          '🔥 Hot',
                        'post':           f"REALTOR.COM FSBO: {addr_text}. Price: {price_text}. {area}. For sale by owner.",
                        'link':           url,
                        'reason':         'FSBO on Realtor.com — selling without agent',
                        'estimatedValue': price_text,
                    }
                    if add_lead(lead):
                        new_leads += 1
                        print(f"  ✅ Realtor FSBO (JSON-LD): {addr_text[:50]}...")
                except Exception:
                    continue

            # HTML fallback
            if not jsonld_items:
                listings = (
                    soup.select('[data-testid*="property"]') or
                    soup.select('[class*="PropertyCard"]')   or
                    soup.select('[class*="listing"]')        or
                    soup.select('[class*="property"]')       or
                    soup.select('article')
                )[:12]

                for listing in listings:
                    try:
                        addr_el  = (listing.select_one('[data-testid*="address"]') or
                                    listing.select_one('[class*="address"]')        or
                                    listing.select_one('h2, h3, h4'))
                        price_el = (listing.select_one('[data-testid*="price"]') or
                                    listing.select_one('[class*="price"]'))
                        phone_el = listing.select_one('[href^="tel"]')

                        addr_text  = get_text(addr_el)
                        price_text = get_text(price_el)
                        phone_text = (phone_el['href'].replace('tel:', '')
                                      if phone_el and phone_el.get('href')
                                      else find_phone(listing))

                        if len(addr_text) < 5:
                            continue

                        lead = {
                            'name':           'FSBO Seller',
                            'phone':          phone_text,
                            'email':          '',
                            'area':           area,
                            'source':         'FSBO',
                            'type':           '🏠 Seller',
                            'score':          '🔥 Hot',
                            'post':           f"REALTOR.COM FSBO: {addr_text}. Price: {price_text}. {area}. For sale by owner.",
                            'link':           url,
                            'reason':         'FSBO on Realtor.com — selling without agent',
                            'estimatedValue': price_text,
                        }
                        if add_lead(lead):
                            new_leads += 1
                            print(f"  ✅ Realtor FSBO: {addr_text[:50]}...")
                        time.sleep(random.uniform(2, 4))
                    except Exception:
                        continue

        except Exception as e:
            print(f"  ❌ Realtor FSBO error: {e}")

    return new_leads


# ---------------------------------------------------------------------------
# HUD Foreclosures
# ---------------------------------------------------------------------------

def scrape_foreclosures():
    """Scrape HUD foreclosure listings for Illinois."""
    print("🔍 Scraping HUD Foreclosure listings...")
    new_leads = 0

    hud_urls = [
        "https://www.hudhomestore.gov/Listing/PropertySearchResult.aspx?sState=IL&sCity=&sZipCode=&iPage=1&sPageSize=20&sHudHomeType=&sPriceRange=&sBedrooms=&sBathrooms=&sSquareFootage=&sLotSize=&sGarageSize=&sYearBuilt=&sPropertyStatus=A",
        "https://www.hudhomestore.gov/Home/Index",
        "https://www.hudhomestore.gov/listing/propertyresult.aspx",
    ]

    for url in hud_urls:
        try:
            resp = requests.get(url, headers=rand_headers(), timeout=15)
            if resp.status_code != 200:
                print(f"  ⚠️ HUD ({url[-30:]}): HTTP {resp.status_code}")
                continue

            soup = BeautifulSoup(resp.text, 'lxml')

            # Try JSON-LD first
            jsonld_items = extract_jsonld(soup)
            for item in jsonld_items[:15]:
                try:
                    addr_text  = item['addr']
                    price_text = item['price']
                    if not addr_text or len(addr_text) < 5:
                        continue
                    lead = {
                        'name':           'HUD Foreclosure',
                        'phone':          '',
                        'email':          '',
                        'area':           f"{addr_text}, Illinois",
                        'source':         'Foreclosure',
                        'type':           '🏠 Seller',
                        'score':          '🔥 Hot',
                        'post':           f"HUD FORECLOSURE: {addr_text}. Price: {price_text}. Government-owned — motivated sale.",
                        'link':           url,
                        'reason':         'HUD government foreclosure — must sell',
                        'estimatedValue': price_text,
                    }
                    if add_lead(lead):
                        new_leads += 1
                        print(f"  ✅ HUD (JSON-LD): {addr_text[:50]}...")
                except Exception:
                    continue

            # HTML table fallback
            rows = (
                soup.select('table tr')[1:] or
                soup.select('.property-result') or
                soup.select('[class*="listing"]')
            )

            for row in rows[:15]:
                try:
                    cols = row.select('td')
                    if len(cols) < 2:
                        continue

                    address = cols[0].get_text(strip=True)
                    price   = cols[2].get_text(strip=True) if len(cols) > 2 else ''

                    if not address or len(address) < 5:
                        continue

                    lead = {
                        'name':           'HUD Foreclosure',
                        'phone':          '',
                        'email':          '',
                        'area':           f"{address}, Illinois",
                        'source':         'Foreclosure',
                        'type':           '🏠 Seller',
                        'score':          '🔥 Hot',
                        'post':           f"HUD FORECLOSURE: {address}. Price: {price}. Government-owned — motivated sale.",
                        'link':           url,
                        'reason':         'HUD government foreclosure — must sell',
                        'estimatedValue': price,
                    }

                    if add_lead(lead):
                        new_leads += 1
                        print(f"  ✅ HUD: {address[:50]}...")

                except Exception:
                    continue

            if new_leads > 0:
                break

        except Exception as e:
            print(f"  ❌ HUD error: {e}")

    print(f"  📊 Foreclosures: {new_leads} new leads found")
    return new_leads


# ---------------------------------------------------------------------------
# BiggerPockets — Illinois investor forum
# ---------------------------------------------------------------------------

def scrape_biggerpockets():
    """Scrape BiggerPockets for Illinois real estate investor leads."""
    print("🔍 Scraping BiggerPockets Illinois...")
    new_leads = 0

    sources = [
        "https://www.biggerpockets.com/search?utf8=%E2%9C%93&q=illinois+real+estate&commit=Search",
        "https://www.biggerpockets.com/forums/48",
        "https://www.biggerpockets.com/forums/48-illinois-real-estate",
    ]

    for url in sources:
        try:
            resp = requests.get(url, headers=rand_headers(), timeout=15)
            if resp.status_code != 200:
                continue

            soup  = BeautifulSoup(resp.text, 'lxml')

            posts = (
                soup.select('[class*="discussion"]') or
                soup.select('[class*="thread"]')     or
                soup.select('[class*="post"]')       or
                soup.select('[class*="result"]')     or
                soup.select('article')               or
                soup.select('li')
            )[:15]

            found = 0
            for post in posts:
                try:
                    title_el  = (post.select_one('h2') or post.select_one('h3') or
                                 post.select_one('[class*="title"]') or
                                 post.select_one('a'))
                    author_el = post.select_one('[class*="author"]') or post.select_one('[class*="user"]')

                    if not title_el:
                        continue

                    title_text  = get_text(title_el)
                    author_text = get_text(author_el) or 'BP Investor'
                    body_text   = post.get_text(separator=' ', strip=True)[:400]

                    combined = (title_text + body_text).lower()
                    if not any(t in combined for t in ['illinois', 'chicago', ' il ', 'naperville', 'cook county']):
                        continue
                    if len(title_text) < 10:
                        continue

                    analysis = score_lead(title_text + ' ' + body_text[:200], 'BiggerPockets', 'Illinois')
                    if not analysis.get('is_real_estate_lead'):
                        continue

                    link_el = title_el if title_el.name == 'a' else title_el.find('a')
                    link    = (f"https://www.biggerpockets.com{link_el['href']}"
                               if link_el and link_el.get('href', '').startswith('/') else url)

                    lead = {
                        'name':           author_text,
                        'phone':          '',
                        'email':          '',
                        'area':           'Illinois',
                        'source':         'BiggerPockets',
                        'type':           analysis.get('type', '🏢 Investor'),
                        'score':          analysis.get('score', '⚡ Warm'),
                        'post':           (title_text + '\n' + body_text)[:400],
                        'link':           link,
                        'reason':         analysis.get('reason', 'IL real estate investor forum post'),
                        'estimatedValue': analysis.get('estimated_value', ''),
                    }

                    if add_lead(lead):
                        new_leads += 1
                        found += 1
                        print(f"  ✅ BP lead: {title_text[:50]}...")

                    time.sleep(0.5)

                except Exception:
                    continue

            if found > 0:
                break

            time.sleep(2)

        except Exception as e:
            print(f"  ❌ BiggerPockets error: {e}")
            continue

    print(f"  📊 BiggerPockets: {new_leads} new leads found")
    return new_leads
