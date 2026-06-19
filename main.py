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

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# -----------------------------
# RSS FEEDS
# -----------------------------

RSS_FEEDS = [
    "https://www.gazzetta.it/rss/calcio.xml",
    "https://www.ansa.it/sito/ansait_rss.xml",
    "https://www.tuttomercatoweb.com/rss/calcio.xml",
    "https://www.calciomercato.com/rss/",
    "https://www.sportmediaset.mediaset.it/rss/calcio.xml"
]

# -----------------------------
# DOMAIN
# -----------------------------

def get_domain(url):
    try:
        if not url:
            return "unknown"
        parsed = urlparse(url)
        return parsed.netloc.replace("www.", "")
    except:
        return "unknown"

# -----------------------------
# SCORE
# -----------------------------

def source_score(d):
    return SOURCE_SCORES.get(d, SOURCE_SCORES["default"])

# -----------------------------
# FRESHNESS FILTER (NO 2024)
# -----------------------------

def is_recent(e, hours=72):
    try:
        if not hasattr(e, "published_parsed") or not e.published_parsed:
            return False

        pub = datetime(*e.published_parsed[:6], tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)

        return 0 <= (now - pub).total_seconds() <= hours * 3600
    except:
        return False

# -----------------------------
# 🔥 SOLO CALCIOMERCATO FILTER
# -----------------------------

def is_transfer_related(text):
    keywords = [
        "calciomercato", "mercato", "trasferimento",
        "cede", "ceduto", "prestito", "acquisto",
        "offerta", "trattativa", "firma", "contratto",
        "scambio", "accordo", "ingaggio"
    ]

    t = text.lower()
    return any(k in t for k in keywords)

# -----------------------------
# ENTITY EXTRACTION (solo se mercato)
# -----------------------------

def extract_entities(text):

    if not is_transfer_related(text):
        return []

    words = re.findall(r"[A-Z][a-z]{2,}", text)

    blacklist = {
        "Calcio", "Serie", "Champions", "League",
        "Breaking", "Live", "News",
        "Partita", "Gol", "Risultato", "Infortunio"
    }

    return list({w for w in words if w not in blacklist})

# -----------------------------
# TELEGRAM
# -----------------------------

def send(msg):
    if not TOKEN or not CHAT_ID:
        print("Missing Telegram config")
        return

    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={
            "chat_id": CHAT_ID,
            "text": msg,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
    )

# -----------------------------
# LABEL
# -----------------------------

def label(score, n):
    if score > 92:
        return "🟢 UFFICIALE"
    if n >= 3:
        return "🔴 HOT"
    if n == 2:
        return "🟡 TRATTATIVA"
    return "⚪ RUMOR"

# -----------------------------
# BAR
# -----------------------------

def bar(v):
    v = int(max(0, min(100, v)))
    return "█" * (v // 10) + "░" * (10 - v // 10)

# -----------------------------
# ENGINE
# -----------------------------

clusters = {}
state = {}

def run():

    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)

        for e in feed.entries:

            if not is_recent(e, 72):
                continue

            title = e.get("title", "")
            link = e.get("link", "")

            if not title or not link:
                continue

            entities = extract_entities(title)

            if not entities:
                continue

            key = "|".join(sorted(entities))

            if state.get(key):
                continue

            if key not in clusters:
                clusters[key] = {
                    "entities": entities,
                    "sources": set(),
                    "links": []
                }

            domain = get_domain(link)

            clusters[key]["sources"].add(domain)
            clusters[key]["links"].append(link)

    for k, v in clusters.items():

        sources = list(v["sources"])
        if not sources:
            continue

        score = sum(source_score(s) for s in sources) / len(sources)

        msg = f"""🦊 FOXGOAL V17 (TRANSFER MODE)

{label(score, len(sources))} → {" & ".join(v["entities"])}

📊 Affidabilità: {int(score)}%

{bar(score)} {int(score)}%

Fonti:
{chr(10).join("✅ " + s for s in sources)}

🔗 {v["links"][0]}

#Calciomercato
"""

        send(msg)
        state[k] = True


if __name__ == "__main__":
    run()