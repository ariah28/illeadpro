"""
ILLeadPro - Listings Scrapers
Sources with contact info:
  - FSBO: fizber.com + fsbo.com + byowner.com (all have phone numbers)
  - HUD Foreclosures
  - BiggerPockets Illinois forum
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


def get_text(el):
    return el.get_text(strip=True) if el else ''


def find_phone(soup_or_text):
    """Extract first phone number from HTML or text."""
    text = soup_or_text if isinstance(soup_or_text, str) else str(soup_or_text)
    m = PHONE_RE.search(text)
    return m.group(1) if m else ''


# ---------------------------------------------------------------------------
# FSBO — multiple sites with contact info
# ---------------------------------------------------------------------------

def scrape_fsbo():
    """Scrape multiple FSBO sites for Illinois listings with contact info."""
    print("🔍 Scraping FSBO sites (fizber, fsbo.com, byowner, houzeo, realtor)...")
    new_leads = 0
    new_leads += _scrape_fizber()
    new_leads += _scrape_fsbo_com()
    new_leads += _scrape_byowner()
    new_leads += _scrape_houzeo()
    new_leads += _scrape_realtor_fsbo()
    print(f"  📊 FSBO: {new_leads} new leads found")
    return new_leads


def _scrape_fizber():
    """Fizber.com — FSBO listings with seller phone numbers."""
    new_leads = 0
    urls = [
        ('https://www.fizber.com/illinois/', 'Illinois'),
        ('https://www.fizber.com/chicago-illinois/', 'Chicago IL'),
    ]

    for url, area in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                print(f"  ⚠️ Fizber {area}: HTTP {resp.status_code}")
                continue

            soup = BeautifulSoup(resp.text, 'lxml')
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

                    post_text = (
                        f"FIZBER FSBO: {addr_text}. "
                        f"Price: {price_text}. {area}. "
                        f"For sale by owner — no agent."
                    )

                    lead = {
                        'name':           'FSBO Seller',
                        'phone':          phone_text,
                        'email':          '',
                        'area':           area,
                        'source':         'FSBO',
                        'type':           '🏠 Seller',
                        'score':          '🔥 Hot',
                        'post':           post_text,
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
            print(f"  ❌ Fizber error: {e}")

    return new_leads


def _scrape_fsbo_com():
    """FSBO.com — dedicated FSBO marketplace with contact info."""
    new_leads = 0
    urls = [
        ('https://www.fsbo.com/listings/il/', 'Illinois'),
        ('https://www.fsbo.com/listings/il/cook/', 'Cook County IL'),
    ]

    for url, area in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                print(f"  ⚠️ FSBO.com {area}: HTTP {resp.status_code}")
                continue

            soup = BeautifulSoup(resp.text, 'lxml')
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

                    post_text = (
                        f"FSBO.COM: {addr_text}. "
                        f"Price: {price_text}. {area}. "
                        f"For sale by owner."
                    )

                    lead = {
                        'name':           'FSBO Seller',
                        'phone':          phone_text,
                        'email':          '',
                        'area':           area,
                        'source':         'FSBO',
                        'type':           '🏠 Seller',
                        'score':          '🔥 Hot',
                        'post':           post_text,
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
    """ByOwner.com — FSBO listings for Illinois."""
    new_leads = 0
    url = 'https://www.byowner.com/illinois-homes-for-sale-by-owner.html'

    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            print(f"  ⚠️ ByOwner: HTTP {resp.status_code}")
            return 0

        soup = BeautifulSoup(resp.text, 'lxml')
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

                post_text = (
                    f"BYOWNER.COM FSBO: {addr_text}. "
                    f"Price: {price_text}. Illinois FSBO."
                )

                lead = {
                    'name':           'FSBO Seller',
                    'phone':          phone_text,
                    'email':          '',
                    'area':           addr_text,
                    'source':         'FSBO',
                    'type':           '🏠 Seller',
                    'score':          '🔥 Hot',
                    'post':           post_text,
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

    except Exception as e:
        print(f"  ❌ ByOwner error: {e}")

    return new_leads


def _scrape_houzeo():
    """Houzeo.com — FSBO/flat-fee MLS listings for Illinois with seller contact."""
    new_leads = 0
    urls = [
        ('https://www.houzeo.com/homes-for-sale/il/', 'Illinois'),
        ('https://www.houzeo.com/homes-for-sale/il/cook-county/', 'Cook County IL'),
    ]

    for url, area in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                print(f"  ⚠️ Houzeo {area}: HTTP {resp.status_code}")
                continue

            soup = BeautifulSoup(resp.text, 'lxml')
            listings = (
                soup.select('[class*="listing"]')  or
                soup.select('[class*="property"]') or
                soup.select('[class*="card"]')     or
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

                    post_text = (
                        f"HOUZEO FSBO: {addr_text}. "
                        f"Price: {price_text}. {area}. "
                        f"For sale by owner — flat-fee MLS listing."
                    )

                    lead = {
                        'name':           'FSBO Seller',
                        'phone':          phone_text,
                        'email':          '',
                        'area':           area,
                        'source':         'FSBO',
                        'type':           '🏠 Seller',
                        'score':          '🔥 Hot',
                        'post':           post_text,
                        'link':           url,
                        'reason':         'FSBO on Houzeo — selling without agent, motivated seller',
                        'estimatedValue': price_text,
                    }

                    if add_lead(lead):
                        new_leads += 1
                        print(f"  ✅ Houzeo FSBO: {addr_text[:50]}...")

                    time.sleep(random.uniform(0.3, 0.7))

                except Exception:
                    continue

            time.sleep(random.uniform(1, 2))

        except Exception as e:
            print(f"  ❌ Houzeo error: {e}")

    return new_leads


def _scrape_realtor_fsbo():
    """Realtor.com FSBO section — Illinois for-sale-by-owner listings."""
    new_leads = 0
    urls = [
        ('https://www.realtor.com/realestateandhomes-search/Illinois/type-single-family-home/sby-fsbo', 'Illinois'),
        ('https://www.realtor.com/realestateandhomes-search/Chicago_IL/type-single-family-home/sby-fsbo', 'Chicago IL'),
    ]

    for url, area in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                print(f"  ⚠️ Realtor FSBO {area}: HTTP {resp.status_code}")
                continue

            soup = BeautifulSoup(resp.text, 'lxml')
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

                    post_text = (
                        f"REALTOR.COM FSBO: {addr_text}. "
                        f"Price: {price_text}. {area}. "
                        f"For sale by owner listing."
                    )

                    lead = {
                        'name':           'FSBO Seller',
                        'phone':          phone_text,
                        'email':          '',
                        'area':           area,
                        'source':         'FSBO',
                        'type':           '🏠 Seller',
                        'score':          '🔥 Hot',
                        'post':           post_text,
                        'link':           url,
                        'reason':         'FSBO on Realtor.com — selling without agent',
                        'estimatedValue': price_text,
                    }

                    if add_lead(lead):
                        new_leads += 1
                        print(f"  ✅ Realtor FSBO: {addr_text[:50]}...")

                    time.sleep(random.uniform(0.3, 0.7))

                except Exception:
                    continue

            time.sleep(random.uniform(1, 2))

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
        "https://www.hudhomestore.gov/Listing/PropertySearchResult.aspx?sState=IL&sCity=&sZipCode=&iPage=1&sPageSize=20",
        "https://www.hudhomestore.gov/Listing/PropertySearchResult.aspx?sState=IL",
    ]

    for url in hud_urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                print(f"  ⚠️ HUD: HTTP {resp.status_code}")
                continue

            soup = BeautifulSoup(resp.text, 'lxml')
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

                    post_text = (
                        f"HUD FORECLOSURE: {address}. "
                        f"Price: {price}. Government-owned — motivated sale."
                    )

                    lead = {
                        'name':           'HUD Foreclosure',
                        'phone':          '',
                        'email':          '',
                        'area':           f"{address}, Illinois",
                        'source':         'Foreclosure',
                        'type':           '🏠 Seller',
                        'score':          '🔥 Hot',
                        'post':           post_text,
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

    # Try search API first, then forum pages
    sources = [
        "https://www.biggerpockets.com/search?utf8=%E2%9C%93&q=illinois+real+estate&commit=Search",
        "https://www.biggerpockets.com/forums/48",
        "https://www.biggerpockets.com/forums/48-illinois-real-estate",
    ]

    for url in sources:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                continue

            soup  = BeautifulSoup(resp.text, 'lxml')

            # Find post titles/threads
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
