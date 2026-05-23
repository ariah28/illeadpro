# ILLeadPro — Illinois Real Estate Lead Finder

Automatically finds motivated buyers and sellers across Illinois 24/7.
Sources: Craigslist, Reddit, FSBO, Foreclosures, BiggerPockets, Twitter/X, Cook County & DuPage County public records.

---

## Setup (15 mins total)

### Step 1 — Reddit API Key (Free, 5 mins)
1. Go to https://reddit.com/prefs/apps
2. Click **Create App**
3. Name: `ILLeadPro` | Type: `script` | Redirect URI: `http://localhost`
4. Copy your **client_id** (under the app name) and **client_secret**

### Step 2 — Anthropic API Key (~$5 one-time)
1. Go to https://console.anthropic.com
2. Sign up → Billing → Add $5 → **Turn off auto-recharge!**
3. Go to API Keys → Create Key → Copy it

### Step 3 — Deploy to Railway (Free)
1. Go to https://railway.app → Sign up with GitHub
2. Click **New Project** → **Deploy from GitHub repo** → select this repo
3. Go to **Variables** tab and add:
   - `ANTHROPIC_API_KEY` = your key
   - `REDDIT_CLIENT_ID` = your id
   - `REDDIT_CLIENT_SECRET` = your secret
   - `ALERT_EMAIL` = hartoul28@gmail.com
4. Click **Deploy**

### Step 4 — Open Your Dashboard
Open `ILLeadPro.html` in your browser.
Point it to your Railway URL and leads will start flowing in.

---

## Daily Use
1. Open dashboard → check new leads
2. Click through to the original post to grab contact info (phone/email)
3. Forward hot leads to your broker partner
4. Track deal status and earnings in the dashboard

---

## Cost Summary
- Railway hosting: Free ($5 credit, no card needed)
- Anthropic API: ~$5 one-time (turn off auto-recharge)
- Everything else: Free
