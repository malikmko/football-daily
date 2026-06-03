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


def viral_title(title: str, summary: str) -> str:
    """
    Re-frames the raw RSS headline into a BallBlitz/FutVibes-style viral title.
    Applies the 6 proven title patterns + correct 2-emoji ending.
    """
    t   = (title + " " + summary).lower()
    cat = categorize(title, summary)

    # Pick emoji pair based on content tone
    if any(k in t for k in ["dumb", "worst", "criminal", "joke", "embarrass", "absurd", "ridiculous"]):
        emojis = "🤣💀"
    elif any(k in t for k in ["shock", "surprise", "unbelievable", "never seen", "first ever", "history"]):
        emojis = "😳🤯"
    elif any(k in t for k in ["injury", "out", "ruled out", "hurt", "surgery"]):
        emojis = "😭💔"
    elif any(k in t for k in ["sack", "resign", "fire", "quit", "leave", "exit", "ban"]):
        emojis = "😳💀"
    elif any(k in t for k in ["world cup", "final", "trophy", "champion", "title", "win"]):
        emojis = "🏆😳"
    elif any(k in t for k in ["transfer", "sign", "deal", "fee", "bid", "buy", "sell"]):
        emojis = "🤯💰"
    elif any(k in t for k in ["drama", "row", "furious", "slams", "clash", "war", "angry"]):
        emojis = "💥😳"
    else:
        emojis = "😳💀"

    # Apply title pattern based on category and keywords
    if any(k in t for k in ["rule", "regulation", "allowed", "banned", "can't", "cannot", "not permitted"]):
        # Pattern: "The Dumb Rule" expose
        return f"Why {title.split('—')[0].strip()} is NOT what you think. {emojis}"

    elif any(k in t for k in ["real reason", "why", "secret", "revealed", "exposed", "truth"]):
        # Pattern: "The Real Reason"
        return f"The real reason behind this... {emojis}"

    elif any(k in t for k in ["transfer", "signs", "deal", "agrees", "confirms move"]):
        # Pattern: Transfer Chaos & Irony
        return f"{title} — and nobody saw this coming. {emojis}"

    elif any(k in t for k in ["never", "first ever", "history", "record", "all-time"]):
        # Pattern: "World First / Never Seen"
        return f"{title} — never seen before in football. {emojis}"

    elif any(k in t for k in ["sacked", "fired", "resign", "quit", "leaves", "exit"]):
        # Pattern: Shocking Contradiction
        return f"{title} — football is actually cooked. {emojis}"

    elif any(k in t for k in ["world cup", "squad", "group", "odds", "chances", "qualify"]):
        # Pattern: Stats/Percentage hook
        return f"{title} — this is disrespectful. {emojis}"

    else:
        return f"{title} 😳💀"


def generate_script(title: str, summary: str) -> dict:
    """
    Generates a full BallBlitz/FutVibes 4-act script.
    Returns a dict with keys: viral_title, hook, context, reveal, punchline, cta
    Always produces complete content — never leaves a section empty.
    """
    em  = club_emoji(title + " " + summary)
    cat = categorize(title, summary)
    t   = (title + " " + summary).lower()
    vtitle = viral_title(title, summary)

    # Extract real sentences from summary
    raw_sentences = re.split(r"(?<=[.!?])\s+", summary)
    facts = [s.strip() for s in raw_sentences if len(s.strip()) > 30][:4]

    # ── ACT 1: HOOK (0–3s) — punchline first, no warmup ──────────────────────
    if "transfer" in cat.lower():
        hook = f"[0–3s] {em} {title} — and the football world is NOT ready for this."
    elif "drama" in cat.lower():
        hook = f"[0–3s] 💥 This is the story nobody in football wants to talk about. {title}."
    elif "injury" in cat.lower():
        hook = f"[0–3s] 😭 {title}. And the timing could not be worse."
    elif "world cup" in cat.lower():
        hook = f"[0–3s] 🏆 {title}. The World Cup just got a lot more interesting."
    else:
        hook = f"[0–3s] ⚽ {title}. Most people have no idea this is happening right now."

    # ── ACT 2: CONTEXT (4–15s) — why should they care ────────────────────────
    if facts:
        context = f"[4–15s] Here's what you need to know. {facts[0]}"
    else:
        if "transfer" in cat.lower():
            context = f"[4–15s] You'd think this was a simple story. But there's a layer to this that most people are completely missing."
        elif "world cup" in cat.lower():
            context = f"[4–15s] With the World Cup just days away, every single move matters. And this one? Changes everything."
        else:
            context = f"[4–15s] This isn't just another football story. There's a reason this is the most talked-about topic in football right now."

    # ── ACT 3: REVEAL (16–50s) — the full story, fast and punchy ─────────────
    reveal_lines = []
    if facts:
        for i, fact in enumerate(facts[1:], 1):
            reveal_lines.append(f"  👉 {fact}")
    if not reveal_lines:
        # Fallback beats based on category
        if "transfer" in cat.lower():
            reveal_lines = [
                f"  👉 The fee being discussed? Absolutely insane.",
                f"  👉 The club involved did NOT see this coming.",
                f"  👉 And here's the part that makes this even wilder — the player reportedly had other options.",
                f"  👉 But they chose THIS. And now everyone is asking why.",
            ]
        elif "drama" in cat.lower():
            reveal_lines = [
                f"  👉 The story starts with something most fans completely ignored.",
                f"  👉 Then things escalated fast. And NOBODY stepped in to stop it.",
                f"  👉 By the time the club realized what was happening, the damage was done.",
                f"  👉 And football Twitter? Absolutely losing it.",
            ]
        elif "injury" in cat.lower():
            reveal_lines = [
                f"  👉 The injury happened at the worst possible moment.",
                f"  👉 The club now has a huge gap to fill — and not much time to do it.",
                f"  👉 Fans are already reacting, and the mood is grim.",
                f"  👉 The question now is: can they survive this setback?",
            ]
        else:
            reveal_lines = [
                f"  👉 Here's what actually happened behind the scenes.",
                f"  👉 The decision was made — and most people weren't even told.",
                f"  👉 Now the fallout is starting to hit. And it's messy.",
                f"  👉 This is the kind of story that only comes out weeks later. Except it's happening NOW.",
            ]
    reveal = "[16–50s]\n" + "\n".join(reveal_lines)

    # ── ACT 4: PUNCHLINE + CTA (50–60s) — opinion that invites comments ──────
    if "transfer" in cat.lower():
        punchline = "[50–60s] This transfer window is genuinely cooked. 💀 And we're not even at the peak yet."
        cta = "💬 Is this the deal of the summer — or the biggest mistake? Comment below 👇 | 🔔 Follow for daily football drops."
    elif "drama" in cat.lower():
        punchline = "[50–60s] Football drama never hits different than this. 💥 Genuinely one of the wildest stories of the season."
        cta = "💬 Who's in the wrong here? Drop your honest take 👇 | 🔔 Follow for daily football drops."
    elif "injury" in cat.lower():
        punchline = "[50–60s] Genuinely gutting. 😭 Some players just can't catch a break. The sport is cooked sometimes."
        cta = "💬 How big a blow is this on a scale of 1–10? 👇 | 🔔 Follow for daily football drops."
    elif "world cup" in cat.lower():
        punchline = "[50–60s] The World Cup hasn't even started and it's already pure cinema. 🏆😳 Buckle up."
        cta = "💬 Who do YOU think wins the 2026 World Cup? Drop it below 👇 | 🔔 Follow for daily football drops."
    else:
        punchline = "[50–60s] Football never stops delivering. And honestly? This is just the beginning. 😳💀"
        cta = "💬 What do you think about this? Let's discuss 👇 | 🔔 Follow for daily football drops."

    return {
        "viral_title": vtitle,
        "hook":        hook,
        "context":     context,
        "reveal":      reveal,
        "punchline":   punchline,
        "cta":         cta,
        "cat":         cat,
        "em":          em,
    }


def _cat_css(cat: str) -> str:
    if "TRANSFER" in cat:   return "cat-transfer"
    if "DRAMA"    in cat:   return "cat-drama"
    if "INJURY"   in cat:   return "cat-injury"
    if "WORLD"    in cat:   return "cat-worldcup"
    return "cat-latest"


def build_html(articles: list[dict], generated_at: str) -> str:
    cards_html = ""
    shown = 0
    for a in articles[:25]:
        if shown >= 20:
            break

        sc = generate_script(a["title"], a["summary"])

        # Format time
        try:
            pub_dt = datetime.fromisoformat(a["pub"])
            time_str = pub_dt.strftime("%b %d · %H:%M UTC")
        except Exception:
            time_str = ""

        def esc(s): return html.escape(s)

        # Reveal lines as individual <li> items
        reveal_lines = sc["reveal"].split("\n")
        reveal_header = esc(reveal_lines[0]) if reveal_lines else ""
        reveal_items  = "".join(
            f"<li>{esc(ln.replace('  👉 ','').strip())}</li>"
            for ln in reveal_lines[1:] if ln.strip()
        )

        cards_html += f"""
        <article class="card">
          <div class="card-top">
            <span class="cat-badge {_cat_css(sc['cat'])}">{sc['cat']}</span>
            <span class="pub-time">{esc(time_str)}</span>
          </div>

          <div class="raw-title">📰 {esc(a['title'])}</div>

          <h2 class="viral-title">{esc(sc['viral_title'])}</h2>

          <div class="script-wrap">
            <div class="script-top-label">📝 COPY-READY SHORT SCRIPT · BallBlitz / FutVibes Style</div>

            <div class="act act-hook">
              <span class="act-label">🎣 HOOK · 0–3s</span>
              <p>{esc(sc['hook'].replace('[0–3s] ',''))}</p>
            </div>

            <div class="act act-context">
              <span class="act-label">📖 CONTEXT · 4–15s</span>
              <p>{esc(sc['context'].replace('[4–15s] ',''))}</p>
            </div>

            <div class="act act-reveal">
              <span class="act-label">💥 REVEAL · 16–50s</span>
              <p class="act-reveal-header">{reveal_header}</p>
              <ul class="reveal-list">{reveal_items}</ul>
            </div>

            <div class="act act-punchline">
              <span class="act-label">🔁 PUNCHLINE · 50–60s</span>
              <p>{esc(sc['punchline'].replace('[50–60s] ',''))}</p>
            </div>

            <div class="act act-cta">
              <span class="act-label">📣 CTA</span>
              <p>{esc(sc['cta'])}</p>
            </div>
          </div>

          <div class="meta">
            <span class="source">📡 {esc(a['source'])}</span>
            <a class="read-more" href="{esc(a['link'])}" target="_blank" rel="noopener">
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
<title>Football Daily Drop · {generated_at}</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;700;800&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  :root {{
    --bg:       #0a0a0a;
    --bg2:      #111111;
    --bg3:      #1a1a1a;
    --border:   rgba(255,255,255,0.07);
    --text:     #f0f0f0;
    --muted:    #888;
    --orange:   #FF6B35;
    --blue:     #00C9FF;
    --green:    #1DB954;
    --yellow:   #F5C518;
    --red:      #E53935;
  }}
  body {{
    font-family: 'Inter', sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    font-size: 15px;
  }}

  /* ── HEADER ── */
  .hero {{
    padding: 50px 40px 36px;
    border-bottom: 1px solid var(--border);
    position: relative;
    overflow: hidden;
  }}
  .hero::before {{
    content: '⚽';
    position: absolute;
    right: -10px; top: -20px;
    font-size: 200px;
    opacity: 0.04;
    pointer-events: none;
  }}
  .hero-label {{
    font-family: 'Syne', sans-serif;
    font-size: 11px;
    letter-spacing: 3px;
    text-transform: uppercase;
    color: var(--green);
    margin-bottom: 10px;
  }}
  .hero h1 {{
    font-family: 'Syne', sans-serif;
    font-size: clamp(26px, 4vw, 48px);
    font-weight: 800;
    line-height: 1.1;
    margin-bottom: 10px;
  }}
  .hero h1 span {{ color: var(--orange); }}
  .hero p {{ color: var(--muted); font-size: 13px; max-width: 540px; }}
  .live-pill {{
    display: inline-block;
    background: var(--red);
    color: #fff;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.5px;
    padding: 2px 8px;
    border-radius: 4px;
    margin-left: 10px;
    vertical-align: middle;
    animation: blink 2s infinite;
  }}
  @keyframes blink {{ 0%,100%{{opacity:1}} 50%{{opacity:.5}} }}

  /* ── STATS ── */
  .stats-bar {{
    display: flex;
    gap: 10px;
    padding: 20px 40px;
    border-bottom: 1px solid var(--border);
    flex-wrap: wrap;
  }}
  .stat-chip {{
    background: var(--bg3);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px 18px;
    flex: 1;
    min-width: 110px;
    text-align: center;
  }}
  .stat-chip .sv {{
    font-family: 'Syne', sans-serif;
    font-size: 22px;
    font-weight: 800;
    color: var(--yellow);
    display: block;
  }}
  .stat-chip .sl {{ font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; }}

  /* ── MAIN ── */
  main {{ max-width: 900px; margin: 0 auto; padding: 30px 24px 70px; display: flex; flex-direction: column; gap: 22px; }}

  /* ── CARD ── */
  .card {{
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 14px;
    overflow: hidden;
    transition: border-color .2s, transform .15s;
  }}
  .card:hover {{ border-color: rgba(255,107,53,0.4); transform: translateY(-2px); }}

  .card-top {{
    padding: 18px 20px 0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
  }}
  .cat-badge {{
    font-family: 'Syne', sans-serif;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
    padding: 3px 10px;
    border-radius: 20px;
    border: 1px solid;
  }}
  .cat-transfer  {{ color: var(--yellow); border-color: rgba(245,197,24,0.3); background: rgba(245,197,24,0.07); }}
  .cat-drama     {{ color: var(--orange); border-color: rgba(255,107,53,0.3); background: rgba(255,107,53,0.07); }}
  .cat-injury    {{ color: var(--blue);   border-color: rgba(0,201,255,0.3);  background: rgba(0,201,255,0.07); }}
  .cat-worldcup  {{ color: var(--green);  border-color: rgba(29,185,84,0.3);  background: rgba(29,185,84,0.07); }}
  .cat-latest    {{ color: var(--muted);  border-color: var(--border);        background: var(--bg3); }}
  .pub-time {{ font-size: 12px; color: var(--muted); }}

  .raw-title {{
    padding: 10px 20px 0;
    font-size: 11px;
    color: var(--muted);
    font-style: italic;
  }}
  .viral-title {{
    font-family: 'Syne', sans-serif;
    font-size: 1.15rem;
    font-weight: 800;
    line-height: 1.3;
    padding: 8px 20px 16px;
    color: var(--text);
  }}

  /* ── SCRIPT BLOCK ── */
  .script-wrap {{
    border-top: 1px solid var(--border);
    background: #0d0d0d;
  }}
  .script-top-label {{
    padding: 8px 16px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: var(--orange);
    background: rgba(255,107,53,0.06);
    border-bottom: 1px solid var(--border);
  }}
  .act {{
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
    font-size: 13px;
    line-height: 1.6;
  }}
  .act:last-child {{ border-bottom: none; }}
  .act-label {{
    display: inline-block;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-bottom: 5px;
    padding: 2px 7px;
    border-radius: 4px;
  }}
  .act-hook     .act-label {{ background: rgba(229,57,53,0.15);   color: var(--red); }}
  .act-context  .act-label {{ background: rgba(0,201,255,0.12);   color: var(--blue); }}
  .act-reveal   .act-label {{ background: rgba(29,185,84,0.12);   color: var(--green); }}
  .act-punchline .act-label{{ background: rgba(245,197,24,0.12);  color: var(--yellow); }}
  .act-cta      .act-label {{ background: rgba(255,107,53,0.12);  color: var(--orange); }}

  .act p {{ color: #ccc; }}
  .act-reveal-header {{ color: var(--muted); font-size: 11px; margin-bottom: 6px; }}
  .reveal-list {{ list-style: none; padding: 0; margin: 0; }}
  .reveal-list li {{
    color: #ddd;
    padding: 3px 0 3px 16px;
    position: relative;
    font-size: 13px;
  }}
  .reveal-list li::before {{ content: '→'; position: absolute; left: 0; color: var(--green); }}
  .act-cta p {{ color: var(--orange); font-weight: 500; }}

  /* ── META ── */
  .meta {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 20px;
    font-size: 12px;
    color: var(--muted);
    border-top: 1px solid var(--border);
    flex-wrap: wrap;
    gap: 6px;
    background: var(--bg2);
  }}
  .read-more {{
    color: var(--green);
    text-decoration: none;
    font-weight: 600;
  }}
  .read-more:hover {{ text-decoration: underline; }}

  /* ── FOOTER ── */
  footer {{
    text-align: center;
    color: var(--muted);
    font-size: 12px;
    padding: 28px 20px;
    border-top: 1px solid var(--border);
  }}

  @media (max-width: 600px) {{
    .hero {{ padding: 36px 20px 28px; }}
    .stats-bar {{ padding: 16px 20px; }}
    main {{ padding: 20px 14px 50px; }}
  }}
</style>
</head>
<body>

<div class="hero">
  <div class="hero-label">Daily Research Report · Football Shorts</div>
  <h1>Football Daily <span>Drop</span> <span class="live-pill">LIVE</span></h1>
  <p>Top stories, transfers, drama &amp; World Cup news from the last 24 hours — scripted in BallBlitz / FutVibes short-form style. Copy-ready.</p>
  <p style="margin-top:8px; font-size:12px; color:#555;">Generated: {generated_at}</p>
</div>

<div class="stats-bar">
  <div class="stat-chip"><span class="sv">{shown}</span><span class="sl">Stories</span></div>
  <div class="stat-chip"><span class="sv">24h</span><span class="sl">Window</span></div>
  <div class="stat-chip"><span class="sv">10+</span><span class="sl">Sources</span></div>
  <div class="stat-chip"><span class="sv">4-Act</span><span class="sl">Scripts</span></div>
  <div class="stat-chip"><span class="sv">🏆</span><span class="sl">World Cup</span></div>
</div>

<main>
  {cards_html}
</main>

<footer>
  ⚽ Football Daily Drop · Auto-updated every 24h · Scripts modelled on BallBlitz &amp; FutVibes · {generated_at}
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
