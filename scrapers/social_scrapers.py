"""
ILLeadPro - Social & Public Records Scrapers (FIXED)
Changes:
  - Twitter/X (Nitter): REPLACED — Nitter instances are offline as of 2024.
    Now scrapes expanded downstate IL Craigslist regions (RSS) + Homes.com FSBO.
  - Cook County: Multiple source fallbacks with address-pattern matching.
  - DuPage County: IMPLEMENTED — was a stub returning 0. Now scrapes 3 sources
    with address regex extraction.
"""
import sys
import os
import re
import time
import random
import requests
from bs4 import BeautifulSoup
from xml.etree import ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from ai_scorer import score_lead
from database import add_lead

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/121.0.0.0 Safari/537.36'
    ),
    'Accept':          'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

ADDR_PATTERN = re.compile(
    r'\d+\s+[\w\s]+(?:St|Ave|Blvd|Dr|Rd|Ln|Ct|Pl|Way|Pkwy|Circle|Cir)',
    re.IGNORECASE
)


def strip_html(text):
    return re.sub(r'<[^>]+>', '', text or '').strip()


def get_text(el):
    return el.get_text(strip=True) if el else ''


# ---------------------------------------------------------------------------
# Twitter/X replacement — expanded IL Craigslist RSS + Homes.com FSBO
# ---------------------------------------------------------------------------

def scrape_twitter():
    """
    REPLACED: Twitter/X via Nitter is no longer viable (instances went offline in 2024).

    Now provides equivalent lead volume via:
      1. Expanded downstate Illinois Craigslist regions (RSS — reliable)
      2. Homes.com Illinois FSBO listings
    """
    print("🔍 Scanning downstate IL Craigslist + Homes.com FSBO "
          "(replaces defunct Twitter/Nitter scraper)...")
    new_leads = 0

    # --- Part 1: Downstate IL Craigslist RSS ---
    extra_feeds = [
        ("https://kankakee.craigslist.org/search/rea?format=rss",    "Kankakee IL"),
        ("https://quincy.craigslist.org/search/rea?format=rss",      "Quincy IL"),
        ("https://rockford.craigslist.org/search/reo?format=rss",    "Rockford IL Wanted"),
        ("https://peoria.craigslist.org/search/hsw?format=rss",      "Peoria IL Wanted"),
        ("https://champaign.craigslist.org/search/reo?format=rss",   "Champaign IL Wanted"),
        ("https://springfieldil.craigslist.org/search/reo?format=rss", "Springfield IL Wanted"),
    ]

    for feed_url, area in extra_feeds:
        try:
            resp = requests.get(feed_url, headers=HEADERS, timeout=10)
            if resp.status_code != 200:
                continue

            root  = ET.fromstring(resp.content)
            items = root.findall('.//item')

            for item in items[:10]:
                try:
                    title       = strip_html(item.findtext('title', ''))
                    link        = item.findtext('link', '')
                    description = strip_html(item.findtext('description', ''))

                    if not title:
                        continue

                    post_text = f"{title}. {description[:300]}"
                    analysis  = score_lead(post_text, 'Craigslist', area)

                    if not analysis.get('is_real_estate_lead'):
                        continue

                    lead = {
                        'name':           'Craigslist Poster',
                        'phone':          '',
                        'email':          '',
                        'area':           area,
                        'source':         'Craigslist',
                        'type':           analysis.get('type', '🏠 Seller'),
                        'score':          analysis.get('score', '⚡ Warm'),
                        'post':           post_text[:400],
                        'link':           link,
                        'reason':         analysis.get('reason', ''),
                        'estimatedValue': analysis.get('estimated_value', ''),
                    }

                    if add_lead(lead):
                        new_leads += 1
                        print(f"  ✅ Regional CL lead ({area}): {title[:50]}...")

                    time.sleep(random.uniform(0.3, 0.7))

                except Exception:
                    continue

            time.sleep(random.uniform(1, 2))

        except (ET.ParseError, Exception) as e:
            print(f"  ⚠️ {area}: {e}")
            continue

    # --- Part 2: Homes.com Illinois FSBO ---
    try:
        homes_url = "https://www.homes.com/for-sale/illinois/fsbo/"
        resp      = requests.get(homes_url, headers=HEADERS, timeout=12)

        if resp.status_code == 200:
            soup     = BeautifulSoup(resp.text, 'lxml')
            listings = (
                soup.select('[class*="listing"]') or
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

                    addr_text  = get_text(addr)
                    price_text = get_text(price)

                    if len(addr_text) < 5:
                        continue

                    post_text = (
                        f"FOR SALE BY OWNER on Homes.com: {addr_text}. "
                        f"Price: {price_text}. Illinois FSBO."
                    )

                    lead = {
                        'name':           'FSBO Seller',
                        'phone':          '',
                        'email':          '',
                        'area':           addr_text,
                        'source':         'FSBO',
                        'type':           '🏠 Seller',
                        'score':          '🔥 Hot',
                        'post':           post_text,
                        'link':           homes_url,
                        'reason':         'FSBO listing on Homes.com — no agent, motivated seller',
                        'estimatedValue': price_text,
                    }

                    if add_lead(lead):
                        new_leads += 1
                        print(f"  ✅ Homes.com FSBO: {addr_text[:50]}...")

                except Exception:
                    continue
        else:
            print(f"  ⚠️ Homes.com: HTTP {resp.status_code}")

    except Exception as e:
        print(f"  ⚠️ Homes.com error: {e}")

    print(f"  📊 Regional/FSBO: {new_leads} new leads found")
    return new_leads


# ---------------------------------------------------------------------------
# Cook County — multiple source fallbacks + address-pattern matching
# ---------------------------------------------------------------------------

def scrape_cook_county_foreclosures():
    """Scrape Cook County public foreclosure / sheriff sale notices."""
    print("🔍 Scraping Cook County public records...")
    new_leads = 0

    sources = [
        {
            'url':  'https://www.cookcountysheriff.org/civil-process/real-estate-sales/',
            'name': 'Cook County Sheriff Sales',
        },
        {
            'url':  'https://www.illinoislegalaid.org/legal-information/foreclosure',
            'name': 'Illinois Legal Aid Foreclosure',
        },
        {
            'url':  'https://www.cookcountyclerkofcourt.org/foreclosure-mediation',
            'name': 'Cook County Clerk of Court',
        },
    ]

    for source in sources:
        try:
            resp = requests.get(source['url'], headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                print(f"  ⚠️ {source['name']}: HTTP {resp.status_code}")
                continue

            soup = BeautifulSoup(resp.text, 'lxml')

            rows = (
                soup.select('table tr')         or
                soup.select('[class*="sale"] li')  or
                soup.select('[class*="property"]') or
                soup.select('[class*="notice"]')   or
                soup.select('li')
            )

            found_here = 0
            for row in rows[1:25]:
                try:
                    text = row.get_text(separator=' ', strip=True)
                    if len(text) < 15:
                        continue

                    # Only keep rows that look like property addresses
                    if not ADDR_PATTERN.search(text):
                        continue

                    cols    = row.select('td')
                    address = cols[0].get_text(strip=True) if cols else text[:120]
                    extra   = (' | '.join(c.get_text(strip=True) for c in cols[1:3])
                               if len(cols) > 1 else '')

                    post_text = (
                        f"COOK COUNTY FORECLOSURE/SALE: {address}. "
                        f"{extra}. Court-ordered sale — motivated seller."
                    )

                    lead = {
                        'name':           'Cook County Foreclosure',
                        'phone':          '',
                        'email':          '',
                        'area':           f"{address}, Cook County, IL",
                        'source':         'Foreclosure',
                        'type':           '🏠 Seller',
                        'score':          '🔥 Hot',
                        'post':           post_text,
                        'link':           source['url'],
                        'reason':         'Court-ordered foreclosure sale — extremely motivated seller',
                        'estimatedValue': extra,
                    }

                    if add_lead(lead):
                        new_leads += 1
                        found_here += 1
                        print(f"  ✅ Cook County lead: {address[:50]}...")

                except Exception:
                    continue

            if found_here > 0:
                break  # Got results; skip remaining sources

            time.sleep(2)

        except Exception as e:
            print(f"  ❌ {source['name']}: {e}")
            continue

    print(f"  📊 Cook County: {new_leads} new leads found")
    return new_leads


# ---------------------------------------------------------------------------
# DuPage County — IMPLEMENTED (was a stub returning 0)
# ---------------------------------------------------------------------------

def scrape_dupage_records():
    """
    Scrape DuPage County property records for motivated sellers.
    FIXED: was a stub that only checked connectivity and returned 0.
    Now tries three public sources and extracts address-matched rows.
    """
    print("🔍 Scraping DuPage County records...")
    new_leads = 0

    sources = [
        {
            'url':    'https://www.dupageco.org/Sheriff/Civil_Process/Real_Estate_Sales/',
            'name':   'DuPage Sheriff Sales',
            'score':  '🔥 Hot',
            'reason': 'Sheriff sale — distressed / court-ordered property',
        },
        {
            'url':    'https://www.dupageco.org/Treasurer/Tax_Sales/',
            'name':   'DuPage Tax Sales',
            'score':  '🔥 Hot',
            'reason': 'Tax delinquent property — motivated to resolve',
        },
        {
            'url':    'https://www.dupageco.org/Sheriff/Civil_Process/',
            'name':   'DuPage Civil Process',
            'score':  '🔥 Hot',
            'reason': 'Court-ordered civil process — distressed property',
        },
    ]

    for source in sources:
        try:
            resp = requests.get(source['url'], headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                print(f"  ⚠️ {source['name']}: HTTP {resp.status_code}")
                continue

            soup = BeautifulSoup(resp.text, 'lxml')

            rows = (
                soup.select('table tr')            or
                soup.select('[class*="property"]') or
                soup.select('[class*="sale"]')     or
                soup.select('li')
            )

            found_here = 0
            for row in rows[1:20]:
                try:
                    text = row.get_text(separator=' ', strip=True)
                    if len(text) < 15:
                        continue

                    addr_match = ADDR_PATTERN.search(text)
                    if not addr_match:
                        continue

                    address = addr_match.group(0).strip()
                    cols    = row.select('td')
                    amount  = cols[-1].get_text(strip=True) if cols else ''

                    post_text = (
                        f"DUPAGE COUNTY RECORD: Property at {address}. "
                        f"Amount: {amount}. DuPage County, IL. Motivated seller."
                    )

                    lead = {
                        'name':           'DuPage Property Owner',
                        'phone':          '',
                        'email':          '',
                        'area':           f"{address}, DuPage County, IL",
                        'source':         'Public Records',
                        'type':           '🏠 Seller',
                        'score':          source['score'],
                        'post':           post_text,
                        'link':           source['url'],
                        'reason':         source['reason'],
                        'estimatedValue': amount,
                    }

                    if add_lead(lead):
                        new_leads += 1
                        found_here += 1
                        print(f"  ✅ DuPage lead: {address[:50]}...")

                except Exception:
                    continue

            if found_here > 0:
                break

            time.sleep(2)

        except Exception as e:
            print(f"  ❌ {source['name']}: {e}")
            continue

    print(f"  📊 DuPage: {new_leads} new leads found")
    return new_leads
