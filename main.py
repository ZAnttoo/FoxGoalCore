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

RSS_FEEDS = [
    "https://www.gazzetta.it/rss/calcio.xml",
    "https://www.ansa.it/sito/ansait_rss.xml",
    "https://www.tuttomercatoweb.com/rss/",
    "https://www.corrieredellosport.it/rss.xml"
]

# -----------------------------
# STATE (anti duplicati)
# -----------------------------

STATE_FILE = "state.json"

def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_state(s):
    with open(STATE_FILE, "w") as f:
        json.dump(s, f)

state = load_state()

# -----------------------------
# HELPERS
# -----------------------------

def domain(url):
    try:
        return urlparse(url).netloc.replace("www.", "")
    except:
        return "unknown"

def score(d):
    return SOURCE_SCORES.get(d, SOURCE_SCORES["default"])

def bar(v):
    v = int(max(0, min(100, v)))
    return "█" * (v // 10) + "░" * (10 - v // 10)

# -----------------------------
# FRESHNESS
# -----------------------------

def recent(e, hours=72):
    try:
        if not e.get("published_parsed"):
            return True
        pub = datetime(*e.published_parsed[:6], tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now - pub) < timedelta(hours=hours)
    except:
        return True

# -----------------------------
# PLAYER / ENTITY EXTRACTION (V16 improved)
# -----------------------------

def extract_entities(text):
    # pattern realistico nomi (non lista fissa rigida)
    words = re.findall(r"[A-Z][a-z]{2,}", text)
    
    blacklist = {
        "Calcio", "Serie", "Champions", "League", "Breaking",
        "Ufficiale", "Mercato", "Live", "News"
    }

    entities = []
    for w in words:
        if w not in blacklist:
            entities.append(w)

    return list(set(entities))

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
# LABEL SYSTEM
# -----------------------------

def label(s, n):
    if s > 92:
        return "🟢 UFFICIALE"
    if n >= 3:
        return "🔴 HOT"
    if n == 2:
        return "🟡 TRATTATIVA"
    return "⚪ RUMOR"

# -----------------------------
# ENGINE
# -----------------------------

clusters = {}

def run():

    for url in RSS_FEEDS:
        feed = feedparser.parse(url)

        for e in feed.entries:

            if not recent(e):
                continue

            title = e.get("title", "")
            link = e.get("link", "")

            if not title or not link:
                continue

            entities = extract_entities(title)

            if len(entities) == 0:
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

            clusters[key]["sources"].add(domain(link))
            clusters[key]["links"].append(link)

    for k, v in clusters.items():

        sources = list(v["sources"])
        if not sources:
            continue

        score_val = sum(score(s) for s in sources) / len(sources)

        msg = f"""🦊 FOXGOAL V16

{label(score_val, len(sources))} → {" & ".join(v["entities"])}

📊 Affidabilità: {int(score_val)}%

{bar(score_val)} {int(score_val)}%

Fonti:
{chr(10).join("✅ " + s for s in sources)}

🔗 {v["links"][0]}

#TransferNews
"""

        send(msg)

        state[k] = True

    save_state(state)

if __name__ == "__main__":
    run()