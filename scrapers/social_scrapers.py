"""
ILLeadPro - Social & Public Records Scrapers
Twitter/X keyword monitoring + Illinois public records
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
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

TWITTER_KEYWORDS = [
    'buying house chicago',
    'selling home illinois',
    'moving to chicago real estate',
    'relocating to illinois house',
    'first home chicago illinois',
    'need agent chicago illinois',
]

NITTER_INSTANCES = [
    'nitter.net',
    'nitter.1d4.us',
    'nitter.kavin.rocks',
]

IL_TERMS = ['chicago', 'illinois', 'IL', 'elmhurst', 'naperville']


def scrape_twitter():
    """Monitor Twitter/X public search for Illinois real estate (via Nitter)"""
    print("🔍 Scraping Twitter/X...")
    new_leads = 0

    for keyword in TWITTER_KEYWORDS[:3]:
        for instance in NITTER_INSTANCES:
            try:
                url = f"https://{instance}/search"
                params = {'q': keyword, 'f': 'tweets'}
                resp = requests.get(url, headers=HEADERS, params=params, timeout=8)

                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, 'lxml')
                tweets = soup.select('.timeline-item, .tweet-content')

                for tweet in tweets[:5]:
                    try:
                        content = tweet.select_one('.tweet-content, .content')
                        username = tweet.select_one('.username, .fullname')

                        if not content:
                            continue

                        tweet_text = content.text.strip()
                        user_text = username.text.strip() if username else 'Twitter User'

                        if not any(t.lower() in tweet_text.lower() for t in IL_TERMS):
                            continue

                        analysis = score_lead(tweet_text, 'Twitter/X', 'Illinois')

                        if not analysis.get('is_real_estate_lead'):
                            continue

                        lead = {
                            'name': user_text,
                            'phone': '',
                            'email': '',
                            'area': 'Illinois',
                            'source': 'Twitter',
                            'type': analysis.get('type', '🔍 Buyer'),
                            'score': analysis.get('score', '⚡ Warm'),
                            'post': tweet_text,
                            'link': f"https://twitter.com/search?q={keyword.replace(' ', '+')}",
                            'reason': analysis.get('reason', ''),
                            'estimatedValue': '',
                        }

                        if add_lead(lead):
                            new_leads += 1
                            print(f"  ✅ New Twitter lead: {tweet_text[:50]}...")

                        time.sleep(1)
                    except Exception:
                        continue

                time.sleep(random.uniform(2, 3))
                break  # Move to next keyword after first successful instance

            except Exception:
                continue

    print(f"  📊 Twitter/X: {new_leads} new leads found")
    return new_leads


def scrape_cook_county_foreclosures():
    """Scrape Cook County public foreclosure notices"""
    print("🔍 Scraping Cook County public records...")
    new_leads = 0

    try:
        url = "https://www.cookcountyclerkofcourt.org/NewWebsite/fr_srch.aspx"
        resp = requests.get(url, headers=HEADERS, timeout=10)

        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'lxml')
            rows = soup.select('table tr, .foreclosure-row')

            for row in rows[1:10]:
                try:
                    cols = row.select('td')
                    if len(cols) < 3:
                        continue

                    address = cols[0].text.strip()
                    case_num = cols[1].text.strip() if len(cols) > 1 else ''
                    amount = cols[2].text.strip() if len(cols) > 2 else ''

                    if not address:
                        continue

                    post_text = (
                        f"COOK COUNTY FORECLOSURE: Property at {address}. "
                        f"Case: {case_num}. Amount: {amount}. "
                        f"Motivated seller - court ordered sale."
                    )

                    lead = {
                        'name': 'Foreclosure Owner',
                        'phone': '',
                        'email': '',
                        'area': f"{address}, Cook County, IL",
                        'source': 'Foreclosure',
                        'type': '🏠 Seller',
                        'score': '🔥 Hot',
                        'post': post_text,
                        'link': url,
                        'reason': 'Court-ordered foreclosure - extremely motivated seller',
                        'estimatedValue': amount,
                    }

                    if add_lead(lead):
                        new_leads += 1
                        print(f"  ✅ New foreclosure: {address[:50]}...")

                except Exception:
                    continue

    except Exception as e:
        print(f"  ❌ Cook County records error: {e}")

    print(f"  📊 Cook County: {new_leads} new leads found")
    return new_leads


def scrape_dupage_records():
    """Scrape DuPage County property records for motivated sellers"""
    print("🔍 Scraping DuPage County records...")
    new_leads = 0

    try:
        url = "https://www.dupageco.org/PropertyInfo/PropertySearch.aspx"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            print("  ✅ DuPage County records accessible")
    except Exception as e:
        print(f"  ⚠️ DuPage County: {e}")

    print(f"  📊 DuPage: {new_leads} leads (manual check recommended)")
    return new_leads
