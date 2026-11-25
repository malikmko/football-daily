"""
Football Daily Research Script
Fetches trending football stories from the last 24 hours across RSS feeds
and generates a styled HTML report in BallBlitz90 short-form style.
"""

import feedparser
import json
import os
import re
import time
import html
from datetime import datetime, timezone, timedelta
from pathlib import Path
import urllib.request
import urllib.error
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
    return sum(2 if kw in t else 0 for kw in HOT_KEYWORDS) + _buzz_score(t)


# ── Creator / fan buzz (trends.json, pushed by the local "football intel" farm) ──
def load_buzz(max_age_hours: int = 36) -> dict:
    p = Path(__file__).parent / "trends.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        age = datetime.now(timezone.utc) - datetime.fromisoformat(d["generated"])
        if age > timedelta(hours=max_age_hours):
            print(f"  [buzz] trends.json is {age} old - ignoring")
            return {}
        print(f"  [buzz] loaded {len(d.get('items', []))} creator/fan items, {d.get('counts')}")
        return d
    except Exception as e:
        print(f"  [buzz] none ({type(e).__name__})")
        return {}


BUZZ = load_buzz()
BUZZ_TERMS = {t: n for t, n in BUZZ.get("top_terms", [])}


def _buzz_score(t: str) -> int:
    """+3 per buzz name in the story (more if several creators mention it), capped."""
    s = sum(3 + min(n, 3) for term, n in BUZZ_TERMS.items()
            if re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", t))
    return min(s, 15)


def buzz_block(limit: int = 60) -> str:
    items = BUZZ.get("items", [])[:limit]
    if not items:
        return ""
    lines = "\n".join(
        f"- [{i['platform']}] {i['source']}: {i['title']} (engagement {i.get('engagement')})"
        for i in items
    )
    return f"""
CREATOR & FAN BUZZ (what the YouTube/TikTok creators and fan communities we follow posted in the last
{BUZZ.get('window_hours', 48)}h; these are NOT stories, just demand signals):
{lines}

HOW TO USE THE BUZZ
- Prefer stories that people are already talking about above (proven demand), especially ones with high engagement
  or covered by several creators.
- But find a DIFFERENT angle from the one those creators already used, and prefer details they missed.
- Name in "buzz" which creators/communities touched the topic and the angle they took ("" if none).
"""


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


# Free tier (per your AI Studio limits): 3.8 Flash = 5 req/min, 20 req/day;
# 3.1 Flash Lite = 15 req/min, 500 req/day. We make 1 request/day, so both are fine.
# Override with env GEMINI_MODEL="modelA,modelB" (tried in order).
GEMINI_MODELS = [
    m.strip() for m in os.environ.get("GEMINI_MODEL", "gemini-3.8-flash,gemini-3.1-flash-lite").split(",")
    if m.strip()
]
AI_PICKS = 12          # exactly how many stories the page shows
AI_CANDIDATES = 40     # how many keyword-ranked stories Gemini chooses from

_VALID_CATS = {
    "TRANSFER": "🔥 TRANSFER", "DRAMA": "💥 DRAMA", "INJURY": "🤕 INJURY",
    "WORLD CUP": "🌍 WORLD CUP", "LATEST": "📰 LATEST",
}

# ── The viral formats the user taught us (names shown on every card) ───────────
FORMATS = {
    "BallBlitz": (
        "Hot-take short. TITLE: sentence case, one named star/club, strong claim, ends with '!' or '.', "
        "then an emoji pair (😳💔 shock/sad, 🤡🤣 or 🤣☠️ mockery, 😳😨 scam/fear); optional bracket joke "
        "like '(Bro stole from the thief! 🤣)'. Patterns: 'The real reason why...', '<X> should be banned/retire', "
        "'<Club> did <Y> dirty', 'Biggest scam ever'. SCRIPT ~110-130 words, one idea per line: line 1 restates the "
        "claim boldly, quick context with stats, build-up with a joke or quote, twist in the last 2 lines."),
    "FutVibes": (
        "Gossip shorts. TITLE: plain shocking claim about one named star, sentence case, ends with '.' then 😭 plus "
        "a second emoji (🤔 suspicious, 💔 tragic, 💀 funny). No hashtags. SCRIPT ~90-110 words: open with 'Why is no "
        "one talking about...' / '<Name> needs to be investigated' style provocation, teaser line, rapid facts with "
        "minutes/ages/numbers, end on the punch image or reported twist."),
    "GoalLine": (
        "News clip, one incident. TITLE: ALL-CAPS key name or club + possessive, then Title Case teaser phrase that "
        "hints the angle without the detail ('Says More Than You Think', 'Has One Awkward Problem'), then 3-4 topic "
        "hashtags (competition, club, player). No emoji. SCRIPT ~70-90 words: witty framing line, incident in order "
        "with names/numbers, one vivid detail, dry ironic closing line."),
    "Mide Talks Football": (
        "First-person fan opinion. TITLE = a Title Case headline (a take or contrast, no emoji). Put a 2-4 sentence "
        "caption in the 'caption' field ending with a question or punchline. 7-10 hashtags (players, clubs, league, "
        "#FootballTok, #MideTalksFootball). SCRIPT ~120-140 words in 'I' voice: hook ('I need to know...', 'Enough of "
        "this...'), claim + stats, then a callback to the opening line, comment-bait last line."),
    "Chilena TV": (
        "Long-form analysis, PT. series. TITLE: Title Case with one ALL-CAPS power word (BREAKING, FAR WORSE, "
        "TERRIFYING, EXACTLY, WARNED, UNCOMFORTABLE) and a 'PT.1' suffix. SCRIPT ~160-190 words: cold-open confusion "
        "hook ('necesito que me expliquen algo' energy, in English), stack facts, promise ('I'll explain exactly why'), "
        "context of how we got here, item-by-item with fee/stat and a rival angle, finish on a paradox/open loop for PT.2."),
    "Narrative of the Exception": (
        "Cinematic documentary narration. TITLE: Title Case thesis sentence, no emoji, no hashtags (superlative, "
        "'Only', or 'REAL'). SCRIPT ~120-140 words: open on the strangest fact, a short pivot line, chronological "
        "build with numbers, rhythmic contrasts ('Precision against imagination'), reframing line, closing sentence "
        "that lands the theme."),
    "Ahmed's Goal": (
        "Calm curiosity explainer. TITLE: sentence-case question or 'Players/Transfers who...' promise, no emoji, "
        "at most one ALL-CAPS word, then these exact hashtags: #FIFAWorldCup #FIFATikTokCreator #TikTokCampaign "
        "#SoccerTikTok. SCRIPT ~110-130 words, one sentence per line: restate the question, setup with dates/numbers, "
        "'But...' pivots, one soft line 'if you're enjoying the video, please hit the follow button' near the middle, "
        "an ironic twist, one-line takeaway."),
    "Lxthalfc Top 5": (
        "Ranked list. ONLY use if the story text itself contains or clearly supports 5 items. TITLE: 'Top 5 <Player/"
        "Topic> \"<Loaded Word>\" Moments in Football'. SCRIPT: 5 numbered items counting down, each one line with "
        "a jab, ~100 words."),
    "_esrbball Imagine": (
        "Imagine-format sad edit. ONLY use for a young star whose story parallels a known legend's career tragedy. "
        "TITLE: '<short lowercase sad line> man..<one emoji from 🥹🥲😢💔> || Watch till the end. ||' plus hashtags "
        "#fyp #<youngStar> #<legend> #edit #trending. SCRIPT ~80-100 words: 'Imagine <star> becoming...', rise, 'But "
        "then everything changes', fall, 'Luckily it's just my imagination, but it did happen to someone.'"),
}
FORMAT_NAMES = list(FORMATS.keys())


def _fmt_key(name: str) -> str | None:
    n = re.sub(r"[^a-z0-9]", "", str(name).lower())
    for k in FORMAT_NAMES:
        if re.sub(r"[^a-z0-9]", "", k.lower()) == n:
            return k
    return None


def ai_rank_and_script(articles: list[dict]) -> list[dict]:
    """
    ONE Gemini call: picks the AI_PICKS stories most likely to go viral (drama, shock,
    big names, transfers, World Cup) and writes each as a title + script in the best
    fitting teaching format. Returns articles with an "ai" dict, or [] on any failure
    (caller falls back to keyword mode).
    """
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("  [ai] GEMINI_API_KEY not set - using keyword mode")
        return []

    cands = articles[:AI_CANDIDATES]
    listing = "\n".join(
        f"[{i}] ({a['source']}) {a['title']} - {a['summary'][:500]}"
        for i, a in enumerate(cands)
    )
    format_guide = "\n".join(f"- {name}: {rules}" for name, rules in FORMATS.items())
    prompt = f"""You are a football short-form video producer. Below are football stories from the last 24 hours.

TASK: pick exactly {AI_PICKS} DIFFERENT stories (skip duplicates of the same event) with the highest viral
potential: drama, rows, shocks, big transfers, injuries to stars, World Cup, controversy, huge names. Skip routine
match reports unless something dramatic happened. For each pick, choose the ONE format below that fits the story
best and write the title and script in that format's style.

FORMATS (use these exact names):
{format_guide}

RULES
- Use at least 5 different formats across the {AI_PICKS} picks and no format more than 3 times.
- FACTS: use ONLY facts present in the story text. Never invent quotes, fees, stats, scores or events. If the text
  is thin, write a shorter script rather than making things up. Exaggerated tone is fine, false facts are not.
- Scripts are SPOKEN narration: short lines, no stage directions, no timestamps, no hashtags inside the script.
- Order picks by viral potential, best first.
{buzz_block()}
Return a JSON array of exactly {AI_PICKS} objects, each with exactly these keys:
  "index": the [number] of the story,
  "format": one of the format names above, exactly,
  "category": one of "TRANSFER", "DRAMA", "INJURY", "WORLD CUP", "LATEST",
  "why_viral": one short sentence on why this will spread,
  "buzz": which followed creators/communities already covered it and their angle, or "",
  "title": the title in that format's style (no hashtags in it),
  "caption": a caption if the format uses one (Mide Talks Football), otherwise "",
  "hashtags": array of hashtags if the format uses them, otherwise [],
  "script": array of strings, one spoken line each.

STORIES:
{listing}"""

    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.8},
    }).encode("utf-8")

    picks, used_model = None, None
    for model in GEMINI_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": "application/json", "x-goog-api-key": key},
        )
        try:
            for attempt in (1, 2):
                try:
                    with urllib.request.urlopen(req, timeout=240) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                    break
                except (urllib.error.HTTPError, TimeoutError, urllib.error.URLError) as e:
                    code = getattr(e, "code", "timeout")
                    if attempt == 1 and code in (429, 500, 503, "timeout"):
                        print(f"  [ai] {model}: {code}, retrying in 20s")
                        time.sleep(20)
                        continue
                    raise
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            picks, used_model = json.loads(text), model
            break
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            print(f"  [ai] {model}: HTTP {e.code}: {detail}")
        except Exception as e:
            print(f"  [ai] {model}: failed ({type(e).__name__}: {e})")
    if picks is None:
        print("  [ai] all Gemini models failed - using keyword mode")
        return []

    chosen, used = [], set()
    for p in picks if isinstance(picks, list) else []:
        try:
            i = int(p["index"])
            if i in used or not 0 <= i < len(cands):
                continue
            script = [str(x).strip() for x in p["script"] if str(x).strip()]
            title = str(p["title"]).strip()
            if not script or not title:
                continue
            tags = [str(h).strip() for h in (p.get("hashtags") or []) if str(h).strip()]
            # Gemini sometimes repeats hashtags inside the title: move them to the tag row
            m = re.search(r"(?:\s+#\w+)+\s*$", title)
            if m:
                tags = tags or re.findall(r"#\w+", m.group(0))
                title = title[:m.start()].rstrip()
            a = dict(cands[i])
            a["ai"] = {
                "format":    _fmt_key(p.get("format", "")) or "BallBlitz",
                "cat":       _VALID_CATS.get(str(p.get("category", "")).upper(), "📰 LATEST"),
                "why_viral": str(p.get("why_viral", "")).strip(),
                "buzz":      str(p.get("buzz", "") or "").strip(),
                "title":     title,
                "caption":   str(p.get("caption", "") or "").strip(),
                "hashtags":  tags,
                "script":    script,
            }
            used.add(i)
            chosen.append(a)
        except Exception:
            continue
    chosen = chosen[:AI_PICKS]
    print(f"  [ai] Gemini ({used_model}) picked {len(chosen)} stories in formats: "
          + ", ".join(sorted({a['ai']['format'] for a in chosen})))
    return chosen


def keyword_fallback(a: dict) -> dict:
    """Same shape as the AI result, built from the old template generator."""
    sc = generate_script(a["title"], a["summary"])
    strip = lambda s: re.sub(r"^\[[^\]]*\]\s*", "", s).strip()
    lines = [strip(sc["hook"]), strip(sc["context"])]
    lines += [ln.replace("👉", "").strip() for ln in sc["reveal"].split("\n")[1:] if ln.strip()]
    lines += [strip(sc["punchline"]), sc["cta"]]
    out = dict(a)
    out["ai"] = {
        "format": "BallBlitz", "cat": sc["cat"], "why_viral": "Keyword-scored (Gemini unavailable).",
        "title": sc["viral_title"], "caption": "", "hashtags": [], "script": lines,
    }
    return out


def _cat_css(cat: str) -> str:
    if "TRANSFER" in cat:   return "cat-transfer"
    if "DRAMA"    in cat:   return "cat-drama"
    if "INJURY"   in cat:   return "cat-injury"
    if "WORLD"    in cat:   return "cat-worldcup"
    return "cat-latest"


_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Football Daily Drop · __GENERATED__</title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg:#0a0a0a; --bg2:#121212; --bg3:#1b1b1b; --border:rgba(255,255,255,.08);
    --text:#f2f2f2; --muted:#8a8a8a; --orange:#FF6B35; --blue:#00C9FF; --green:#1DB954;
    --yellow:#F5C518; --red:#E53935; --pink:#ff4fa3; --purple:#a77bff;
  }
  body { font-family:'Inter',sans-serif; background:var(--bg); color:var(--text); line-height:1.6; font-size:15px; -webkit-font-smoothing:antialiased; }
  .hero { padding:44px 28px 26px; max-width:1000px; margin:0 auto; }
  .hero-label { font-family:'Plus Jakarta Sans','Inter',sans-serif; font-size:11px; letter-spacing:3px; text-transform:uppercase; color:var(--green); margin-bottom:8px; }
  .hero h1 { font-family:'Plus Jakarta Sans','Inter',sans-serif; font-size:clamp(26px,4.5vw,46px); font-weight:800; line-height:1.1; }
  .hero h1 span { color:var(--orange); }
  .hero p { color:var(--muted); font-size:13px; max-width:620px; margin-top:8px; }
  .toolbar { max-width:1000px; margin:0 auto; padding:0 28px 18px; display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
  .chip { background:var(--bg3); border:1px solid var(--border); color:#ccc; border-radius:20px; padding:5px 13px;
          font-size:12px; cursor:pointer; font-family:inherit; }
  .chip:hover { border-color:rgba(255,255,255,.25); }
  .chip.on { background:var(--orange); border-color:var(--orange); color:#111; font-weight:700; }
  .toolbar .count { margin-left:auto; color:var(--muted); font-size:12px; }
  main { max-width:1000px; margin:0 auto; padding:6px 28px 70px; display:grid; grid-template-columns:repeat(auto-fill,minmax(440px,1fr)); gap:20px; }
  .card { background:var(--bg2); border:1px solid var(--border); border-radius:16px; overflow:hidden; display:flex; flex-direction:column; }
  .card.hide { display:none; }
  .card-head { padding:16px 18px 0; display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
  .rank { font-family:'Plus Jakarta Sans','Inter',sans-serif; font-weight:800; font-size:13px; color:#111; background:var(--yellow); border-radius:6px; padding:1px 8px; }
  .fmt { font-family:'Plus Jakarta Sans','Inter',sans-serif; font-size:13px; font-weight:700; padding:4px 13px; border-radius:20px; border:1px solid; }
  .fmt small { font-size:10px; font-weight:600; letter-spacing:1.2px; opacity:.65; margin-right:7px; }
  .f0{color:#ff8a5c;border-color:#ff8a5c55;background:#ff8a5c14}.f1{color:#ff4fa3;border-color:#ff4fa355;background:#ff4fa314}
  .f2{color:#00C9FF;border-color:#00C9FF55;background:#00C9FF14}.f3{color:#F5C518;border-color:#F5C51855;background:#F5C51814}
  .f4{color:#a77bff;border-color:#a77bff55;background:#a77bff14}.f5{color:#7ee0a6;border-color:#7ee0a655;background:#7ee0a614}
  .f6{color:#ffb347;border-color:#ffb34755;background:#ffb34714}.f7{color:#9ad0ff;border-color:#9ad0ff55;background:#9ad0ff14}
  .f8{color:#f28bb3;border-color:#f28bb355;background:#f28bb314}
  .cat-badge { font-size:10px; font-weight:700; letter-spacing:1px; text-transform:uppercase; padding:2px 9px; border-radius:20px; border:1px solid var(--border); color:var(--muted); }
  .cat-transfer{color:var(--yellow)}.cat-drama{color:var(--orange)}.cat-injury{color:var(--blue)}.cat-worldcup{color:var(--green)}
  .pub-time { margin-left:auto; font-size:11px; color:var(--muted); }
  .title { font-family:'Plus Jakarta Sans','Inter',sans-serif; font-size:1.35rem; font-weight:700; line-height:1.3; letter-spacing:-.01em; padding:14px 18px 6px; }
  .caption { padding:0 18px; font-size:14px; color:#c4c4c4; line-height:1.6; }
  .tags { padding:8px 18px 0; display:flex; flex-wrap:wrap; gap:5px; }
  .tag { font-size:12px; color:var(--blue); }
  .why { margin:14px 18px 0; font-size:13px; color:#b5b5b5; line-height:1.5; border-left:3px solid var(--orange); padding-left:11px; }
  .why.buzz { border-left-color:var(--blue); margin-top:8px; }
  .script { margin:16px 0 0; border-top:1px solid var(--border); background:#0d0d0d; padding:14px 18px 16px; flex:1; }
  .script-label { font-size:12px; letter-spacing:.8px; text-transform:uppercase; color:var(--orange); font-weight:700; margin-bottom:10px; display:flex; justify-content:space-between; align-items:center; }
  .copy { background:none; border:1px solid var(--border); color:#bbb; border-radius:6px; font-size:11px; padding:2px 9px; cursor:pointer; font-family:inherit; }
  .copy:hover { border-color:var(--green); color:var(--green); }
  .script ol { list-style:none; counter-reset:l; }
  .script li { counter-increment:l; font-size:15px; line-height:1.65; color:#e6e6e6; padding:6px 0 6px 30px; position:relative; border-bottom:1px solid rgba(255,255,255,.04); }
  .script li:last-child { border-bottom:none; }
  .script li::before { content:counter(l); position:absolute; left:0; top:9px; width:20px; height:20px; line-height:20px; text-align:center; font-size:11px; font-weight:600; color:var(--muted); background:var(--bg3); border-radius:50%; }
  .meta { display:flex; justify-content:space-between; align-items:center; gap:8px; flex-wrap:wrap; padding:11px 18px; border-top:1px solid var(--border); font-size:12px; color:var(--muted); }
  .meta .raw { font-style:italic; flex:1 1 100%; font-size:11px; }
  .read-more { color:var(--green); text-decoration:none; font-weight:600; }
  .read-more:hover { text-decoration:underline; }
  footer { text-align:center; color:var(--muted); font-size:12px; padding:26px 20px; border-top:1px solid var(--border); }
  @media (max-width:520px) { main { grid-template-columns:1fr; padding:6px 14px 50px; } .hero,.toolbar { padding-left:14px; padding-right:14px; } }
</style>
</head>
<body>
<div class="hero">
  <div class="hero-label">Daily Viral Research · Football Shorts</div>
  <h1>Football Daily <span>Top __COUNT__</span></h1>
  <p>The __COUNT__ stories most likely to go viral in the last 24 hours, each written in the short-form format that fits it best. Generated: __GENERATED__</p>
</div>
<div class="toolbar">
  <button class="chip on" data-f="all">All</button>
  __CHIPS__
  <span class="count" id="count">__COUNT__ stories</span>
</div>
<main>
__CARDS__
</main>
<footer>⚽ Football Daily Drop · Auto-updated daily · __SRC__ sources · __GENERATED__</footer>
<script>
  const chips = document.querySelectorAll('.chip'), cards = document.querySelectorAll('.card');
  chips.forEach(c => c.addEventListener('click', () => {
    chips.forEach(x => x.classList.remove('on')); c.classList.add('on');
    let n = 0;
    cards.forEach(card => {
      const show = c.dataset.f === 'all' || card.dataset.f === c.dataset.f;
      card.classList.toggle('hide', !show); if (show) n++;
    });
    document.getElementById('count').textContent = n + ' stories';
  }));
  document.querySelectorAll('.copy').forEach(b => b.addEventListener('click', () => {
    const card = b.closest('.card');
    const lines = [...card.querySelectorAll('.script li')].map(li => li.textContent).join('\\n');
    const t = card.querySelector('.title').textContent;
    const cap = card.querySelector('.caption');
    const tags = [...card.querySelectorAll('.tag')].map(x => x.textContent).join(' ');
    const txt = t + '\\n' + (cap ? cap.textContent + '\\n' : '') + (tags ? tags + '\\n' : '') + '\\n' + lines;
    (navigator.clipboard ? navigator.clipboard.writeText(txt) : Promise.reject()).then(
      () => { b.textContent = 'Copied ✓'; setTimeout(() => b.textContent = 'Copy', 1500); },
      () => { b.textContent = 'Copy failed'; });
  }));
</script>
</body>
</html>"""


def build_html(articles: list[dict], generated_at: str) -> str:
    esc = html.escape
    shown = articles[:AI_PICKS]
    fmt_order = [f for f in FORMAT_NAMES if any(a["ai"]["format"] == f for a in shown)]
    fclass = {f: f"f{FORMAT_NAMES.index(f)}" for f in FORMAT_NAMES}

    chips = "".join(
        f'<button class="chip" data-f="{esc(f)}">{esc(f)}</button>' for f in fmt_order
    )

    cards = ""
    for n, a in enumerate(shown, 1):
        ai = a["ai"]
        try:
            time_str = datetime.fromisoformat(a["pub"]).strftime("%b %d · %H:%M UTC")
        except Exception:
            time_str = ""
        caption = f'<p class="caption">{esc(ai["caption"])}</p>' if ai["caption"] else ""
        tags = (
            '<div class="tags">' + "".join(f'<span class="tag">{esc(t)}</span>' for t in ai["hashtags"]) + "</div>"
            if ai["hashtags"] else ""
        )
        why = f'<div class="why">🔥 {esc(ai["why_viral"])}</div>' if ai["why_viral"] else ""
        if ai.get("buzz"):
            why += f'<div class="why buzz">📡 Already buzzing: {esc(ai["buzz"])}</div>'
        lines = "".join(f"<li>{esc(ln)}</li>" for ln in ai["script"])
        cards += f"""
<article class="card" data-f="{esc(ai['format'])}">
  <div class="card-head">
    <span class="rank">#{n}</span>
    <span class="fmt {fclass[ai['format']]}"><small>FORMAT</small>{esc(ai['format'])}</span>
    <span class="cat-badge {_cat_css(ai['cat'])}">{esc(ai['cat'])}</span>
    <span class="pub-time">{esc(time_str)}</span>
  </div>
  <h2 class="title">{esc(ai['title'])}</h2>
  {caption}
  {tags}
  {why}
  <div class="script">
    <div class="script-label"><span>📝 Script · {esc(ai['format'])}</span><button class="copy">Copy</button></div>
    <ol>{lines}</ol>
  </div>
  <div class="meta">
    <span class="raw">📰 {esc(a['title'])}</span>
    <span>📡 {esc(a['source'])}</span>
    <a class="read-more" href="{esc(a['link'])}" target="_blank" rel="noopener">Read Full Story →</a>
  </div>
</article>"""

    if not cards:
        cards = "<p style='color:#aaa;text-align:center;margin-top:60px'>No stories found in the last 24 hours.</p>"

    return (_PAGE_TEMPLATE
            .replace("__GENERATED__", esc(generated_at))
            .replace("__COUNT__", str(len(shown)))
            .replace("__CHIPS__", chips)
            .replace("__CARDS__", cards)
            .replace("__SRC__", str(len({a["source"] for a in shown}) or len(FEEDS))))


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    print("Football Daily Drop -- fetching last 24h stories...")
    articles = fetch_articles(hours=24)
    print(f"   Found {len(articles)} articles")

    ai_articles = ai_rank_and_script(articles)
    if ai_articles:
        articles = ai_articles
    else:
        articles = [keyword_fallback(a) for a in articles[:AI_PICKS]]

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
