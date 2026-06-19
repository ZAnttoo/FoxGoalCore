import os
import feedparser
import requests
import json
import re
from urllib.parse import urlparse

# -----------------------------
# LOAD CONFIG
# -----------------------------

with open("sources.json", "r") as f:
    SOURCE_SCORES = json.load(f)

with open("config.json", "r") as f:
    CONFIG = json.load(f)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# -----------------------------
# RSS FEEDS
# -----------------------------

RSS_FEEDS = [
    "https://www.gazzetta.it/rss/calcio.xml",
    "https://www.ansa.it/sito/ansait_rss.xml",
    "https://www.tuttomercatoweb.com/rss/",
    "https://www.corrieredellosport.it/rss.xml"
]

# -----------------------------
# SAFE DOMAIN PARSER
# -----------------------------

def get_domain(url):
    try:
        if not url:
            return "unknown"
        parsed = urlparse(url)
        domain = parsed.netloc
        if not domain:
            return "unknown"
        return domain.replace("www.", "")
    except:
        return "unknown"

# -----------------------------
# SOURCE SCORE
# -----------------------------

def source_score(domain):
    return SOURCE_SCORES.get(domain, SOURCE_SCORES["default"])

# -----------------------------
# TELEGRAM
# -----------------------------

def send_telegram(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Missing Telegram credentials")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    })

# -----------------------------
# BAR
# -----------------------------

def bar(score):
    score = max(0, min(100, int(score)))
    return "█" * (score // 10) + "░" * (10 - score // 10)

# -----------------------------
# LABEL SYSTEM
# -----------------------------

def label(score):
    if score >= 95:
        return "🟢 UFFICIALE"
    elif score >= 75:
        return "🟡 TRATTATIVA"
    else:
        return "🔴 RUMOR"

# -----------------------------
# CLEAN TEXT
# -----------------------------

def clean(text):
    if not text:
        return ""
    return re.sub(r"<.*?>", "", text)

# -----------------------------
# FORMAT MESSAGE
# -----------------------------

def format_post(title, score, source, link):
    return f"""🦊 FOXGOAL

{label(score)} → {title}

{bar(score)} {score}%

Fonte:
✅ {source}

🔗 {link}

#Calciomercato
"""

# -----------------------------
# MAIN ENGINE
# -----------------------------

seen = set()

def run():
    posts = []

    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)

        for e in feed.entries:
            title = clean(e.get("title", ""))
            link = e.get("link", "")

            # safety checks
            if not title or not link:
                continue

            if title in seen:
                continue
            seen.add(title)

            domain = get_domain(link)
            score = source_score(domain)

            posts.append(format_post(title, score, domain, link))

    # send max 5 posts per run
    for post in posts[:5]:
        send_telegram(post)

if __name__ == "__main__":
    run()