import os
import feedparser
import requests
import json
import re
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta

# -----------------------------
# CONFIG
# -----------------------------

with open("sources.json", "r") as f:
    SOURCE_SCORES = json.load(f)

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
# SAFE DOMAIN
# -----------------------------

def get_domain(url):
    try:
        if not url:
            return "unknown"
        parsed = urlparse(url)
        domain = parsed.netloc
        return domain.replace("www.", "") if domain else "unknown"
    except:
        return "unknown"

# -----------------------------
# SOURCE SCORE
# -----------------------------

def source_score(domain):
    return SOURCE_SCORES.get(domain, SOURCE_SCORES["default"])

# -----------------------------
# FRESHNESS FILTER
# -----------------------------

def is_recent(entry, hours=72):
    try:
        if not hasattr(entry, "published_parsed") or not entry.published_parsed:
            return True

        published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)

        return (now - published) <= timedelta(hours=hours)
    except:
        return True

# -----------------------------
# PLAYER DETECTION
# -----------------------------

def extract_players(text):
    players = [
        "Osimhen", "Ndoye", "Lukaku", "Vlahovic", "Leao",
        "Chiesa", "Dybala", "Kvara", "Kvaratskhelia",
        "Barella", "Tonali", "Modric", "Haaland"
    ]

    found = []
    for p in players:
        if re.search(rf"\b{p.lower()}\b", text.lower()):
            found.append(p)

    return found

# -----------------------------
# TELEGRAM
# -----------------------------

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Missing Telegram credentials")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    })

# -----------------------------
# LABEL
# -----------------------------

def label(score, sources_count):
    if score >= 95:
        return "🟢 UFFICIALE"
    if sources_count >= 3:
        return "🔴 HOT"
    if sources_count == 2:
        return "🟡 TRATTATIVA"
    return "⚪ RUMOR"

# -----------------------------
# BAR
# -----------------------------

def bar(score):
    score = int(max(0, min(100, score)))
    return "█" * (score // 10) + "░" * (10 - score // 10)

# -----------------------------
# FORMAT
# -----------------------------

def format_msg(players, score, sources, link):
    return f"""🦊 FOXGOAL V11

{label(score, len(sources))} → {" & ".join(players)}

📊 Affidabilità: {score:.0f}%

{bar(score)} {score:.0f}%

Fonti:
{chr(10).join([f"✅ {s}" for s in sources])}

🔗 {link}

#Calciomercato
"""

# -----------------------------
# ENGINE
# -----------------------------

clusters = {}

def run():

    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)

        for e in feed.entries:

            if not is_recent(e, hours=72):
                continue

            title = e.get("title", "")
            link = e.get("link", "")

            if not title or not link:
                continue

            players = extract_players(title)

            if not players:
                continue

            key = "|".join(players)

            if key not in clusters:
                clusters[key] = {
                    "players": players,
                    "sources": set(),
                    "links": []
                }

            domain = get_domain(link)

            clusters[key]["sources"].add(domain)
            clusters[key]["links"].append(link)

    for key, data in clusters.items():

        sources = list(data["sources"])
        score = sum([source_score(s) for s in sources]) / len(sources)

        msg = format_msg(
            data["players"],
            score,
            sources,
            data["links"][0]
        )

        send_telegram(msg)

if __name__ == "__main__":
    run()