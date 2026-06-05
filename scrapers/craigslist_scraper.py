"""
ILLeadPro - Craigslist Scraper (RSS-based, reliable)
FIXED: Switched from brittle HTML scraping to Craigslist RSS feeds.
Expanded to cover downstate Illinois regions in addition to Chicago metro.
No extra dependencies — uses stdlib xml.etree.ElementTree.
"""
import sys
import os
import re
import time
import random
import requests
from xml.etree import ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from ai_scorer import score_lead
from database import add_lead

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; ILLeadPro/1.0; RSS reader)'
}

# Craigslist RSS feeds — much more reliable than HTML scraping
CL_FEEDS = [
    # Chicago metro
    ("https://chicago.craigslist.org/search/rea.rss", "Chicago",       "RE For Sale"),
    ("https://chicago.craigslist.org/search/reo.rss", "Chicago",       "RE Wanted"),
    ("https://chicago.craigslist.org/search/hsw.rss", "Chicago",       "Housing Wanted"),
    # Downstate / suburbs
    ("https://bloomington.craigslist.org/search/rea.rss",   "Bloomington IL",  "RE For Sale"),
    ("https://champaign.craigslist.org/search/rea.rss",     "Champaign IL",    "RE For Sale"),
    ("https://peoria.craigslist.org/search/rea.rss",        "Peoria IL",       "RE For Sale"),
    ("https://rockford.craigslist.org/search/rea.rss",      "Rockford IL",     "RE For Sale"),
    ("https://springfieldil.craigslist.org/search/rea.rss", "Springfield IL",  "RE For Sale"),
    ("https://decatur.craigslist.org/search/rea.rss",       "Decatur IL",      "RE For Sale"),
]


def strip_html(text):
    """Remove HTML tags from RSS description fields."""
    return re.sub(r'<[^>]+>', '', text or '').strip()


def scrape_craigslist():
    """Scrape Craigslist Illinois via RSS feeds."""
    print("🔍 Scraping Craigslist (RSS)...")
    new_leads = 0

    for feed_url, area, section in CL_FEEDS:
        try:
            resp = requests.get(feed_url, headers=HEADERS, timeout=10)
            if resp.status_code != 200:
                print(f"  ⚠️ {area} ({section}): HTTP {resp.status_code}")
                continue

            root = ET.fromstring(resp.content)
            items = root.findall('.//item')
            print(f"  📡 {area} — {section}: {len(items)} items")

            for item in items[:20]:
                try:
                    title       = strip_html(item.findtext('title', ''))
                    link        = item.findtext('link', '')
                    description = strip_html(item.findtext('description', ''))

                    if not title:
                        continue

                    post_text = f"{title}. {description[:400]}"
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
                        print(f"  ✅ Lead: {title[:60]}...")

                    time.sleep(random.uniform(0.2, 0.5))

                except Exception as e:
                    print(f"  ⚠️ Item error: {e}")
                    continue

            time.sleep(random.uniform(1, 2))

        except ET.ParseError as e:
            print(f"  ❌ RSS parse error for {area}: {e}")
        except Exception as e:
            print(f"  ❌ Error fetching {area} feed: {e}")
            continue

    print(f"  📊 Craigslist: {new_leads} new leads found")
    return new_leads
