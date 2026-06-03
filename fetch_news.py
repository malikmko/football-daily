"""
Football Daily Research Script
Fetches trending football stories from the last 24 hours across RSS feeds
and generates a styled HTML report in BallBlitz90 short-form style.
"""

import feedparser
import json
import os
import re
import html
from datetime import datetime, timezone, timedelta
from pathlib import Path
import urllib.request
import urllib.parse

# ── RSS sources ────────────────────────────────────────────────────────────────
FEEDS = [
    # General football news
    ("Sky Sports Football",        "https://www.skysports.com/rss/12040"),
    ("BBC Sport Football",         "https://feeds.bbci.co.uk/sport/football/rss.xml"),
    ("Goal.com",                   "https://www.goal.com/feeds/en/news"),
    ("ESPN Soccer",                "https://www.espn.com/espn/rss/soccer/news"),
    ("The Guardian Football",      "https://www.theguardian.com/football/rss"),
    # Transfers
    ("Sky Sports Transfer Centre", "https://www.skysports.com/rss/12895"),
    ("Transfermarkt News",         "https://www.transfermarkt.us/rss/news"),
    # Clubs / leagues
    ("UEFA",                       "https://www.uefa.com/rssfeed/newsrss.xml"),
    ("FourFourTwo",                "https://www.fourfourtwo.com/rss"),
    ("Marca (English)",            "https://www.marca.com/en/rss/football.xml"),
    ("AS English",                 "https://en.as.com/rss/football.xml"),
]

# Keywords that make a story more interesting / viral
HOT_KEYWORDS = [
    "drama", "shock", "scandal", "ban", "row", "fury", "slams", "war",
    "secret", "betrayal", "sacked", "resign", "fight", "clash", "breaks silence",
    "confirms", "denies", "exclusive", "revealed", "world cup", "transfer",
    "signs", "deal", "agreement", "messi", "ronaldo", "mbappé", "haaland",
    "bellingham", "vinicius", "barcelona", "real madrid", "chelsea", "arsenal",
    "man city", "man utd", "liverpool", "psg", "injury", "return", "retire",
    "salary", "contract", "record", "fee", "bid", "rejected", "demand",
]

# Club emoji map
CLUB_EMOJI = {
    "barcelona":       "🔵🔴",
    "real madrid":     "⚪👑",
    "chelsea":         "🔵🦁",
    "arsenal":         "🔴⚪",
    "manchester city": "🔵🌙",
    "man city":        "🔵🌙",
    "manchester united":"🔴😈",
    "man utd":         "🔴😈",
    "liverpool":       "🔴🦅",
    "psg":             "🔵🗼",
    "juventus":        "⚫⚪",
    "inter":           "⚫🔵",
    "ac milan":        "🔴⚫",
    "bayern":          "🔴⚪",
    "atletico":        "🔴⚪",
    "tottenham":       "⚪🐓",
    "spurs":           "⚪🐓",
    "world cup":       "🏆🌍",
    "england":         "🦁⚪",
    "spain":           "🇪🇸",
    "brazil":          "🇧🇷",
    "argentina":       "🇦🇷",
    "france":          "🇫🇷",
    "portugal":        "🇵🇹",
    "germany":         "🇩🇪",
}

CATEGORY_KEYWORDS = {
    "🔥 TRANSFER":   ["transfer", "signs", "deal", "bid", "fee", "loan", "swap", "move", "agrees", "contract"],
    "💥 DRAMA":      ["drama", "row", "fury", "slams", "war", "fight", "clash", "rant", "sacked", "resign", "ban", "scandal"],
    "🤕 INJURY":     ["injury", "injured", "out", "ruled out", "fitness", "return", "muscle", "hamstring", "knee"],
    "🌍 WORLD CUP":  ["world cup", "worldcup", "fifa", "squad", "group stage"],
    "📰 LATEST":     [],  # default
}


def fetch_articles(hours: int = 24) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    articles = []

    for source_name, url in FEEDS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read()
            feed = feedparser.parse(raw)
        except Exception as e:
            print(f"  [skip] {source_name}: {e}")
            continue

        for entry in feed.entries[:30]:
            # Parse publish date
            pub = None
            for attr in ("published_parsed", "updated_parsed"):
                if hasattr(entry, attr) and getattr(entry, attr):
                    try:
                        pub = datetime(*getattr(entry, attr)[:6], tzinfo=timezone.utc)
                        break
                    except Exception:
                        pass
            if pub is None:
                pub = datetime.now(timezone.utc)

            if pub < cutoff:
                continue

            title   = html.unescape(entry.get("title", "")).strip()
            summary = html.unescape(entry.get("summary", entry.get("description", ""))).strip()
            summary = re.sub(r"<[^>]+>", " ", summary)   # strip HTML tags
            summary = re.sub(r"\s+", " ", summary).strip()
            link    = entry.get("link", "")

            if not title:
                continue

            articles.append({
                "title":   title,
                "summary": summary[:600],
                "link":    link,
                "source":  source_name,
                "pub":     pub.isoformat(),
                "score":   _score(title + " " + summary),
            })

    # De-duplicate by similar title
    seen, unique = set(), []
    for a in articles:
        key = re.sub(r"\W+", "", a["title"].lower())[:60]
        if key not in seen:
            seen.add(key)
            unique.append(a)

    unique.sort(key=lambda x: x["score"], reverse=True)
    return unique


def _score(text: str) -> int:
    t = text.lower()
    return sum(2 if kw in t else 0 for kw in HOT_KEYWORDS)


def categorize(title: str, summary: str) -> str:
    t = (title + " " + summary).lower()
    for cat, kws in CATEGORY_KEYWORDS.items():
        if kws and any(k in t for k in kws):
            return cat
    return "📰 LATEST"


def club_emoji(text: str) -> str:
    t = text.lower()
    for club, em in CLUB_EMOJI.items():
        if club in t:
            return em
    return "⚽"


def generate_script(title: str, summary: str) -> list[str]:
    """
    Generate a BallBlitz-style 8-10 line script from a title + summary.
    """
    lines = []
    em = club_emoji(title + " " + summary)
    cat = categorize(title, summary)

    lines.append(f"{em} {title.upper()}")
    lines.append("")

    sentences = re.split(r"(?<=[.!?])\s+", summary)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20][:6]

    if sentences:
        lines.append(f"Here's everything you need to know... {em}")
        for s in sentences[:4]:
            lines.append(f"👉 {s}")
    else:
        lines.append(f"This is one of the BIGGEST stories in football right now.")
        lines.append(f"And trust me — you need to hear this. 👀")

    lines.append("")
    lines.append(f"Category: {cat}")
    lines.append(f"💬 Drop your take below — are YOU surprised? 👇")
    lines.append(f"🔔 Follow for daily football drops!")

    # Pad to at least 8 lines
    while len(lines) < 8:
        lines.append("")

    return lines[:10]


def build_html(articles: list[dict], generated_at: str) -> str:
    cards_html = ""
    shown = 0
    for a in articles[:25]:
        if shown >= 20:
            break
        cat   = categorize(a["title"], a["summary"])
        em    = club_emoji(a["title"] + " " + a["summary"])
        lines = generate_script(a["title"], a["summary"])
        script_block = "\n".join(f"<p class='sl'>{html.escape(ln)}</p>" for ln in lines if ln)

        # Format time
        try:
            pub_dt = datetime.fromisoformat(a["pub"])
            time_str = pub_dt.strftime("%b %d · %H:%M UTC")
        except Exception:
            time_str = ""

        cards_html += f"""
        <article class="card">
          <div class="card-header">
            <span class="cat-badge">{cat}</span>
            <span class="time">{html.escape(time_str)}</span>
          </div>
          <h2 class="story-title">{em} {html.escape(a['title'])}</h2>
          <div class="script-block">
            <div class="script-label">📝 SHORT SCRIPT (copy-ready)</div>
            {script_block}
          </div>
          <div class="meta">
            <span class="source">📡 {html.escape(a['source'])}</span>
            <a class="read-more" href="{html.escape(a['link'])}" target="_blank" rel="noopener">
              Read Full Story →
            </a>
          </div>
        </article>
        """
        shown += 1

    if not cards_html:
        cards_html = "<p style='color:#aaa;text-align:center;margin-top:60px'>No stories found in the last 24 hours. Try again later.</p>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>⚽ Football Daily Drop · {generated_at}</title>
<style>
  :root {{
    --bg:      #0d0d0d;
    --surface: #161616;
    --card:    #1c1c1e;
    --accent:  #ff3b30;
    --gold:    #ffd60a;
    --text:    #f2f2f7;
    --muted:   #8e8e93;
    --border:  #2c2c2e;
    --green:   #30d158;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    line-height: 1.6;
    min-height: 100vh;
  }}

  /* ── Header ── */
  header {{
    background: linear-gradient(135deg, #1a0000 0%, #0d0d0d 60%, #001a33 100%);
    border-bottom: 2px solid var(--accent);
    padding: 28px 20px 22px;
    text-align: center;
    position: sticky;
    top: 0;
    z-index: 100;
    backdrop-filter: blur(12px);
  }}
  header .logo {{ font-size: 2rem; letter-spacing: -1px; font-weight: 900; }}
  header .logo span {{ color: var(--accent); }}
  header .subtitle {{
    color: var(--muted);
    font-size: .85rem;
    margin-top: 4px;
    letter-spacing: .5px;
  }}
  .live-badge {{
    display: inline-block;
    background: var(--accent);
    color: #fff;
    font-size: .7rem;
    font-weight: 700;
    letter-spacing: 1px;
    padding: 2px 8px;
    border-radius: 4px;
    margin-left: 8px;
    vertical-align: middle;
    animation: pulse 2s infinite;
  }}
  @keyframes pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:.6}} }}

  /* ── Layout ── */
  main {{
    max-width: 860px;
    margin: 0 auto;
    padding: 30px 16px 60px;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }}

  /* ── Stats bar ── */
  .stats {{
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 4px;
  }}
  .stat {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 10px 16px;
    font-size: .8rem;
    color: var(--muted);
    flex: 1;
    min-width: 120px;
    text-align: center;
  }}
  .stat strong {{ display: block; font-size: 1.4rem; color: var(--gold); }}

  /* ── Card ── */
  .card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 22px 20px 18px;
    transition: border-color .2s, transform .15s;
  }}
  .card:hover {{
    border-color: var(--accent);
    transform: translateY(-2px);
  }}
  .card-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
  }}
  .cat-badge {{
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--gold);
    font-size: .72rem;
    font-weight: 700;
    letter-spacing: .6px;
    padding: 3px 9px;
    border-radius: 20px;
  }}
  .time {{ color: var(--muted); font-size: .75rem; }}

  .story-title {{
    font-size: 1.15rem;
    font-weight: 800;
    line-height: 1.35;
    margin-bottom: 16px;
    color: var(--text);
  }}

  /* ── Script block ── */
  .script-block {{
    background: #111;
    border-left: 3px solid var(--accent);
    border-radius: 0 8px 8px 0;
    padding: 14px 16px;
    margin-bottom: 14px;
  }}
  .script-label {{
    font-size: .7rem;
    font-weight: 700;
    letter-spacing: 1px;
    color: var(--accent);
    margin-bottom: 8px;
  }}
  .sl {{
    font-size: .88rem;
    color: #ddd;
    margin-bottom: 4px;
    font-family: 'Courier New', monospace;
  }}

  /* ── Meta ── */
  .meta {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: .78rem;
    color: var(--muted);
    flex-wrap: wrap;
    gap: 8px;
  }}
  .read-more {{
    color: var(--green);
    text-decoration: none;
    font-weight: 600;
    letter-spacing: .3px;
  }}
  .read-more:hover {{ text-decoration: underline; }}

  /* ── Footer ── */
  footer {{
    text-align: center;
    color: var(--muted);
    font-size: .78rem;
    padding: 30px 16px;
    border-top: 1px solid var(--border);
  }}

  @media (max-width: 500px) {{
    .story-title {{ font-size: 1rem; }}
    header .logo {{ font-size: 1.5rem; }}
  }}
</style>
</head>
<body>

<header>
  <div class="logo">⚽ FOOTBALL DAILY <span>DROP</span> <span class="live-badge">LIVE</span></div>
  <div class="subtitle">Last 24 hours · Top Stories · Transfers · Drama · World Cup</div>
  <div class="subtitle" style="margin-top:6px;color:#555">Generated: {generated_at}</div>
</header>

<main>
  <div class="stats">
    <div class="stat"><strong>{shown}</strong>Stories Today</div>
    <div class="stat"><strong>24h</strong>Window</div>
    <div class="stat"><strong>10+</strong>Sources</div>
    <div class="stat"><strong>🏆</strong>World Cup Mode</div>
  </div>

  {cards_html}
</main>

<footer>
  ⚽ Football Daily Drop · Auto-updated every 24 hours · Research powered by RSS + AI scripting
</footer>

</body>
</html>"""


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    print("Football Daily Drop -- fetching last 24h stories...")
    articles = fetch_articles(hours=24)
    print(f"   Found {len(articles)} articles")

    now = datetime.now(timezone.utc).strftime("%B %d, %Y · %H:%M UTC")
    page = build_html(articles, now)

    out = Path(__file__).parent / "index.html"
    out.write_text(page, encoding="utf-8")
    print(f"   ✅ Report saved → {out}")

    # Also save raw JSON for debugging
    json_out = Path(__file__).parent / "articles.json"
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(articles[:25], f, ensure_ascii=False, indent=2)
    print(f"   ✅ Raw data saved → {json_out}")
