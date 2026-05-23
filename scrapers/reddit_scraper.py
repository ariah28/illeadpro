"""
ILLeadPro - Reddit Scraper
Monitors Illinois/Chicago subreddits for buyer/seller leads
"""
import sys
import os
import praw
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from ai_scorer import score_lead
from database import add_lead

SUBREDDITS = [
    'chicago',
    'ChicagoRealEstate',
    'FirstTimeHomeBuyer',
    'RealEstate',
    'chicagosuburbs',
    'illinois',
]

BUY_KEYWORDS = [
    'want to buy', 'looking to buy', 'buying a house', 'first home',
    'first time buyer', 'house hunting', 'relocating to chicago',
    'moving to illinois', 'moving to chicago', 'pre-approved',
    'need a home', 'searching for home', 'looking for house',
    'mortgage', 'down payment', 'affordable home chicago'
]

SELL_KEYWORDS = [
    'selling my home', 'sell my house', 'fsbo', 'for sale by owner',
    'need to sell', 'selling fast', 'motivated seller', 'must sell',
    'relocating', 'downsizing', 'inherited property', 'divorce',
    'selling our home', 'list my house', 'selling in illinois'
]

IL_TERMS = [
    'chicago', 'illinois', 'elmhurst', 'naperville', 'evanston',
    'dupage', 'cook county', 'aurora', 'joliet', 'schaumburg', 'IL'
]


def get_reddit_client():
    return praw.Reddit(
        client_id=os.getenv('REDDIT_CLIENT_ID'),
        client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
        user_agent=os.getenv('REDDIT_USER_AGENT', 'ILLeadPro/1.0')
    )


def has_keywords(text):
    text_lower = text.lower()
    for kw in BUY_KEYWORDS + SELL_KEYWORDS:
        if kw in text_lower:
            return True
    return False


def scrape_reddit():
    """Scrape Reddit for Illinois real estate leads"""
    print("🔍 Scraping Reddit...")
    new_leads = 0

    try:
        reddit = get_reddit_client()

        for subreddit_name in SUBREDDITS:
            try:
                subreddit = reddit.subreddit(subreddit_name)

                for post in subreddit.new(limit=50):
                    try:
                        full_text = f"{post.title} {post.selftext}"

                        if not has_keywords(full_text):
                            continue

                        text_lower = full_text.lower()
                        location_specific = subreddit_name in [
                            'chicago', 'ChicagoRealEstate', 'chicagosuburbs', 'illinois'
                        ]
                        if not location_specific:
                            if not any(t.lower() in text_lower for t in IL_TERMS):
                                continue

                        post_content = f"Title: {post.title}\n\nPost: {post.selftext[:400]}"
                        analysis = score_lead(post_content, 'Reddit', f"r/{subreddit_name}")

                        if not analysis.get('is_real_estate_lead'):
                            continue

                        author_name = str(post.author) if post.author else 'Anonymous'

                        lead = {
                            'name': f"u/{author_name}",
                            'phone': '',
                            'email': '',
                            'area': f"r/{subreddit_name} - Illinois",
                            'source': 'Reddit',
                            'type': analysis.get('type', '🔍 Buyer'),
                            'score': analysis.get('score', '⚡ Warm'),
                            'post': f"{post.title}\n\n{post.selftext[:300]}",
                            'link': f"https://reddit.com{post.permalink}",
                            'reason': analysis.get('reason', ''),
                            'estimatedValue': analysis.get('estimated_value', ''),
                        }

                        if add_lead(lead):
                            new_leads += 1
                            print(f"  ✅ New Reddit lead: {post.title[:50]}...")

                        time.sleep(1)

                    except Exception as e:
                        print(f"  ⚠️ Error processing Reddit post: {e}")
                        continue

                time.sleep(2)

            except Exception as e:
                print(f"  ❌ Error scraping r/{subreddit_name}: {e}")
                continue

    except Exception as e:
        print(f"  ❌ Reddit client error: {e}")

    print(f"  📊 Reddit: {new_leads} new leads found")
    return new_leads
