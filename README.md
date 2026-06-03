# ⚽ Football Daily Drop

Auto-generated daily football research page — top stories, transfers, drama, and World Cup news from the last 24 hours, formatted as short-form video scripts in BallBlitz90 style.

## 🔗 Your Live Link
Once deployed:
```
https://YOUR-GITHUB-USERNAME.github.io/football-daily/
```

---

## 🚀 Setup (One-time, ~5 minutes)

### Step 1 — Create a GitHub repo
1. Go to [github.com](https://github.com) → sign in (or create a free account)
2. Click **New repository**
3. Name it: `football-daily`
4. Set to **Public**
5. Click **Create repository**

### Step 2 — Upload these files
Upload all files from this folder to your new GitHub repo:
- `fetch_news.py`
- `requirements.txt`
- `.github/workflows/daily.yml`
- `README.md`

(Drag and drop them into the GitHub web UI, or use GitHub Desktop)

### Step 3 — Enable GitHub Pages
1. In your repo → **Settings** → **Pages**
2. Source: **Deploy from a branch**
3. Branch: **gh-pages** → **/ (root)**
4. Click **Save**

### Step 4 — Run it for the first time
1. Go to **Actions** tab in your repo
2. Click **Football Daily Drop**
3. Click **Run workflow** → **Run workflow**
4. Wait ~60 seconds
5. Your page is live at: `https://YOUR-USERNAME.github.io/football-daily/`

### Step 5 — It runs automatically every day at 07:00 UTC 🎉

---

## 📖 What it covers
| Category | Topics |
|----------|--------|
| 🔥 TRANSFER | Signings, bids, fees, contract news |
| 💥 DRAMA | Rows, bans, sackings, social media clashes |
| 🤕 INJURY | Player fitness, returns, ruled out |
| 🌍 WORLD CUP | Squad news, results, group stage |
| 📰 LATEST | General football news |

**Clubs tracked:** Barcelona, Real Madrid, Chelsea, Arsenal, Man City, Man Utd, Liverpool, PSG, Bayern, Juventus, Inter, Atletico, Tottenham

**Countries:** England, Spain, Brazil, Argentina, France, Germany, Portugal

---

## 🛠 Local run
```bash
pip install feedparser
py fetch_news.py        # Windows
python fetch_news.py    # Mac/Linux
```
Opens `index.html` locally in your browser.

---

## 🔧 Customize
- Change the daily run time: edit `cron: "0 7 * * *"` in `.github/workflows/daily.yml`
- Add more RSS feeds: add to the `FEEDS` list in `fetch_news.py`
- Change how many stories show: edit `articles[:25]` in `build_html()`
