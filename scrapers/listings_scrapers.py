"""
ILLeadPro - Listings Scrapers (FIXED)
Changes:
  - FSBO: Multi-selector fallback strategy instead of single guessed selectors
  - HUD Foreclosures: BUG FIXED — was parsing data but never creating leads
  - BiggerPockets: Targets Illinois forum (#48) directly; multi-selector fallback
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
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/121.0.0.0 Safari/537.36'
    ),
    'Accept':          'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'Connection':      'keep-alive',
}

IL_CITIES = [
    'chicago-il', 'naperville-il', 'aurora-il', 'joliet-il',
    'evanston-il', 'schaumburg-il', 'elmhurst-il', 'oak-park-il',
]


def get_text(el):
    return el.get_text(strip=True) if el else ''


# ---------------------------------------------------------------------------
# FSBO
# ---------------------------------------------------------------------------

def scrape_fsbo():
    """Scrape ForSaleByOwner.com for Illinois listings."""
    print("🔍 Scraping ForSaleByOwner.com...")
    new_leads = 0

    for city in IL_CITIES[:5]:
        try:
            url  = f"https://www.forsalebyowner.com/real-estate/{city}/"
            resp = requests.get(url, headers=HEADERS, timeout=12)

            if resp.status_code != 200:
                print(f"  ⚠️ FSBO {city}: HTTP {resp.status_code}")
                continue

            soup = BeautifulSoup(resp.text, 'lxml')

            # Try selectors from most-specific to broadest fallback
            listings = (
                soup.select('.listing-card')              or
                soup.select('.property-card')             or
                soup.select('article.listing')            or
                soup.select('[data-testid="listing-card"]') or
                soup.select('[class*="listing"]')         or
                soup.select('[class*="property"]')
            )[:10]

            for listing in listings:
                try:
                    title_el = (
                        listing.select_one('h2')              or
                        listing.select_one('h3')              or
                        listing.select_one('[class*="title"]')   or
                        listing.select_one('[class*="address"]') or
                        listing.select_one('a')
                    )
                    price_el = (
                        listing.select_one('[class*="price"]') or
                        listing.select_one('[class*="Price"]')
                    )
                    loc_el = (
                        listing.select_one('[class*="location"]') or
                        listing.select_one('[class*="city"]')     or
                        listing.select_one('[class*="address"]')
                    )
                    phone_el = listing.select_one('[href^="tel"]')
                    email_el = listing.select_one('[href^="mailto"]')

                    title_text = get_text(title_el) or 'FSBO Illinois'
                    price_text = get_text(price_el)
                    loc_text   = get_text(loc_el) or city.replace('-', ' ').title()
                    phone_text = (phone_el['href'].replace('tel:', '')
                                  if phone_el and phone_el.get('href') else '')
                    email_text = (email_el['href'].replace('mailto:', '')
                                  if email_el and email_el.get('href') else '')

                    if len(title_text) < 3:
                        continue

                    post_text = (
                        f"FOR SALE BY OWNER: {title_text}. "
                        f"Price: {price_text}. Location: {loc_text}."
                    )
                    analysis = score_lead(post_text, 'ForSaleByOwner', loc_text)

                    if not analysis.get('is_real_estate_lead'):
                        continue

                    lead = {
                        'name':           'FSBO Seller',
                        'phone':          phone_text,
                        'email':          email_text,
                        'area':           loc_text,
                        'source':         'FSBO',
                        'type':           '🏠 Seller',
                        'score':          analysis.get('score', '🔥 Hot'),
                        'post':           post_text,
                        'link':           url,
                        'reason':         'For Sale By Owner — selling without an agent',
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


# ---------------------------------------------------------------------------
# HUD Foreclosures — BUG FIX: was parsing rows but never creating leads
# ---------------------------------------------------------------------------

def scrape_foreclosures():
    """Scrape HUD foreclosure listings for Illinois."""
    print("🔍 Scraping HUD Foreclosure listings...")
    new_leads = 0

    try:
        url    = "https://www.hudhomestore.gov/Listing/PropertySearchResult.aspx"
        params = {'sState': 'IL', 'sCity': '', 'sZip': '', 'iPage': 1}
        resp   = requests.get(url, headers=HEADERS, params=params, timeout=12)

        if resp.status_code != 200:
            print(f"  ⚠️ HUD site returned HTTP {resp.status_code}")
        else:
            soup = BeautifulSoup(resp.text, 'lxml')
            rows = (
                soup.select('table.grid tr')    or
                soup.select('.property-result') or
                soup.select('tr.listing-row')   or
                soup.select('table tr')[1:]        # skip header row
            )

            for row in rows[:15]:
                try:
                    cols = row.select('td')
                    if len(cols) < 2:
                        continue

                    address  = cols[0].get_text(strip=True)
                    case_num = cols[1].get_text(strip=True) if len(cols) > 1 else ''
                    price    = cols[2].get_text(strip=True) if len(cols) > 2 else ''

                    if not address or len(address) < 5:
                        continue

                    post_text = (
                        f"HUD FORECLOSURE: Property at {address}. "
                        f"Case: {case_num}. List Price: {price}. "
                        f"Government-owned foreclosure — motivated sale."
                    )

                    # ✅ FIX: lead dict and add_lead() call were missing
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
                        'reason':         'HUD government foreclosure — price reduced, must sell',
                        'estimatedValue': price,
                    }

                    if add_lead(lead):
                        new_leads += 1
                        print(f"  ✅ New HUD foreclosure: {address[:50]}...")

                except Exception:
                    continue

    except Exception as e:
        print(f"  ❌ HUD scraper error: {e}")

    # Backup: RealtyTrac public listings
    if new_leads == 0:
        try:
            rt_url  = "https://www.realtytrac.com/mapsearch/il/foreclosure/"
            rt_resp = requests.get(rt_url, headers=HEADERS, timeout=10)
            if rt_resp.status_code == 200:
                soup     = BeautifulSoup(rt_resp.text, 'lxml')
                listings = (
                    soup.select('.property-listing') or
                    soup.select('[class*="property"]') or
                    soup.select('article')
                )[:10]

                for listing in listings:
                    try:
                        addr  = (listing.select_one('[class*="address"]') or
                                 listing.select_one('h2, h3'))
                        price = listing.select_one('[class*="price"]')
                        if not addr:
                            continue
                        addr_text  = addr.get_text(strip=True)
                        price_text = price.get_text(strip=True) if price else ''
                        post_text  = (
                            f"FORECLOSURE: {addr_text}. {price_text}. "
                            f"Pre-foreclosure / bank owned."
                        )
                        lead = {
                            'name':           'Foreclosure Property',
                            'phone':          '',
                            'email':          '',
                            'area':           f"{addr_text}, Illinois",
                            'source':         'Foreclosure',
                            'type':           '🏠 Seller',
                            'score':          '🔥 Hot',
                            'post':           post_text,
                            'link':           rt_url,
                            'reason':         'Foreclosure listing — distressed sale',
                            'estimatedValue': price_text,
                        }
                        if add_lead(lead):
                            new_leads += 1
                            print(f"  ✅ RealtyTrac foreclosure: {addr_text[:50]}...")
                    except Exception:
                        continue
        except Exception:
            pass

    print(f"  📊 Foreclosures: {new_leads} new leads found")
    return new_leads


# ---------------------------------------------------------------------------
# BiggerPockets — target Illinois forum directly
# ---------------------------------------------------------------------------

def scrape_biggerpockets():
    """Scrape BiggerPockets Illinois forum for investor leads."""
    print("🔍 Scraping BiggerPockets Illinois forum...")
    new_leads = 0

    forum_urls = [
        "https://www.biggerpockets.com/forums/48",
        "https://www.biggerpockets.com/forums/48-illinois-real-estate",
    ]

    for url in forum_urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                continue

            soup  = BeautifulSoup(resp.text, 'lxml')
            posts = (
                soup.select('.discussion-list-item') or
                soup.select('.forum-post')           or
                soup.select('[class*="discussion"]') or
                soup.select('[class*="thread"]')     or
                soup.select('article')
            )[:10]

            for post in posts:
                try:
                    title_el = (
                        post.select_one('h2')                   or
                        post.select_one('h3')                   or
                        post.select_one('[class*="title"]')     or
                        post.select_one('a[href*="forum"]')
                    )
                    body_el   = post.select_one(
                        '[class*="body"], [class*="content"], p'
                    )
                    author_el = post.select_one(
                        '[class*="author"], [class*="user"]'
                    )

                    if not title_el:
                        continue

                    title_text  = get_text(title_el)
                    body_text   = get_text(body_el)[:300]
                    author_text = get_text(author_el) or 'BP User'

                    post_text = f"{title_text}\n{body_text}"
                    combined  = post_text.lower()

                    if not any(t in combined for t in
                               ['illinois', 'chicago', 'naperville', ' il ']):
                        continue

                    analysis = score_lead(post_text, 'BiggerPockets', 'Illinois')
                    if not analysis.get('is_real_estate_lead'):
                        continue

                    # Try to get post-specific link
                    link_el = (title_el if title_el.name == 'a'
                               else title_el.find('a'))
                    link = (f"https://biggerpockets.com{link_el['href']}"
                            if link_el and link_el.get('href') else url)

                    lead = {
                        'name':           author_text,
                        'phone':          '',
                        'email':          '',
                        'area':           'Illinois',
                        'source':         'BiggerPockets',
                        'type':           analysis.get('type', '🏢 Investor'),
                        'score':          analysis.get('score', '⚡ Warm'),
                        'post':           post_text[:400],
                        'link':           link,
                        'reason':         analysis.get('reason', 'RE investor forum post'),
                        'estimatedValue': analysis.get('estimated_value', ''),
                    }

                    if add_lead(lead):
                        new_leads += 1
                        print(f"  ✅ New BP lead: {title_text[:50]}...")

                    time.sleep(1)

                except Exception:
                    continue

            if posts:
                break  # Got content from this URL; no need to try next

            time.sleep(2)

        except Exception as e:
            print(f"  ❌ BiggerPockets error: {e}")
            continue

    print(f"  📊 BiggerPockets: {new_leads} new leads found")
    return new_leads
