"""
ILLeadPro - Main Scraper Orchestrator
Runs all scrapers on schedule and manages the system
"""
import schedule
import time
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(__file__))

from database import load_leads, get_stats
from scrapers.craigslist_scraper import scrape_craigslist
from scrapers.reddit_scraper import scrape_reddit
from scrapers.listings_scrapers import scrape_fsbo, scrape_foreclosures, scrape_biggerpockets
from scrapers.social_scrapers import scrape_twitter, scrape_cook_county_foreclosures, scrape_dupage_records

LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
LOG_FILE = os.path.join(LOG_DIR, 'scraper.log')


def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{timestamp}] {msg}"
    print(line)
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(LOG_FILE, 'a') as f:
        f.write(line + '\n')


def run_all_scrapers():
    log("=" * 50)
    log("🚀 Starting scraping cycle...")
    log("=" * 50)

    total_new = 0

    scrapers = [
        ("Craigslist", scrape_craigslist),
        ("Reddit", scrape_reddit),
        ("FSBO", scrape_fsbo),
        ("Foreclosures", scrape_foreclosures),
        ("BiggerPockets", scrape_biggerpockets),
        ("Twitter/X", scrape_twitter),
        ("Cook County", scrape_cook_county_foreclosures),
        ("DuPage County", scrape_dupage_records),
    ]

    for name, scraper_fn in scrapers:
        try:
            log(f"▶️  Running {name} scraper...")
            new = scraper_fn()
            total_new += new
            log(f"✅ {name}: {new} new leads")
        except Exception as e:
            log(f"❌ {name} failed: {e}")
        time.sleep(5)

    stats = get_stats()
    log("=" * 50)
    log(f"✅ Cycle complete! {total_new} new leads this run")
    log(f"📊 Total leads in system: {stats['total']}")
    log(f"🔥 Hot leads: {stats['hot']}")
    log(f"📤 Forwarded: {stats['forwarded']}")
    log(f"💰 Deals closed: {stats['closed']}")
    log("=" * 50)

    return total_new


def run_quick_check():
    log("⚡ Quick check running...")
    total = 0
    total += scrape_craigslist()
    total += scrape_reddit()
    log(f"⚡ Quick check done: {total} new leads")


def start_scheduler():
    interval = int(os.getenv('SCRAPE_INTERVAL', 120))

    log(f"🕐 Scheduler started - running every {interval} minutes")
    log(f"📍 Monitoring Illinois real estate leads 24/7")

    # Run immediately on start
    run_all_scrapers()

    # Full run every 2 hours
    schedule.every(interval).minutes.do(run_all_scrapers)

    # Quick check every 30 mins
    schedule.every(30).minutes.do(run_quick_check)

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--once':
        run_all_scrapers()
    else:
        start_scheduler()
