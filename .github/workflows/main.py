import os
import feedparser
import requests
import json
import re
from datetime import datetime

# -----------------------------
# LOAD CONFIG
# -----------------------------

with open("sources.json", "r") as f:
    SOURCE_SCORES = json.load(f)

with open("config.json", "r") as f:
    CONFIG = json.load(f)

STATE_FILE = "state.json"

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# -----------------------------
# STATE (persistent dedupe)
# -----------------------------

def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

state = load_state()

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
# NORMALIZATION (CLUSTER KEY)
# -----------------------------

def normalize(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def cluster_key(title):
    # remove common noise words
    stop = ["ufficiale", "breaking", "calciomercato", "news"]
    t = normalize(title)
    for s in stop:
        t = t.replace(s, "")
    return t.strip()

# -----------------------------
# SOURCE SCORE
# -----------------------------

def get_domain(url):
    return url.split("/")[2].replace("www.", "")

def source_score(domain):
    return SOURCE_SCORES.get(domain, SOURCE_SCORES["default"])

# -----------------------------
# CLUSTER STORAGE
# -----------------------------

clusters = {}

# -----------------------------
# TELEGRAM
# -----------------------------

def send(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    })

# -----------------------------
# BAR
# -----------------------------

def bar(p):
    p = max(0, min(100, int(p)))
    return "█" * (p // 10) + "░" * (10 - p // 10)

# -----------------------------
# CLASSIFICATION
# -----------------------------

def label(score, sources):
    if score >= 95:
        return "🟢 UFFICIALE"
    if len(sources) >= 3:
        return "🔴 VIRAL"
    if len(sources) >= 2:
        return "🟡 TRATTATIVA"
    return "⚪ RUMOR"

# -----------------------------
# BUILD MESSAGE
# -----------------------------

def format_post(title, score, sources, links):
    return f"""🦊 FOXGOAL V10

{label(score, sources)} → {title}

{bar(score)} {score}%

Fonti:
{chr(10).join([f"✅ {s}" for s in sources])}

🔗 {links[0] if links else ""}

#Calciomercato
"""

# -----------------------------
# MAIN ENGINE
# -----------------------------

def run():
    global clusters

    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)

        for e in feed.entries:
            title = e.get("title", "")
            link = e.get("link", "")
            domain = get_domain(link)

            key = cluster_key(title)

            if key not in clusters:
                clusters[key] = {
                    "title": title,
                    "sources": set(),
                    "links": []
                }

            clusters[key]["sources"].add(domain)
            clusters[key]["links"].append(link)

    # PROCESS CLUSTERS
    for key, data in clusters.items():
        sources = list(data["sources"])

        # skip already sent
        if state.get(key):
            continue

        # score aggregation
        score = sum([source_score(s) for s in sources]) / max(1, len(sources))

        # RULE: ignore weak single rumor
        if len(sources) == 1 and score < 85:
            continue

        msg = format_post(
            data["title"],
            int(score),
            sources,
            data["links"]
        )

        send(msg)

        state[key] = True

    save_state(state)

if __name__ == "__main__":
    run()