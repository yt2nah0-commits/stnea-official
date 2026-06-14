"""
St.NEA AIコラム配信パイプライン — 設定
環境変数 or .env ファイルで上書き可能
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

# ── Claude API ─────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ── メール設定 ──────────────────────────────────────────
SMTP_HOST     = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT     = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER     = os.environ.get("SMTP_USER", "")          # 送信元アドレス
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")      # アプリパスワード等
ADMIN_EMAIL_PRIMARY   = "yaita-tetsuro@nishikawa1566.com"
ADMIN_EMAIL_FALLBACK  = "yt2nah0@gmail.com"

# ── パス ───────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent.parent
DB_PATH       = Path(__file__).parent / "db" / "articles.db"
COLUMN_JSON   = BASE_DIR / "column_feed.json"

# ── RSS ソース ─────────────────────────────────────────
RSS_FEEDS = [
    {"url": "https://www.anthropic.com/news.rss",                            "source": "Anthropic"},
    {"url": "https://openai.com/news.rss",                                   "source": "OpenAI"},
    {"url": "https://blog.google/technology/ai/rss/",                        "source": "Google"},
    {"url": "https://techcrunch.com/category/artificial-intelligence/feed/", "source": "TechCrunch"},
    {"url": "https://venturebeat.com/category/ai/feed/",                     "source": "VentureBeat"},
]

MAJOR_SOURCES = {"Anthropic", "OpenAI", "Google", "Meta"}  # イレギュラー即時配信対象

# ── パイプライン設定 ────────────────────────────────────
COLLECT_INTERVAL_HOURS = 2
FRESHNESS_DAYS         = 10      # 取得からこの日数以内のNG記事は修正後再キュー候補
NG_RATE_THRESHOLD      = 0.5    # 通過率がこれを下回ったら配信見送り
MAX_ITEMS_PER_FEED     = 5
MAX_TOTAL_ITEMS        = 20

# 定期配信スケジュール（APScheduler用）
WEEKLY_DAY    = "mon"
WEEKLY_HOUR   = 8
WEEKLY_MINUTE = 30

# ── GitHubへpush（GitHub Pages自動反映）────────────────
GIT_REPO_PATH = BASE_DIR   # stnea-official/
AUTO_GIT_PUSH = True
